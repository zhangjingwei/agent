package infrastructure

import (
	"fmt"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"go.uber.org/zap"

	"zero-gateway/internal/config"
	"zero-gateway/pkg/session"
)

// SessionService 会话管理服务（基础设施层）
type SessionService struct {
	manager *session.SessionManager
	logger  *zap.Logger
}

// NewSessionService 创建会话服务
func NewSessionService(cfg *config.Config, logger *zap.Logger) *SessionService {
	// Create Redis client for session management
	redisClient := redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port),
		Password:     cfg.Redis.Password,
		DB:           cfg.Redis.DB,
		PoolSize:     cfg.Redis.PoolSize,
		MinIdleConns: 2,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
	})

	// Create session manager
	var sessionManager *session.SessionManager
	if redisClient != nil {
		sessionManager = session.NewSessionManager(redisClient)
	}

	return &SessionService{
		manager: sessionManager,
		logger:  logger,
	}
}

// CreateSession 创建新会话
func (s *SessionService) CreateSession(agentID string, metadata map[string]interface{}) (*session.Session, error) {
	if s.manager == nil {
		return nil, fmt.Errorf("session manager not available")
	}
	return s.manager.CreateSession(agentID, metadata)
}

// GetSession 获取会话
func (s *SessionService) GetSession(sessionID string) (*session.Session, error) {
	if s.manager == nil {
		return nil, fmt.Errorf("session manager not available")
	}
	return s.manager.GetSession(sessionID)
}

// GetHistory 获取会话历史
func (s *SessionService) GetHistory(sessionID string, limit *int) ([]*session.Message, error) {
	if s.manager == nil {
		return nil, fmt.Errorf("session manager not available")
	}
	return s.manager.GetHistory(sessionID, limit)
}

// AddMessage 添加消息到会话
func (s *SessionService) AddMessage(sessionID, role, content string, metadata map[string]interface{}) error {
	if s.manager == nil {
		return fmt.Errorf("session manager not available")
	}
	return s.manager.AddMessage(sessionID, role, content, metadata)
}

// DeleteSession 删除会话
func (s *SessionService) DeleteSession(sessionID string) error {
	if s.manager == nil {
		return fmt.Errorf("session manager not available")
	}
	return s.manager.DeleteSession(sessionID)
}

// IsAvailable 检查会话服务是否可用
func (s *SessionService) IsAvailable() bool {
	return s.manager != nil
}

// FormatHistoryForRequest 格式化历史消息用于请求（优化上下文携带）
// 只保留最近 20 轮对话（40 条消息），只携带 role 和 content
func (s *SessionService) FormatHistoryForRequest(messages []*session.Message) []map[string]interface{} {
	maxHistoryMessages := 40
	startIdx := 0
	if len(messages) > maxHistoryMessages {
		startIdx = len(messages) - maxHistoryMessages
	}

	// 只携带必需字段：role 和 content（性价比最高）
	formatted := make([]map[string]interface{}, len(messages)-startIdx)
	for i, msg := range messages[startIdx:] {
		formatted[i] = map[string]interface{}{
			"role":    msg.Role,
			"content": msg.Content,
			// 不携带 timestamp 和 metadata，减少传输量
		}
	}
	return formatted
}

// ParseHistoryLimit 从查询参数解析历史消息限制
func (s *SessionService) ParseHistoryLimit(c *gin.Context) *int {
	limitStr := c.DefaultQuery("limit", "50")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 50
	}
	return &limit
}
