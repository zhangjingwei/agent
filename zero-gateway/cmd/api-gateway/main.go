package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/gin-contrib/cors"
	"github.com/gin-contrib/gzip"
	"github.com/gin-contrib/requestid"
	"github.com/gin-contrib/secure"
	"github.com/redis/go-redis/v9"
	"github.com/ulule/limiter/v3"
	limiterRedis "github.com/ulule/limiter/v3/drivers/store/redis"

	"github.com/your-org/zero-gateway/internal/api"
	"github.com/your-org/zero-gateway/internal/config"
	"github.com/your-org/zero-gateway/pkg/filters"
	"github.com/your-org/zero-gateway/pkg/filters/builtin"
	"github.com/your-org/zero-gateway/pkg/middleware"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Initialize logger
	var logger *zap.Logger
	if cfg.Logging.Format == "json" {
		logger, _ = zap.NewProduction()
	} else {
		logger, _ = zap.NewDevelopment()
	}
	defer logger.Sync()

	// Set Gin mode
	if cfg.Logging.Level == "debug" {
		gin.SetMode(gin.DebugMode)
	} else {
		gin.SetMode(gin.ReleaseMode)
	}

	// Initialize router
	r := gin.New()

	// Add middleware
	r.Use(gin.Logger())
	r.Use(gin.Recovery())

	// 选择使用开源组件或自定义中间件
	// 方案1: 使用开源组件（推荐用于生产环境）
	setupMiddlewareWithOpenSource(r, cfg, logger)

	// 方案2: 使用自定义中间件（当前实现）
	// setupMiddlewareCustom(r, cfg, logger)

	// Initialize filter manager
	filterManager := filters.NewFilterManager(logger)

	// Register built-in filters
	registerBuiltinFilters(filterManager, logger)

	// Add filter middleware
	filterMiddleware := filters.NewFilterMiddleware(filterManager)
	r.Use(filterMiddleware.Handler())

	// Initialize API handlers
	apiHandler := api.NewHandler(cfg, logger)

	// Setup routes
	setupRoutes(r, apiHandler)

	// Health check endpoint
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"service":   "api-gateway",
			"timestamp": time.Now().Unix(),
		})
	})

	// Filter metrics endpoint
	r.GET("/api/v1/filters/metrics", filterManager.HealthCheckHandler())

	// Start server
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Server.Port),
		Handler:      r,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		IdleTimeout:  cfg.Server.IdleTimeout,
	}

	// Start server in a goroutine
	go func() {
		logger.Info("Starting API Gateway server",
			zap.Int("port", cfg.Server.Port),
			zap.String("mode", gin.Mode()))

		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Failed to start server", zap.Error(err))
		}
	}()

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// Give outstanding requests 30 seconds to complete
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Fatal("Server forced to shutdown", zap.Error(err))
	}

	logger.Info("Server exited")
}

// registerBuiltinFilters 注册内置过滤器
func registerBuiltinFilters(manager *filters.FilterManager, logger *zap.Logger) {
	// 审计过滤器（请求和响应）
	auditConfig := builtin.AuditConfig{
		EnableRequestLogging:  true,
		EnableResponseLogging: true,
		LogSensitiveData:      false,
		LogLevel:              "info",
	}
	auditRequestFilter := builtin.NewAuditFilter(logger, auditConfig)
	manager.RegisterRequestFilter(auditRequestFilter)
	auditResponseFilter := builtin.NewAuditResponseFilter(logger, auditConfig)
	manager.RegisterResponseFilter(auditResponseFilter)

	// 输入验证过滤器
	inputValidationConfig := builtin.InputValidationConfig{
		MaxMessageLength:    10000,
		MaxMetadataSize:     1024,
		BlockedWords:        []string{"spam", "inappropriate"}, // 示例屏蔽词
		RequiredFields:      []string{},                        // 根据API需求配置
		AllowedContentTypes: []string{"application/json"},
	}
	inputFilter := builtin.NewInputValidationFilter(logger, inputValidationConfig)
	manager.RegisterRequestFilter(inputFilter)

	// 输出处理过滤器
	outputConfig := builtin.OutputProcessingConfig{
		SanitizeOutput:     true,
		MaxResponseSize:    10 * 1024 * 1024, // 10MB
		AddResponseHeaders: true,
		CORSHeaders:        true,
		CompressionEnabled: false,
	}
	outputFilter := builtin.NewOutputProcessingFilter(logger, outputConfig)
	manager.RegisterResponseFilter(outputFilter)

	logger.Info("Built-in filters registered successfully")
}

