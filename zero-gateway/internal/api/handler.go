package api

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"go.uber.org/zap"
	"golang.org/x/net/http2"

	"zero-gateway/internal/config"
	"zero-gateway/pkg/session"
)

// Handler handles HTTP API requests
type Handler struct {
	config         *config.Config
	logger         *zap.Logger
	httpClient     *http.Client
	sessionManager *session.SessionManager
}

// NewHandler creates a new API handler
func NewHandler(cfg *config.Config, logger *zap.Logger) *Handler {

	// Create HTTP/2 client with timeout and TLS config
	// 设置连接超时为5秒（增加超时时间以支持更稳定的连接）
	connectionTimeout := 5 * time.Second
	transport := &http2.Transport{
		AllowHTTP: true, // 允许非加密连接（h2c - HTTP/2 over cleartext）
		DialTLS: func(network, addr string, cfg *tls.Config) (net.Conn, error) {
			// 对于 h2c，不使用 TLS，直接建立普通 TCP 连接
			dialer := &net.Dialer{
				Timeout:   connectionTimeout,
				KeepAlive: 30 * time.Second, // 保持连接活跃
			}
			// 使用 context.Background()，因为 DialTLS 不接收 context
			// 超时由 dialer.Timeout 控制
			return dialer.DialContext(context.Background(), network, addr)
		},
		MaxHeaderListSize: 262144, // 256KB - HTTP/2 最大头部列表大小
	}

	httpClient := &http.Client{
		Transport: transport,
		Timeout:   cfg.Python.Timeout,
	}

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

	return &Handler{
		config:         cfg,
		logger:         logger,
		httpClient:     httpClient,
		sessionManager: sessionManager,
	}
}

// Chat handles chat requests (unified endpoint for both streaming and non-streaming)
func (h *Handler) Chat(c *gin.Context) {
	var req ChatRequest

	// 绑定请求体
	if err := bindJSON(c, &req); err != nil {
		h.logger.Error("Invalid chat request", zap.Error(err))
		c.JSON(http.StatusBadRequest, NewErrorResponse(ErrCodeInvalidRequest, "Invalid request format"))
		return
	}

	// 验证请求体
	if req.Message == "" {
		c.JSON(http.StatusBadRequest, NewErrorResponse(ErrCodeMissingField, "Message is required"))
		return
	}

	// 根据stream字段决定使用流式或非流式响应
	// 注意：如果请求体中不包含stream字段，Go的JSON解析会将其设置为false（bool的零值）
	// 因此默认行为是非流式响应，确保向后兼容性
	if req.Stream {
		h.handleChatStream(c, &req)
		return
	}

	// 默认使用非流式响应（兼容没有stream字段的旧客户端）
	h.handleChatNonStream(c, &req)
}

