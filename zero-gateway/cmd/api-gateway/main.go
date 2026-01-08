package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"

	"github.com/gin-contrib/requestid"
	"github.com/redis/go-redis/v9"
	"github.com/ulule/limiter/v3"
	limiterRedis "github.com/ulule/limiter/v3/drivers/store/redis"

	"zero-gateway/internal/api"
	"zero-gateway/internal/config"
	"zero-gateway/internal/infrastructure"
	"zero-gateway/pkg/cache"
	"zero-gateway/pkg/filters"
	"zero-gateway/pkg/filters/builtin"
	"zero-gateway/pkg/middleware"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Initialize logger with file output support
	var logger *zap.Logger
	var logErr error

	if cfg.Logging.OutputFile != "" {
		// 配置日志文件输出
		// 构建日志文件路径
		logFile := cfg.Logging.OutputFile
		if filepath.IsAbs(logFile) {
			// 绝对路径：确保父目录存在
			logDir := filepath.Dir(logFile)
			if err := os.MkdirAll(logDir, 0755); err != nil {
				log.Fatalf("Failed to create log directory: %v", err)
			}
		} else {
			// 相对路径：检查是否包含目录
			logDir := cfg.Logging.LogDir
			if logDir == "" {
				logDir = "logs" // 默认目录
			}

			// 如果 logFile 已经包含目录（如 logs/gateway.log），使用其父目录
			// 如果 logFile 只是文件名（如 gateway.log），放在 logDir 下
			if filepath.Dir(logFile) != "." {
				// logFile 包含目录，确保其父目录存在
				logDir = filepath.Dir(logFile)
				if err := os.MkdirAll(logDir, 0755); err != nil {
					log.Fatalf("Failed to create log directory: %v", err)
				}
				// logFile 已经是完整路径，不需要修改
			} else {
				// logFile 只是文件名，放在 logDir 下
				if err := os.MkdirAll(logDir, 0755); err != nil {
					log.Fatalf("Failed to create log directory: %v", err)
				}
				logFile = filepath.Join(logDir, logFile)
			}
		}

		// 创建日志文件
		file, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
		if err != nil {
			log.Fatalf("Failed to open log file: %v", err)
		}

		// 配置 zap logger 输出到文件
		encoderConfig := zap.NewProductionEncoderConfig()
		if cfg.Logging.Format != "json" {
			encoderConfig = zap.NewDevelopmentEncoderConfig()
		}

		encoder := zapcore.NewJSONEncoder(encoderConfig)
		if cfg.Logging.Format != "json" {
			encoder = zapcore.NewConsoleEncoder(encoderConfig)
		}

		core := zapcore.NewCore(encoder, zapcore.AddSync(file), getLogLevel(cfg.Logging.Level))

		// 如果配置了同时输出到控制台
		if os.Getenv("LOG_TO_CONSOLE") != "false" {
			consoleCore := zapcore.NewCore(
				encoder,
				zapcore.AddSync(os.Stderr),
				getLogLevel(cfg.Logging.Level),
			)
			core = zapcore.NewTee(core, consoleCore)
		}

		logger = zap.New(core, zap.AddCaller(), zap.AddStacktrace(zap.ErrorLevel))
		log.Printf("Logging to file: %s", logFile)
	} else {
		// 默认输出到 stderr
		if cfg.Logging.Format == "json" {
			logger, logErr = zap.NewProduction()
		} else {
			logger, logErr = zap.NewDevelopment()
		}
		if logErr != nil {
			log.Fatalf("Failed to initialize logger: %v", logErr)
		}
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

	// Setup middleware
	// setupMiddlewareWithOpenSource(r, cfg, logger)

	// 过滤器管理器
	filterManager := filters.NewFilterManager(logger)

	// 注册内置过滤器
	registerBuiltinFilters(filterManager, logger)

	// 添加过滤器中间件
	filterMiddleware := filters.NewFilterMiddleware(filterManager)
	r.Use(filterMiddleware.Handler())

	// 初始化 Redis 缓存（用于服务发现和会话管理）
	var redisCache *cache.RedisCache
	var serviceDiscoveryClient *infrastructure.ServiceDiscoveryClient

	if cfg.Python.UseServiceDiscovery {
		var err error
		redisCache, err = cache.NewRedisCache(
			cfg.Redis.Host,
			cfg.Redis.Port,
			cfg.Redis.Password,
			cfg.Redis.DB,
			cfg.Redis.PoolSize,
		)
		if err != nil {
			logger.Fatal("Failed to connect to Redis for service discovery", zap.Error(err))
		}

		// 创建服务发现和负载均衡器（使用 go-kit）
		serviceDiscovery := cache.NewServiceDiscovery(redisCache)
		redisInstancer := cache.NewRedisInstancer(serviceDiscovery, cfg.Python.ServiceName, logger)
		serviceDiscoveryClient = infrastructure.NewServiceDiscoveryClient(redisInstancer, cfg, logger)
		logger.Info("Service discovery enabled",
			zap.String("service_name", cfg.Python.ServiceName),
			zap.String("strategy", cfg.Python.LoadBalanceStrategy),
		)
	} else {
		logger.Info("Service discovery disabled, using static configuration")
	}

	// 初始化API处理器
	apiHandler := api.NewHandler(cfg, logger, serviceDiscoveryClient)

	// 设置路由
	api.SetupRoutes(r, apiHandler)

	// Filter metrics endpoint
	// r.GET("/api/v1/filters/metrics", filterManager.HealthCheckHandler())

	// 启动服务器
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Server.Port),
		Handler:      r,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		IdleTimeout:  cfg.Server.IdleTimeout,
	}

	// 启动服务器
	go func() {
		logger.Info("Starting API Gateway server",
			zap.Int("port", cfg.Server.Port),
			zap.String("mode", gin.Mode()))

		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Failed to start server", zap.Error(err))
		}
	}()

	// 等待中断信号以优雅地关闭服务器
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// 停止服务发现客户端
	if serviceDiscoveryClient != nil {
		serviceDiscoveryClient.Stop()
		logger.Info("Service discovery client stopped")
	}

	// 给未完成的请求30秒时间完成
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Fatal("Server forced to shutdown", zap.Error(err))
	}

	logger.Info("Server exited")
}

