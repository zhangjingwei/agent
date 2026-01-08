package business

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"zero-gateway/internal/infrastructure"
)

// ToolService 工具业务服务
type ToolService struct {
	httpClient *infrastructure.HTTPClient
	config     *infrastructure.RequestService
	logger     *zap.Logger
}

// NewToolService 创建工具服务
func NewToolService(httpClient *infrastructure.HTTPClient, requestService *infrastructure.RequestService, logger *zap.Logger) *ToolService {
	return &ToolService{
		httpClient: httpClient,
		config:     requestService,
		logger:     logger,
	}
}

// ListTools 列出可用工具
func (s *ToolService) ListTools(c *gin.Context) {
	// 从查询参数获取 agent_id，如果没有则使用默认值
	// 默认 agent_id 与 Python 端的 default_agent.yaml 中的 id 保持一致
	agentID := c.DefaultQuery("agent_id", "zero")
	s.logger.Debug("列出工具", zap.String("agent_id", agentID))

	// Prepare request to Python service
	pythonURL, err := s.httpClient.BuildURL(fmt.Sprintf("/agents/%s/tools", agentID))
	if err != nil {
		s.logger.Error("Failed to build Python service URL", zap.Error(err))
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "service unavailable",
			"error_code": infrastructure.ErrCodeAgentServiceUnavailable,
		})
		return
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(
		c.Request.Context(),
		"GET",
		pythonURL,
		nil,
	)
	if err != nil {
		s.logger.Error("Failed to create HTTP request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to create request",
			"error_code": infrastructure.ErrCodeRequestCreationError,
		})
		return
	}

	// Call Python service
	resp, err := s.httpClient.Do(httpReq)
	if err != nil {
		s.logger.Error("Failed to call Python service", zap.Error(err),
			zap.String("url", pythonURL))
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "service unavailable",
			"error_code": infrastructure.ErrCodeAgentServiceUnavailable,
		})
		return
	}
	defer resp.Body.Close()

	// Read and forward response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		s.logger.Error("Failed to read response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to read response",
			"error_code": infrastructure.ErrCodeResponseReadError,
		})
		return
	}

	if resp.StatusCode != http.StatusOK {
		var errorCode int
		switch resp.StatusCode {
		case http.StatusBadRequest:
			errorCode = infrastructure.ErrCodeInvalidRequest
		case http.StatusNotFound:
			errorCode = infrastructure.ErrCodeAgentServiceError // Agent not found
		case http.StatusServiceUnavailable:
			errorCode = infrastructure.ErrCodeAgentServiceUnavailable
		default:
			errorCode = infrastructure.ErrCodeAgentServiceError
		}

		s.logger.Error("Python service error", zap.Int("status_code", resp.StatusCode), zap.Int("error_code", errorCode))
		c.JSON(resp.StatusCode, gin.H{
			"error":      "Agent service error",
			"error_code": errorCode,
		})
		return
	}

	var tools interface{}
	if err := json.Unmarshal(body, &tools); err != nil {
		s.logger.Error("Failed to parse response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to parse response",
			"error_code": infrastructure.ErrCodeUnmarshalError,
		})
		return
	}

	c.JSON(http.StatusOK, tools)
}
