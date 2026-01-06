package api

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"go.uber.org/zap"

	"github.com/your-org/zero-gateway/internal/config"
	"github.com/your-org/zero-gateway/pkg/api"
	"github.com/your-org/zero-gateway/pkg/session"
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

	// Create HTTP client with timeout and TLS config
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: cfg.Python.InsecureSkipVerify, // For development
		},
		MaxIdleConns:        100,              // 最大空闲连接数
		MaxIdleConnsPerHost: 10,               // 每个host的最大空闲连接数
		IdleConnTimeout:     90 * time.Second, // 空闲连接超时
	}

	httpClient := &http.Client{
		Transport: transport,
		Timeout:   time.Duration(cfg.Python.Timeout) * time.Second,
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

	// Test Redis connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := redisClient.Ping(ctx).Result(); err != nil {
		logger.Error("Failed to connect to Redis", zap.Error(err))
		// Continue without session manager for now
		redisClient = nil
	}

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

// Chat handles chat requests
func (h *Handler) Chat(c *gin.Context) {
	var req api.ChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.logger.Error("Invalid chat request", zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request format"})
		return
	}

	h.logger.Info("Chat request",
		zap.String("session_id", req.SessionID),
		zap.String("message", req.Message[:min(100, len(req.Message))]))

	// Validate request
	if req.Message == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Message is required"})
		return
	}

	// Get full message history for context
	var messageHistory []map[string]interface{}
	if h.sessionManager != nil {
		messages, err := h.sessionManager.GetHistory(req.SessionID, nil)
		if err != nil {
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

	// Prepare request to Python service (no session dependency)
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
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to prepare request"})
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
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
		return
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// Call Python service with retry
	resp, err := h.callPythonWithRetry(httpReq, pythonURL, req.SessionID)
	if err != nil {
		h.logger.Error("Failed to call Python service after retries", zap.Error(err),
			zap.String("url", pythonURL), zap.String("session_id", req.SessionID))
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Agent service unavailable"})
		return
	}

	defer resp.Body.Close()

	// Read response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.logger.Error("Failed to read response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read response"})
		return
	}

	// Handle different status codes
	if resp.StatusCode != http.StatusOK {
		h.logger.Error("Python service error",
			zap.Int("status_code", resp.StatusCode),
			zap.String("response", string(body)))
		c.JSON(resp.StatusCode, gin.H{"error": "Agent service error"})
		return
	}

	// Parse response
	var response map[string]interface{}
	if err := json.Unmarshal(body, &response); err != nil {
		h.logger.Error("Failed to parse response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse response"})
		return
	}

	// Add assistant message to session
	if h.sessionManager != nil {
		if message, ok := response["message"].(string); ok {
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

	c.JSON(http.StatusOK, response)
}

// min helper function
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// CreateSession creates a new chat session
func (h *Handler) CreateSession(c *gin.Context) {
	var req api.CreateSessionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.logger.Error("Invalid session request", zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request format"})
		return
	}

	if h.sessionManager == nil {
		h.logger.Error("Session manager not available")
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Session service unavailable"})
		return
	}

	// Create session using local session manager (Go主导)
	session, err := h.sessionManager.CreateSession("demo-agent", req.Metadata)
	if err != nil {
		h.logger.Error("Failed to create session", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create session"})
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
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Session service unavailable"})
		return
	}

	// Get session history from local session manager
	messages, err := h.sessionManager.GetHistory(sessionID, &limit)
	if err != nil {
		h.logger.Error("Failed to get session history", zap.Error(err),
			zap.String("session_id", sessionID))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve history"})
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
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Session service unavailable"})
		return
	}

	// Delete session from Redis
	err := h.sessionManager.DeleteSession(sessionID)
	if err != nil {
		h.logger.Error("Failed to delete session", zap.Error(err),
			zap.String("session_id", sessionID))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to delete session"})
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
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
		return
	}

	// Call Python service
	resp, err := h.httpClient.Do(httpReq)
	if err != nil {
		h.logger.Error("Failed to call Python service", zap.Error(err),
			zap.String("url", pythonURL))
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Agent service unavailable"})
		return
	}
	defer resp.Body.Close()

	// Read and forward response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.logger.Error("Failed to read response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read response"})
		return
	}

	if resp.StatusCode != http.StatusOK {
		c.Data(resp.StatusCode, "application/json", body)
		return
	}

	var tools interface{}
	if err := json.Unmarshal(body, &tools); err != nil {
		h.logger.Error("Failed to parse response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse response"})
		return
	}

	c.JSON(http.StatusOK, tools)
}

