package business

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"zero-gateway/internal/infrastructure"
	"zero-gateway/pkg/session"
)

// SessionService 会话业务服务
type SessionService struct {
	sessionService *infrastructure.SessionService
	logger         *zap.Logger
}

// NewSessionService 创建会话业务服务
func NewSessionService(sessionService *infrastructure.SessionService, logger *zap.Logger) *SessionService {
	return &SessionService{
		sessionService: sessionService,
		logger:         logger,
	}
}

// CreateSession 创建新会话
func (s *SessionService) CreateSession(c *gin.Context) {
	var req infrastructure.CreateSessionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		s.logger.Error("Invalid session request", zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"error":      "Invalid request format",
			"error_code": infrastructure.ErrCodeInvalidRequest,
		})
		return
	}

	if !s.sessionService.IsAvailable() {
		s.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "Session service unavailable",
			"error_code": infrastructure.ErrCodeSessionServiceUnavailable,
		})
		return
	}

	// Create session using local session manager
	// 使用 "zero" 作为默认 agent_id，与 Python 端的 default_agent.yaml 配置保持一致
	agentID := "zero"
	s.logger.Debug("创建会话", zap.String("agent_id", agentID))
	sess, err := s.sessionService.CreateSession(agentID, req.Metadata)
	if err != nil {
		s.logger.Error("Failed to create session", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to create session",
			"error_code": infrastructure.ErrCodeSessionCreateError,
		})
		return
	}

	s.logger.Info("Session created", zap.String("session_id", sess.ID))

	c.JSON(http.StatusCreated, gin.H{
		"session_id": sess.ID,
		"agent_id":   sess.AgentID,
		"created_at": sess.CreatedAt.Format(time.RFC3339),
		"metadata":   sess.Metadata,
	})
}

// GetHistory 获取会话历史
func (s *SessionService) GetHistory(c *gin.Context) {
	sessionID := c.Param("session_id")

	if !s.sessionService.IsAvailable() {
		s.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "Session service unavailable",
			"error_code": infrastructure.ErrCodeSessionServiceUnavailable,
		})
		return
	}

	// Get session history from local session manager
	limit := s.sessionService.ParseHistoryLimit(c)
	messages, err := s.sessionService.GetHistory(sessionID, limit)
	if err != nil {
		// 检查是否为会话不存在错误
		if session.IsSessionNotFound(err) {
			s.logger.Warn("Session not found", zap.String("session_id", sessionID))
			c.JSON(http.StatusNotFound, gin.H{
				"error":      "Session not found",
				"error_code": infrastructure.ErrCodeSessionNotFound,
				"session_id": sessionID,
			})
			return
		}

		s.logger.Error("Failed to get session history", zap.Error(err),
			zap.String("session_id", sessionID))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to retrieve history",
			"error_code": infrastructure.ErrCodeSessionGetHistoryError,
		})
		return
	}

	// Format messages for response
	formattedMessages := make([]gin.H, len(messages))
	for i, msg := range messages {
		formattedMessages[i] = gin.H{
			"id":        msg.ID,
			"role":      msg.Role,
			"content":   msg.Content,
			"timestamp": msg.Timestamp.Format(time.RFC3339),
			"metadata":  msg.Metadata,
		}
	}

	s.logger.Info("Retrieved session history",
		zap.String("session_id", sessionID),
		zap.Int("message_count", len(messages)))

	c.JSON(http.StatusOK, gin.H{"messages": formattedMessages})
}

// ClearSession 清除会话
func (s *SessionService) ClearSession(c *gin.Context) {
	sessionID := c.Param("session_id")

	if !s.sessionService.IsAvailable() {
		s.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "Session service unavailable",
			"error_code": infrastructure.ErrCodeSessionServiceUnavailable,
		})
		return
	}

	// Delete session from Redis
	err := s.sessionService.DeleteSession(sessionID)
	if err != nil {
		s.logger.Error("Failed to delete session", zap.Error(err),
			zap.String("session_id", sessionID))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to delete session",
			"error_code": infrastructure.ErrCodeSessionDeleteError,
		})
		return
	}

	s.logger.Info("Session deleted successfully", zap.String("session_id", sessionID))

	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Session deleted"})
}
