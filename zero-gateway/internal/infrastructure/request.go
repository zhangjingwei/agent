package infrastructure

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"go.uber.org/zap"

	"zero-gateway/internal/config"
	"zero-gateway/pkg/session"
)

// ChatRequest 聊天请求
type ChatRequest struct {
	SessionID string
	Message   string
	Stream    bool
	Metadata  map[string]interface{}
}

// CreateSessionRequest 创建会话请求
type CreateSessionRequest struct {
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// RequestService 请求处理服务（基础设施层）
type RequestService struct {
	httpClient     *HTTPClient
	sessionService *SessionService
	logger         *zap.Logger
	config         *config.Config
}

// NewRequestService 创建请求服务
func NewRequestService(httpClient *HTTPClient, sessionService *SessionService, cfg *config.Config, logger *zap.Logger) *RequestService {
	return &RequestService{
		httpClient:     httpClient,
		sessionService: sessionService,
		logger:         logger,
		config:         cfg,
	}
}

// SessionService 提供 SessionService 访问
func (r *RequestService) SessionService() *SessionService {
	return r.sessionService
}

// PrepareChatRequest 准备聊天请求的公共逻辑（统一流式和非流式）
// 返回：messageHistory, agentID, error
func (r *RequestService) PrepareChatRequest(req *ChatRequest) ([]map[string]interface{}, string, error) {
	// 获取会话历史
	var messageHistory []map[string]interface{}
	if r.sessionService.IsAvailable() && req.SessionID != "" {
		messages, err := r.sessionService.GetHistory(req.SessionID, nil)
		if err != nil {
			// 如果会话不存在，记录警告但继续处理（使用空历史）
			if session.IsSessionNotFound(err) {
				r.logger.Debug("Session not found, proceeding without history", zap.String("session_id", req.SessionID))
			} else {
				// 其他错误，记录但继续处理（可能只是临时性问题）
				r.logger.Warn("Failed to get message history, proceeding without context", zap.Error(err),
					zap.String("session_id", req.SessionID))
			}
		} else {
			// 格式化消息历史
			messageHistory = r.sessionService.FormatHistoryForRequest(messages)
			if len(messages) > 40 {
				r.logger.Debug("Limiting message history",
					zap.String("session_id", req.SessionID),
					zap.Int("total_messages", len(messages)),
					zap.Int("kept_messages", 40))
			}
		}

		// 添加当前用户消息到会话（统一处理，失败时记录警告但继续）
		if req.SessionID != "" {
			if err := r.sessionService.AddMessage(req.SessionID, "user", req.Message, req.Metadata); err != nil {
				r.logger.Debug("Failed to add user message to session (session may not exist)", zap.Error(err),
					zap.String("session_id", req.SessionID))
				// 继续处理，不中断请求
			}
		}
	}

	// 获取 agent_id（从会话或使用默认值）
	agentID := "zero" // 默认 agent_id，与 Python 端配置一致
	if r.sessionService.IsAvailable() {
		session, err := r.sessionService.GetSession(req.SessionID)
		if err == nil && session != nil && session.AgentID != "" {
			agentID = session.AgentID
			r.logger.Info("从会话获取 agent_id", zap.String("agent_id", agentID), zap.String("session_id", req.SessionID))
		} else {
			// 会话不存在时，仍然使用默认 agent_id，不返回错误
			r.logger.Info("会话不存在或未找到 agent_id，使用默认值", zap.String("session_id", req.SessionID), zap.String("default_agent_id", agentID), zap.Error(err))
		}
	} else {
		r.logger.Info("会话管理器未初始化，使用默认 agent_id", zap.String("default_agent_id", agentID))
	}

	// 确保 agentID 不为空
	if agentID == "" {
		agentID = "zero"
		r.logger.Warn("agent_id 为空，使用默认值", zap.String("default_agent_id", agentID))
	}

	return messageHistory, agentID, nil
}

// BuildPythonRequest 构建Python服务请求（统一流式和非流式）
func (r *RequestService) BuildPythonRequest(ctx context.Context, agentID string, req *ChatRequest, messageHistory []map[string]interface{}, stream bool) (*http.Request, string, error) {
	// 构建URL
	streamParam := "false"
	if stream {
		streamParam = "true"
	}
	path := fmt.Sprintf("/agents/%s/chat?stream=%s", agentID, streamParam)
	pythonURL, err := r.httpClient.BuildURL(path)
	if err != nil {
		return nil, "", fmt.Errorf("failed to build URL: %w", err)
	}

	// 构建请求体
	requestBody := map[string]interface{}{
		"message":         req.Message,
		"session_id":      req.SessionID, // 必需字段，Python API 要求
		"message_history": messageHistory,
		"metadata":        req.Metadata,
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		r.logger.Error("Failed to marshal request", zap.Error(err))
		return nil, "", fmt.Errorf("failed to marshal request: %w", err)
	}

	// 创建HTTP请求
	httpReq, err := http.NewRequestWithContext(ctx, "POST", pythonURL, bytes.NewBuffer(jsonData))
	if err != nil {
		r.logger.Error("Failed to create HTTP request", zap.Error(err))
		return nil, "", fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if stream {
		httpReq.Header.Set("Accept", "text/event-stream") // 流式响应，使用SSE标准
	}

	return httpReq, pythonURL, nil
}

// NormalizeChatResponse 规范化聊天响应数据，确保格式符合OpenAPI标准
func (r *RequestService) NormalizeChatResponse(response map[string]interface{}) map[string]interface{} {
	normalized := make(map[string]interface{})
	for k, v := range response {
		normalized[k] = v
	}

	// 确保 tool_calls 是数组类型
	if toolCalls, exists := normalized["tool_calls"]; exists {
		if toolCalls == nil {
			normalized["tool_calls"] = []interface{}{}
		}
	}

	// 确保 processing_time 是数字类型
	if processingTime, exists := normalized["processing_time"]; exists {
		if processingTime == nil {
			normalized["processing_time"] = 0.0
		}
	} else {
		normalized["processing_time"] = 0.0
	}

	// 确保 message 字段存在且为字符串
	if message, exists := normalized["message"]; !exists || message == nil {
		normalized["message"] = ""
	}

	return normalized
}

// CollectStreamResponse 从流式响应中收集完整内容
func (r *RequestService) CollectStreamResponse(body io.Reader) (string, error) {
	var fullResponseContent strings.Builder
	buf := make([]byte, 4096)

	for {
		n, err := body.Read(buf)
		if n > 0 {
			chunk := string(buf[:n])
			// 解析 SSE 格式: "data: {...}\n\n"
			lines := strings.Split(chunk, "\n")
			for _, line := range lines {
				if strings.HasPrefix(line, "data: ") {
					data := strings.TrimPrefix(line, "data: ")
					// 尝试解析 JSON 提取 message 字段
					var jsonData map[string]interface{}
					if err := json.Unmarshal([]byte(data), &jsonData); err == nil {
						if msg, ok := jsonData["message"].(string); ok && msg != "" {
							fullResponseContent.WriteString(msg)
						}
						// 如果遇到 done 标记，停止收集
						if done, ok := jsonData["done"].(bool); ok && done {
							return fullResponseContent.String(), nil
						}
					}
				}
			}
		}

		if err != nil {
			if err == io.EOF {
				return fullResponseContent.String(), nil
			}
			return fullResponseContent.String(), err
		}
	}
}