// callPythonWithRetry calls Python service with exponential backoff retry
func (h *Handler) callPythonWithRetry(req *http.Request, url, sessionID string) (*http.Response, error) {
	const maxRetries = 3
	const baseDelay = 100 * time.Millisecond

	for attempt := 0; attempt < maxRetries; attempt++ {
		resp, err := h.httpClient.Do(req)
		if err == nil && resp.StatusCode < 500 {
			// Success or client error (4xx), don't retry
			return resp, nil
		}

		if err != nil {
			h.logger.Warn("Python service call failed, retrying",
				zap.Error(err), zap.Int("attempt", attempt+1), zap.String("session_id", sessionID))
		} else {
			resp.Body.Close() // Close body before retry
			h.logger.Warn("Python service returned server error, retrying",
				zap.Int("status_code", resp.StatusCode), zap.Int("attempt", attempt+1), zap.String("session_id", sessionID))
		}

		if attempt < maxRetries-1 {
			// Exponential backoff: baseDelay * 2^attempt
			delay := baseDelay * time.Duration(1<<uint(attempt))
			time.Sleep(delay)
		}
	}

	// Final attempt without retry
	return h.httpClient.Do(req)
}

// ChatStream handles streaming chat requests
func (h *Handler) ChatStream(c *gin.Context) {
	var req api.ChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		h.logger.Error("Invalid chat stream request", zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request format"})
		return
	}

	h.logger.Info("Chat stream request",
		zap.String("session_id", req.SessionID),
		zap.String("message", req.Message[:min(100, len(req.Message))]))

	// Validate request
	if req.Message == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Message is required"})
		return
	}

	// Get full message history for context
	var messageHistory []map[string]interface{}
	if h.sessionManager != nil {
		messages, err := h.sessionManager.GetHistory(req.SessionID, nil)
		if err != nil {
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

	// Prepare request to Python service (streaming endpoint)
	pythonURL := fmt.Sprintf("http://%s:%d/chat/stream",
		h.config.Python.Host, h.config.Python.Port)

	requestBody := map[string]interface{}{
		"message":         req.Message,
		"message_history": messageHistory,
		"metadata":        req.Metadata,
		"stream":          true, // 明确标记为流式请求
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		h.logger.Error("Failed to marshal request", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to prepare request"})
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
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
		return
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "text/plain") // 流式响应

	// Call Python service with streaming
	resp, err := h.callPythonWithRetry(httpReq, pythonURL, req.SessionID)
	if err != nil {
		h.logger.Error("Failed to call Python service after retries", zap.Error(err),
			zap.String("url", pythonURL), zap.String("session_id", req.SessionID))
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Agent service unavailable"})
		return
	}
	defer resp.Body.Close()

	// Handle different status codes
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		h.logger.Error("Python service error",
			zap.Int("status_code", resp.StatusCode),
			zap.String("response", string(body)))
		c.JSON(resp.StatusCode, gin.H{"error": "Agent service error"})
		return
	}

	// Set SSE headers
	c.Header("Content-Type", "text/plain")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Headers", "Cache-Control")

	// Stream response to client
	// Python service already returns SSE formatted data, just forward it
	buf := make([]byte, 4096)
	for {
		n, err := resp.Body.Read(buf)
		if n > 0 {
			// Forward the raw SSE data from Python service
			c.Writer.Write(buf[:n])
			c.Writer.Flush()
		}
		if err != nil {
			if err != io.EOF {
				h.logger.Error("Error reading stream", zap.Error(err))
			}
			break
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