// setupMiddlewareWithOpenSource 使用开源组件设置中间件（推荐方案）
func setupMiddlewareWithOpenSource(r *gin.Engine, cfg *config.Config, logger *zap.Logger) {
	// 1. 请求ID中间件
	r.Use(requestid.New())

	// 2. 限流中间件（强制使用 Redis 分布式限流）
	// 创建Redis客户端
	redisClient := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
		PoolSize: cfg.Redis.PoolSize,
	})

	// 验证Redis连接（强制要求）
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := redisClient.Ping(ctx).Result(); err != nil {
		logger.Fatal("Redis connection failed - Redis is required for distributed rate limiting",
			zap.Error(err),
			zap.String("redis_addr", fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port)))
		return
	}

	setupRateLimitWithRedis(r, cfg, logger, redisClient)

	// 3. CORS中间件（替换自定义实现）
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"*"},
		AllowCredentials: true,
	}))

	// 4. 安全头中间件
	r.Use(secure.New(secure.Config{
		FrameDeny:          true,
		ContentTypeNosniff: true,
		BrowserXssFilter:   true,
	}))

	// 5. Gzip压缩
	r.Use(gzip.Gzip(gzip.DefaultCompression))

	logger.Info("Using open source middleware components",
		zap.String("rate_limit", fmt.Sprintf("%d requests per %v", cfg.Security.RateLimitRequests, cfg.Security.RateLimitWindow)))
}

// setupMiddlewareCustom 使用自定义中间件设置（当前实现）
func setupMiddlewareCustom(r *gin.Engine, cfg *config.Config, logger *zap.Logger) {
	r.Use(middleware.CORS())
	r.Use(middleware.RateLimit(cfg.Security.RateLimitRequests, cfg.Security.RateLimitWindow))
	r.Use(middleware.RequestLogger(logger))
}

func setupRoutes(r *gin.Engine, handler *api.Handler) {
	apiV1 := r.Group("/api/v1")
	{
		// Chat endpoints
		apiV1.POST("/chat", handler.Chat)
		apiV1.POST("/chat/stream", handler.ChatStream)
		apiV1.POST("/sessions", handler.CreateSession)
		apiV1.GET("/sessions/:session_id/history", handler.GetHistory)
		apiV1.DELETE("/sessions/:session_id", handler.ClearSession)

		// Tools endpoints
		apiV1.GET("/tools", handler.ListTools)
	}
}

// setupRateLimitWithRedis 使用Redis存储的分布式限流
func setupRateLimitWithRedis(r *gin.Engine, cfg *config.Config, logger *zap.Logger, redisClient *redis.Client) {
	store, err := limiterRedis.NewStoreWithOptions(redisClient, limiter.StoreOptions{
		Prefix: "nexus_gateway_ratelimit:",
	})
	if err != nil {
		logger.Fatal("Failed to create Redis store for rate limiter", zap.Error(err))
		return
	}

	rate := limiter.Rate{
		Period: cfg.Security.RateLimitWindow,
		Limit:  int64(cfg.Security.RateLimitRequests),
	}
	instance := limiter.New(store, rate)

	r.Use(createRateLimitMiddleware(instance, logger))
	logger.Info("Using Redis-based distributed rate limiter",
		zap.String("redis_addr", fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port)),
		zap.Int("rate_limit", cfg.Security.RateLimitRequests),
		zap.Duration("window", cfg.Security.RateLimitWindow))
}

// createRateLimitMiddleware 创建限流中间件
func createRateLimitMiddleware(instance *limiter.Limiter, logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		context, err := instance.Get(c, c.ClientIP())
		if err != nil {
			logger.Error("Rate limiter error", zap.Error(err))
			c.Next()
			return
		}

		if context.Reached {
			c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", context.Limit))
			c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", context.Remaining))
			c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", context.Reset))
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error":       "Rate limit exceeded",
				"retry_after": context.Reset,
			})
			c.Abort()
			return
		}

		// 添加限流头信息
		c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", context.Limit))
		c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", context.Remaining))
		c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", context.Reset))

		c.Next()
	}
}