// getLogLevel 将字符串日志级别转换为 zapcore.Level
func getLogLevel(level string) zapcore.Level {
	switch level {
	case "debug":
		return zapcore.DebugLevel
	case "info":
		return zapcore.InfoLevel
	case "warn":
		return zapcore.WarnLevel
	case "error":
		return zapcore.ErrorLevel
	case "fatal":
		return zapcore.FatalLevel
	default:
		return zapcore.InfoLevel
	}
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
	// 请求ID中间件
	r.Use(requestid.New())

	// 限流
	// redisClient := redis.NewClient(&redis.Options{
	// 	Addr:     fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port),
	// 	Password: cfg.Redis.Password,
	// 	DB:       cfg.Redis.DB,
	// 	PoolSize: cfg.Redis.PoolSize,
	// })

	// setupRateLimitWithRedis(r, cfg, logger, redisClient)

	// 3. CORS中间件（替换自定义实现）
	// r.Use(cors.New(cors.Config{
	// 	AllowOrigins:     []string{"*"},
	// 	AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
	// 	AllowHeaders:     []string{"*"},
	// 	AllowCredentials: true,
	// }))

	// 4. 安全头中间件
	// r.Use(secure.New(secure.Config{
	// 	FrameDeny:          true,
	// 	ContentTypeNosniff: true,
	// 	BrowserXssFilter:   true,
	// }))

	// 5. Gzip压缩
	// r.Use(gzip.Gzip(gzip.DefaultCompression))

	logger.Info("Using open source middleware components", zap.String("rate_limit", fmt.Sprintf("%d requests per %v", cfg.Security.RateLimitRequests, cfg.Security.RateLimitWindow)))
}

// setupMiddlewareCustom 使用自定义中间件设置（当前实现）
func setupMiddlewareCustom(r *gin.Engine, cfg *config.Config, logger *zap.Logger) {
	r.Use(middleware.CORS())
	r.Use(middleware.RateLimit(cfg.Security.RateLimitRequests, cfg.Security.RateLimitWindow))
	r.Use(middleware.RequestLogger(logger))
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