// normalizeChatResponse 规范化聊天响应数据，确保格式符合OpenAPI标准
func (h *Handler) normalizeChatResponse(response map[string]interface{}) map[string]interface{} {
	normalized := make(map[string]interface{})

	// 复制所有字段
	for k, v := range response {
		normalized[k] = v
	}

	// 处理 usage 字段：如果为 null，设置为空对象
	if usage, exists := normalized["usage"]; !exists || usage == nil {
		normalized["usage"] = map[string]interface{}{
			"prompt_tokens":     0,
			"completion_tokens": 0,
			"total_tokens":      0,
		}
	} else if usageMap, ok := usage.(map[string]interface{}); ok {
		// 确保 usage 对象包含所有必需字段
		normalizedUsage := map[string]interface{}{
			"prompt_tokens":     0,
			"completion_tokens": 0,
			"total_tokens":      0,
		}
		if promptTokens, ok := usageMap["prompt_tokens"]; ok {
			normalizedUsage["prompt_tokens"] = promptTokens
		}
		if completionTokens, ok := usageMap["completion_tokens"]; ok {
			normalizedUsage["completion_tokens"] = completionTokens
		}
		if totalTokens, ok := usageMap["total_tokens"]; ok {
			normalizedUsage["total_tokens"] = totalTokens
		}
		normalized["usage"] = normalizedUsage
	}

	// 处理 tool_calls 字段：确保是数组而不是 null
	if toolCalls, exists := normalized["tool_calls"]; !exists || toolCalls == nil {
		normalized["tool_calls"] = []interface{}{}
	} else {
		// 确保是数组类型
		switch v := toolCalls.(type) {
		case []interface{}:
			// 已经是数组，保持不变
			normalized["tool_calls"] = v
		case []map[string]interface{}:
			// 如果是 []map[string]interface{}，转换为 []interface{}
			result := make([]interface{}, len(v))
			for i, item := range v {
				result[i] = item
			}
			normalized["tool_calls"] = result
		default:
			// 其他类型，转换为空数组
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

// handleChatNonStream handles non-streaming chat requests
func (h *Handler) handleChatNonStream(c *gin.Context, req *ChatRequest) {

	// 获取会话历史
	var messageHistory []map[string]interface{}
	if h.sessionManager != nil {
		messages, err := h.sessionManager.GetHistory(req.SessionID, nil)
		// 如果获取会话历史失败，返回错误
		if err != nil {
			// 如果会话不存在，返回错误
			if session.IsSessionNotFound(err) {
				h.logger.Warn("Session not found for chat", zap.String("session_id", req.SessionID))
				errorResp := NewErrorResponseWithDetails(ErrCodeSessionNotFound, "Session not found", map[string]interface{}{
					"session_id": req.SessionID,
				})
				c.JSON(http.StatusNotFound, errorResp)
				return
			}
			h.logger.Error("Failed to get message history", zap.Error(err),
				zap.String("session_id", req.SessionID))
			c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeSessionGetHistoryError, "Failed to get message history"))
			return
		}

		// 格式化消息
		messageHistory = make([]map[string]interface{}, len(messages))
		for i, msg := range messages {
			messageHistory[i] = map[string]interface{}{
				"role":      msg.Role,
				"content":   msg.Content,
				"timestamp": msg.Timestamp.Format(time.RFC3339),
			}
		}

		// 添加当前用户消息到会话
		err = h.sessionManager.AddMessage(req.SessionID, "user", req.Message, req.Metadata)
		if err != nil {
			h.logger.Error("Failed to add user message to session", zap.Error(err),
				zap.String("session_id", req.SessionID))
			c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeSessionAddMessageError, "Failed to add message to session"))
			return
		}
	}

	// 准备请求到Python服务（无会话依赖）
	pythonURL := fmt.Sprintf("http://%s:%d/chat",
		h.config.Python.Host, h.config.Python.Port)

	requestBody := map[string]interface{}{
		"message":         req.Message,
		"message_history": messageHistory,
		"metadata":        req.Metadata,
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		h.logger.Error("Failed to marshal request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeMarshalError, "Failed to prepare request"))
		return
	}

	// 创建HTTP请求
	httpReq, err := http.NewRequestWithContext(
		c.Request.Context(),
		"POST",
		pythonURL,
		bytes.NewBuffer(jsonData),
	)
	if err != nil {
		h.logger.Error("Failed to create HTTP request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeRequestCreationError, "Failed to create request"))
		return
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// 调用Python服务
	resp, err := h.httpClient.Do(httpReq)
	if err != nil {
		// 根据错误类型选择更具体的错误码
		var errorCode int
		if err.Error() == "context deadline exceeded" || err.Error() == "timeout" {
			errorCode = ErrCodeAgentRequestTimeout
		} else if err.Error() == "connection refused" || err.Error() == "no such host" {
			errorCode = ErrCodeAgentConnectionTimeout
		} else {
			errorCode = ErrCodeAgentServiceUnavailable
		}

		h.logger.Error("Failed to call Python service", zap.Error(err),
			zap.String("url", pythonURL), zap.String("session_id", req.SessionID))
		c.JSON(http.StatusServiceUnavailable, NewErrorResponse(errorCode, "service unavailable"))
		return
	}

	defer resp.Body.Close()

	// Read response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.logger.Error("Failed to read response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeResponseReadError, "Failed to read response"))
		return
	}

	// Handle different status codes
	if resp.StatusCode != http.StatusOK {
		var errorCode int
		switch resp.StatusCode {
		case http.StatusBadRequest:
			errorCode = ErrCodeInvalidRequest
		case http.StatusRequestTimeout:
			errorCode = ErrCodeAgentRequestTimeout
		case http.StatusServiceUnavailable:
			errorCode = ErrCodeAgentServiceUnavailable
		case http.StatusTooManyRequests:
			errorCode = ErrCodeAgentServiceBusy
		default:
			errorCode = ErrCodeAgentServiceError
		}

		h.logger.Error("Python service error",
			zap.Int("status_code", resp.StatusCode),
			zap.String("response", string(body)))
		c.JSON(resp.StatusCode, NewErrorResponse(errorCode, "Agent service error"))
		return
	}

	// Parse response
	var response map[string]interface{}
	if err := json.Unmarshal(body, &response); err != nil {
		h.logger.Error("Failed to parse response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeUnmarshalError, "Failed to parse response"))
		return
	}

	// 规范化响应数据，确保格式正确
	normalizedResponse := h.normalizeChatResponse(response)

	// Add assistant message to session
	if h.sessionManager != nil {
		if message, ok := normalizedResponse["message"].(string); ok {
			err = h.sessionManager.AddMessage(req.SessionID, "assistant", message, nil)
			if err != nil {
				h.logger.Error("Failed to add assistant message to session", zap.Error(err),
					zap.String("session_id", req.SessionID))
				// Continue returning response even if session save fails
			}
		}
	}

	h.logger.Info("Chat completed",
		zap.String("session_id", req.SessionID),
		zap.String("user_message", req.Message[:min(50, len(req.Message))]))

	// 返回OpenAPI标准格式的成功响应
	successResp := NewSuccessResponse(normalizedResponse)
	c.JSON(http.StatusOK, successResp)
}

// handleChatStream handles streaming chat requests
func (h *Handler) handleChatStream(c *gin.Context, req *ChatRequest) {
	// Get full message history for context
	var messageHistory []map[string]interface{}
	if h.sessionManager != nil {
		messages, err := h.sessionManager.GetHistory(req.SessionID, nil)
		if err != nil {
			// 如果会话不存在，返回错误
			if session.IsSessionNotFound(err) {
				h.logger.Warn("Session not found for chat", zap.String("session_id", req.SessionID))
				errorResp := NewErrorResponseWithDetails(ErrCodeSessionNotFound, "Session not found", map[string]interface{}{
					"session_id": req.SessionID,
				})
				c.JSON(http.StatusNotFound, errorResp)
				return
			}
			// 其他错误，记录警告但继续处理（可能只是临时性问题）
			h.logger.Warn("Failed to get message history, proceeding without context", zap.Error(err),
				zap.String("session_id", req.SessionID))
		} else {
			// Format messages for Python service
			messageHistory = make([]map[string]interface{}, len(messages))
			for i, msg := range messages {
				messageHistory[i] = map[string]interface{}{
					"role":      msg.Role,
					"content":   msg.Content,
					"timestamp": msg.Timestamp.Format(time.RFC3339),
					"metadata":  msg.Metadata,
				}
			}
		}

		// Add current user message to session
		err = h.sessionManager.AddMessage(req.SessionID, "user", req.Message, req.Metadata)
		if err != nil {
			h.logger.Error("Failed to add user message to session", zap.Error(err),
				zap.String("session_id", req.SessionID))
			// Continue processing even if session save fails
		}
	}

	h.logger.Info("Chat stream request started",
		zap.String("session_id", req.SessionID),
		zap.String("message", req.Message[:min(100, len(req.Message))]),
		zap.Int("message_history_count", len(messageHistory)))

	// Prepare request to Python service (streaming endpoint)
	pythonURL := fmt.Sprintf("http://%s:%d/chat/stream",
		h.config.Python.Host, h.config.Python.Port)

	h.logger.Debug("Preparing streaming request",
		zap.String("url", pythonURL),
		zap.String("session_id", req.SessionID))

	requestBody := map[string]interface{}{
		"message":         req.Message,
		"message_history": messageHistory,
		"metadata":        req.Metadata,
		"stream":          true, // 明确标记为流式请求
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		h.logger.Error("Failed to marshal request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeMarshalError, "Failed to prepare request"))
		return
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(
		c.Request.Context(),
		"POST",
		pythonURL,
		bytes.NewBuffer(jsonData),
	)
	if err != nil {
		h.logger.Error("Failed to create HTTP request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeRequestCreationError, "Failed to create request"))
		return
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "text/event-stream") // 流式响应，使用SSE标准

	h.logger.Debug("Sending streaming request to Python service",
		zap.String("url", pythonURL),
		zap.String("session_id", req.SessionID))

	// 对于流式响应，使用无超时的客户端（或很长的超时）
	// 因为流式响应可能需要很长时间
	streamClient := &http.Client{
		Transport: h.httpClient.Transport,
		Timeout:   0, // 无超时，让流式响应可以持续进行
	}

	// Call Python service with streaming
	requestStartTime := time.Now()
	resp, err := streamClient.Do(httpReq)
	requestDuration := time.Since(requestStartTime)

	if err != nil {
		// 根据错误类型选择更具体的错误码
		var errorCode int
		if err.Error() == "context deadline exceeded" || err.Error() == "timeout" {
			errorCode = ErrCodeAgentRequestTimeout
		} else if err.Error() == "connection refused" || err.Error() == "no such host" {
			errorCode = ErrCodeAgentConnectionTimeout
		} else {
			errorCode = ErrCodeAgentServiceUnavailable
		}

		h.logger.Error("Failed to call Python service for streaming",
			zap.Error(err),
			zap.String("url", pythonURL),
			zap.String("session_id", req.SessionID),
			zap.Duration("request_duration", requestDuration),
			zap.Int("error_code", errorCode))
		c.JSON(http.StatusServiceUnavailable, NewErrorResponse(errorCode, "service unavailable"))
		return
	}
	defer resp.Body.Close()

	h.logger.Info("Received response from Python service",
		zap.Int("status_code", resp.StatusCode),
		zap.String("session_id", req.SessionID),
		zap.Duration("request_duration", requestDuration),
		zap.String("content_type", resp.Header.Get("Content-Type")))

	// Handle different status codes
	if resp.StatusCode != http.StatusOK {
		var errorCode int
		switch resp.StatusCode {
		case http.StatusBadRequest:
			errorCode = ErrCodeInvalidRequest
		case http.StatusRequestTimeout:
			errorCode = ErrCodeAgentRequestTimeout
		case http.StatusServiceUnavailable:
			errorCode = ErrCodeAgentServiceUnavailable
		case http.StatusTooManyRequests:
			errorCode = ErrCodeAgentServiceBusy
		default:
			errorCode = ErrCodeAgentServiceError
		}

		body, _ := io.ReadAll(resp.Body)
		h.logger.Error("Python service error",
			zap.Int("status_code", resp.StatusCode),
			zap.String("response", string(body)))
		c.JSON(resp.StatusCode, NewErrorResponse(errorCode, "Agent service error"))
		return
	}

	// Set SSE headers (必须在写入响应体之前设置)
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no") // 禁用Nginx缓冲
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Headers", "Cache-Control")

	h.logger.Info("Starting to stream response to client",
		zap.String("session_id", req.SessionID))

	// 立即刷新响应头，确保客户端知道这是流式响应
	c.Writer.Flush()

	// Stream response to client
	// Python service already returns SSE formatted data, just forward it
	buf := make([]byte, 4096)
	totalBytesRead := 0
	chunkCount := 0
	streamStartTime := time.Now()

	for {
		// 检查客户端连接是否已关闭
		select {
		case <-c.Request.Context().Done():
			h.logger.Warn("Client disconnected during streaming",
				zap.String("session_id", req.SessionID),
				zap.Int("total_bytes", totalBytesRead),
				zap.Int("chunk_count", chunkCount),
				zap.Duration("stream_duration", time.Since(streamStartTime)))
			return
		default:
		}

		readStartTime := time.Now()
		n, err := resp.Body.Read(buf)
		readDuration := time.Since(readStartTime)

		if n > 0 {
			totalBytesRead += n
			chunkCount++

			h.logger.Debug("Read chunk from Python service",
				zap.Int("bytes_read", n),
				zap.Int("total_bytes", totalBytesRead),
				zap.Int("chunk_count", chunkCount),
				zap.Duration("read_duration", readDuration),
				zap.String("session_id", req.SessionID))

			// Forward the raw SSE data from Python service
			writeStartTime := time.Now()
			if _, writeErr := c.Writer.Write(buf[:n]); writeErr != nil {
				h.logger.Error("Error writing stream to client",
					zap.Error(writeErr),
					zap.String("session_id", req.SessionID),
					zap.Int("bytes_written", n))
				return
			}
			writeDuration := time.Since(writeStartTime)

			// 立即刷新，确保数据及时发送到客户端
			flushStartTime := time.Now()
			c.Writer.Flush()
			flushDuration := time.Since(flushStartTime)

			if chunkCount%10 == 0 { // 每10个chunk记录一次详细信息
				h.logger.Info("Streaming progress",
					zap.String("session_id", req.SessionID),
					zap.Int("total_bytes", totalBytesRead),
					zap.Int("chunk_count", chunkCount),
					zap.Duration("stream_duration", time.Since(streamStartTime)),
					zap.Duration("last_read_duration", readDuration),
					zap.Duration("last_write_duration", writeDuration),
					zap.Duration("last_flush_duration", flushDuration))
			}
		}

		if err != nil {
			if err == io.EOF {
				h.logger.Info("Stream completed (EOF)",
					zap.String("session_id", req.SessionID),
					zap.Int("total_bytes", totalBytesRead),
					zap.Int("chunk_count", chunkCount),
					zap.Duration("stream_duration", time.Since(streamStartTime)))
			} else {
				h.logger.Error("Error reading stream",
					zap.Error(err),
					zap.String("session_id", req.SessionID),
					zap.Int("total_bytes", totalBytesRead),
					zap.Int("chunk_count", chunkCount),
					zap.Duration("stream_duration", time.Since(streamStartTime)))
			}
			break
		}

		// 如果读取超时（超过5秒没有数据），记录警告
		if readDuration > 5*time.Second {
			h.logger.Warn("Long read duration detected",
				zap.Duration("read_duration", readDuration),
				zap.String("session_id", req.SessionID))
		}
	}

	// Add assistant message to session after streaming completes
	if h.sessionManager != nil {
		// Note: In a real implementation, you might want to collect the full response
		// and store it. For now, we'll store a placeholder.
		err = h.sessionManager.AddMessage(req.SessionID, "assistant", "[Streaming response completed]", nil)
		if err != nil {
			h.logger.Error("Failed to add assistant message to session", zap.Error(err),
				zap.String("session_id", req.SessionID))
		}
	}

	h.logger.Info("Chat stream completed",
		zap.String("session_id", req.SessionID),
		zap.String("user_message", req.Message[:min(50, len(req.Message))]))
}

// CreateSession creates a new chat session
func (h *Handler) CreateSession(c *gin.Context) {
	var req CreateSessionRequest
	if err := bindJSON(c, &req); err != nil {
		h.logger.Error("Invalid session request", zap.Error(err))
		c.JSON(http.StatusBadRequest, NewErrorResponse(ErrCodeInvalidRequest, "Invalid request format"))
		return
	}

	if h.sessionManager == nil {
		h.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, NewErrorResponse(ErrCodeSessionServiceUnavailable, "Session service unavailable"))
		return
	}

	// Create session using local session manager
	agentID := "zero-agent"
	session, err := h.sessionManager.CreateSession(agentID, req.Metadata)
	if err != nil {
		h.logger.Error("Failed to create session", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeSessionCreateError, "Failed to create session"))
		return
	}

	h.logger.Info("Session created", zap.String("session_id", session.ID))

	c.JSON(http.StatusCreated, gin.H{
		"session_id": session.ID,
		"agent_id":   session.AgentID,
		"created_at": session.CreatedAt.Format(time.RFC3339),
		"metadata":   session.Metadata,
	})
}

// GetHistory retrieves chat history for a session
func (h *Handler) GetHistory(c *gin.Context) {
	sessionID := c.Param("session_id")
	limitStr := c.DefaultQuery("limit", "50")

	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 50
	}

	if h.sessionManager == nil {
		h.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, NewErrorResponse(ErrCodeSessionServiceUnavailable, "Session service unavailable"))
		return
	}

	// Get session history from local session manager
	messages, err := h.sessionManager.GetHistory(sessionID, &limit)
	if err != nil {
		// 检查是否为会话不存在错误
		if session.IsSessionNotFound(err) {
			h.logger.Warn("Session not found", zap.String("session_id", sessionID))
			c.JSON(http.StatusNotFound, gin.H{
				"error":      "Session not found",
				"error_code": ErrCodeSessionNotFound,
				"session_id": sessionID,
			})
			return
		}

		h.logger.Error("Failed to get session history", zap.Error(err),
			zap.String("session_id", sessionID))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeSessionGetHistoryError, "Failed to retrieve history"))
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

	h.logger.Info("Retrieved session history",
		zap.String("session_id", sessionID),
		zap.Int("message_count", len(messages)))

	c.JSON(http.StatusOK, gin.H{"messages": formattedMessages})
}

