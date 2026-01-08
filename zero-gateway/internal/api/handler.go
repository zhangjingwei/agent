package api

import (
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"zero-gateway/internal/business"
	"zero-gateway/internal/config"
	"zero-gateway/internal/infrastructure"
	"zero-gateway/pkg/circuitbreaker"
)

// Handler 薄层 Handler，负责路由到业务服务
type Handler struct {
	chatService    *business.ChatService
	toolService    *business.ToolService
	sessionService *business.SessionService
	logger         *zap.Logger
}

// NewHandler 创建新的 API handler
func NewHandler(cfg *config.Config, logger *zap.Logger, serviceDiscovery *infrastructure.ServiceDiscoveryClient) *Handler {
	// 初始化基础设施层
	httpClient := infrastructure.NewHTTPClient(cfg, logger, serviceDiscovery)
	sessionService := infrastructure.NewSessionService(cfg, logger)
	requestService := infrastructure.NewRequestService(httpClient, sessionService, cfg, logger)

	// 初始化熔断器管理器
	var breakerManager *circuitbreaker.Manager
	if cfg.Security.CircuitBreaker.Enabled {
		userConfig := circuitbreaker.Config{
			FailureThreshold: cfg.Security.CircuitBreaker.UserFailureThreshold,
			SuccessThreshold: cfg.Security.CircuitBreaker.UserSuccessThreshold,
			Timeout:          cfg.Security.CircuitBreaker.UserTimeout,
		}
		agentConfig := circuitbreaker.Config{
			FailureThreshold: cfg.Security.CircuitBreaker.AgentFailureThreshold,
			SuccessThreshold: cfg.Security.CircuitBreaker.AgentSuccessThreshold,
			Timeout:          cfg.Security.CircuitBreaker.AgentTimeout,
		}
		breakerManager = circuitbreaker.NewManager(userConfig, agentConfig)
		logger.Info("Circuit breaker enabled",
			zap.Int("user_failure_threshold", userConfig.FailureThreshold),
			zap.Int("agent_failure_threshold", agentConfig.FailureThreshold))
	} else {
		// 如果禁用，使用默认管理器（但不会真正执行熔断检查）
		breakerManager = circuitbreaker.DefaultManager()
		logger.Info("Circuit breaker disabled, using default manager")
	}

	// 初始化业务层
	chatService := business.NewChatService(requestService, httpClient, logger, breakerManager)
	toolService := business.NewToolService(httpClient, requestService, logger)
	sessionBusinessService := business.NewSessionService(sessionService, logger)

	return &Handler{
		chatService:    chatService,
		toolService:    toolService,
		sessionService: sessionBusinessService,
		logger:         logger,
	}
}

// Chat 处理聊天请求（统一入口，根据 stream 参数路由）
func (h *Handler) Chat(c *gin.Context) {
	var req ChatRequest

	// 绑定请求体
	if err := bindJSON(c, &req); err != nil {
		h.logger.Error("Invalid chat request", zap.Error(err))
		c.JSON(400, NewErrorResponse(ErrCodeInvalidRequest, "Invalid request format"))
		return
	}

	// 验证请求体
	if req.Message == "" {
		c.JSON(400, NewErrorResponse(ErrCodeMissingField, "Message is required"))
		return
	}

	// 转换为基础设施层模型
	infraReq := &infrastructure.ChatRequest{
		SessionID: req.SessionID,
		Message:   req.Message,
		Stream:    req.Stream,
		Metadata:  req.Metadata,
	}

	// 委托给业务层处理
	h.chatService.HandleChat(c, infraReq)
}

// CreateSession 创建会话
func (h *Handler) CreateSession(c *gin.Context) {
	h.sessionService.CreateSession(c)
}

// GetHistory 获取会话历史
func (h *Handler) GetHistory(c *gin.Context) {
	h.sessionService.GetHistory(c)
}

// ClearSession 清除会话
func (h *Handler) ClearSession(c *gin.Context) {
	h.sessionService.ClearSession(c)
}

// ListTools 列出可用工具
func (h *Handler) ListTools(c *gin.Context) {
	h.toolService.ListTools(c)
}