// ClearSession clears a chat session
func (h *Handler) ClearSession(c *gin.Context) {
	sessionID := c.Param("session_id")

	if h.sessionManager == nil {
		h.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, NewErrorResponse(ErrCodeSessionServiceUnavailable, "Session service unavailable"))
		return
	}

	// Delete session from Redis
	err := h.sessionManager.DeleteSession(sessionID)
	if err != nil {
		h.logger.Error("Failed to delete session", zap.Error(err),
			zap.String("session_id", sessionID))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeSessionDeleteError, "Failed to delete session"))
		return
	}

	h.logger.Info("Session deleted successfully", zap.String("session_id", sessionID))

	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Session deleted"})
}

// ListTools lists available tools
func (h *Handler) ListTools(c *gin.Context) {
	// Prepare request to Python service
	pythonURL := fmt.Sprintf("http://%s:%d/tools",
		h.config.Python.Host, h.config.Python.Port)

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(
		c.Request.Context(),
		"GET",
		pythonURL,
		nil,
	)
	if err != nil {
		h.logger.Error("Failed to create HTTP request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeRequestCreationError, "Failed to create request"))
		return
	}

	// Call Python service
	resp, err := h.httpClient.Do(httpReq)
	if err != nil {
		h.logger.Error("Failed to call Python service", zap.Error(err),
			zap.String("url", pythonURL))
		c.JSON(http.StatusServiceUnavailable, NewErrorResponse(ErrCodeAgentServiceUnavailable, "service unavailable"))
		return
	}
	defer resp.Body.Close()

	// Read and forward response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.logger.Error("Failed to read response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeResponseReadError, "Failed to read response"))
		return
	}

	if resp.StatusCode != http.StatusOK {
		c.Data(resp.StatusCode, "application/json", body)
		return
	}

	var tools interface{}
	if err := json.Unmarshal(body, &tools); err != nil {
		h.logger.Error("Failed to parse response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, NewErrorResponse(ErrCodeUnmarshalError, "Failed to parse response"))
		return
	}

	c.JSON(http.StatusOK, tools)
}
