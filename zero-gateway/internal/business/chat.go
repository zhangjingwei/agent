package business

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"zero-gateway/internal/infrastructure"
)

// ChatService 聊天业务服务
type ChatService struct {
	requestService *infrastructure.RequestService
	httpClient     *infrastructure.HTTPClient
	logger         *zap.Logger
}

// NewChatService 创建聊天服务
func NewChatService(requestService *infrastructure.RequestService, httpClient *infrastructure.HTTPClient, logger *zap.Logger) *ChatService {
	return &ChatService{
		requestService: requestService,
		httpClient:     httpClient,
		logger:         logger,
	}
}

// HandleChat 处理聊天请求（统一入口，根据 stream 参数路由）
func (s *ChatService) HandleChat(c *gin.Context, req *infrastructure.ChatRequest) {
	if req.Stream {
		s.HandleChatStream(c, req)
		return
	}
	s.HandleChatNonStream(c, req)
}

// HandleChatNonStream 处理非流式聊天请求
func (s *ChatService) HandleChatNonStream(c *gin.Context, req *infrastructure.ChatRequest) {
	// 准备请求（统一逻辑）
	messageHistory, agentID, err := s.requestService.PrepareChatRequest(req)
	if err != nil {
		// 会话不存在时返回404
		if err.Error() == "session not found" || fmt.Sprintf("%v", err) == "session not found" {
			c.JSON(http.StatusNotFound, gin.H{
				"error":      "Session not found",
				"error_code": infrastructure.ErrCodeSessionNotFound,
				"session_id": req.SessionID,
			})
			return
		}
		// 其他错误继续处理（可能只是临时性问题）
	}

	s.logger.Info("准备请求Python服务", zap.String("agent_id", agentID), zap.String("session_id", req.SessionID), zap.Int("history_count", len(messageHistory)))

	// 构建Python服务请求（统一逻辑）
	httpReq, pythonURL, err := s.requestService.BuildPythonRequest(c.Request.Context(), agentID, req, messageHistory, false)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      err.Error(),
			"error_code": infrastructure.ErrCodeRequestCreationError,
		})
		return
	}

	// 调用Python服务
	resp, err := s.httpClient.Do(httpReq)
	if err != nil {
		// 根据错误类型选择更具体的错误码
		var errorCode int
		if err.Error() == "context deadline exceeded" || err.Error() == "timeout" {
			errorCode = infrastructure.ErrCodeAgentRequestTimeout
		} else if err.Error() == "connection refused" || err.Error() == "no such host" {
			errorCode = infrastructure.ErrCodeAgentConnectionTimeout
		} else {
			errorCode = infrastructure.ErrCodeAgentServiceUnavailable
		}

		s.logger.Error("Failed to call Python service", zap.Error(err),
			zap.String("url", pythonURL), zap.String("session_id", req.SessionID))
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "service unavailable",
			"error_code": errorCode,
		})
		return
	}

	defer resp.Body.Close()

	// Read response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		s.logger.Error("Failed to read response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to read response",
			"error_code": infrastructure.ErrCodeResponseReadError,
		})
		return
	}

	// Handle different status codes
	if resp.StatusCode != http.StatusOK {
		var errorCode int
		switch resp.StatusCode {
		case http.StatusBadRequest:
			errorCode = infrastructure.ErrCodeInvalidRequest
		case http.StatusRequestTimeout:
			errorCode = infrastructure.ErrCodeAgentRequestTimeout
		case http.StatusServiceUnavailable:
			errorCode = infrastructure.ErrCodeAgentServiceUnavailable
		case http.StatusTooManyRequests:
			errorCode = infrastructure.ErrCodeAgentServiceBusy
		default:
			errorCode = infrastructure.ErrCodeAgentServiceError
		}

		s.logger.Error("Python service error",
			zap.Int("status_code", resp.StatusCode),
			zap.String("response", string(body)))
		c.JSON(resp.StatusCode, gin.H{
			"error":      "Agent service error",
			"error_code": errorCode,
		})
		return
	}

	// Parse response
	var response map[string]interface{}
	if err := json.Unmarshal(body, &response); err != nil {
		s.logger.Error("Failed to parse response", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      "Failed to parse response",
			"error_code": infrastructure.ErrCodeUnmarshalError,
		})
		return
	}

	// 规范化响应数据，确保格式正确
	normalizedResponse := s.requestService.NormalizeChatResponse(response)

	// Add assistant message to session
	if s.requestService.SessionService().IsAvailable() {
		if message, ok := normalizedResponse["message"].(string); ok {
			err = s.requestService.SessionService().AddMessage(req.SessionID, "assistant", message, nil)
			if err != nil {
				s.logger.Error("Failed to add assistant message to session", zap.Error(err),
					zap.String("session_id", req.SessionID))
				// Continue returning response even if session save fails
			}
		}
	}

	s.logger.Info("Chat completed",
		zap.String("session_id", req.SessionID),
		zap.String("user_message", req.Message[:min(50, len(req.Message))]))

	// 返回OpenAPI标准格式的成功响应
	// 返回成功响应
	c.JSON(http.StatusOK, gin.H{"data": normalizedResponse})
}

// HandleChatStream 处理流式聊天请求
func (s *ChatService) HandleChatStream(c *gin.Context, req *infrastructure.ChatRequest) {
	// 准备请求（统一逻辑）
	messageHistory, agentID, err := s.requestService.PrepareChatRequest(req)
	if err != nil {
		// 会话不存在时返回404
		if err.Error() == "session not found" || fmt.Sprintf("%v", err) == "session not found" {
			c.JSON(http.StatusNotFound, gin.H{
				"error":      "Session not found",
				"error_code": infrastructure.ErrCodeSessionNotFound,
				"session_id": req.SessionID,
			})
			return
		}
		// 其他错误继续处理（可能只是临时性问题）
	}

	s.logger.Info("准备请求Python服务 (流式)", zap.String("agent_id", agentID), zap.String("session_id", req.SessionID), zap.Int("history_count", len(messageHistory)))

	// 构建Python服务请求（统一逻辑）
	httpReq, pythonURL, err := s.requestService.BuildPythonRequest(c.Request.Context(), agentID, req, messageHistory, true)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":      err.Error(),
			"error_code": infrastructure.ErrCodeRequestCreationError,
		})
		return
	}

	// 对于流式响应，使用无超时的客户端
	streamClient := s.httpClient.NewStreamClient()

	// Call Python service with streaming
	requestStartTime := time.Now()
	resp, err := streamClient.Do(httpReq)
	requestDuration := time.Since(requestStartTime)

	if err != nil {
		// 根据错误类型选择更具体的错误码
		var errorCode int
		if err.Error() == "context deadline exceeded" || err.Error() == "timeout" {
			errorCode = infrastructure.ErrCodeAgentRequestTimeout
		} else if err.Error() == "connection refused" || err.Error() == "no such host" {
			errorCode = infrastructure.ErrCodeAgentConnectionTimeout
		} else {
			errorCode = infrastructure.ErrCodeAgentServiceUnavailable
		}

		s.logger.Error("Failed to call Python service for streaming",
			zap.Error(err),
			zap.String("url", pythonURL),
			zap.String("session_id", req.SessionID),
			zap.Duration("request_duration", requestDuration),
			zap.Int("error_code", errorCode))
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":      "service unavailable",
			"error_code": errorCode,
		})
		return
	}
	defer resp.Body.Close()

	s.logger.Info("Received response from Python service",
		zap.Int("status_code", resp.StatusCode),
		zap.String("session_id", req.SessionID),
		zap.Duration("request_duration", requestDuration),
		zap.String("content_type", resp.Header.Get("Content-Type")))

	// Handle different status codes
	if resp.StatusCode != http.StatusOK {
		var errorCode int
		switch resp.StatusCode {
		case http.StatusBadRequest:
			errorCode = infrastructure.ErrCodeInvalidRequest
		case http.StatusRequestTimeout:
			errorCode = infrastructure.ErrCodeAgentRequestTimeout
		case http.StatusServiceUnavailable:
			errorCode = infrastructure.ErrCodeAgentServiceUnavailable
		case http.StatusTooManyRequests:
			errorCode = infrastructure.ErrCodeAgentServiceBusy
		default:
			errorCode = infrastructure.ErrCodeAgentServiceError
		}

		body, _ := io.ReadAll(resp.Body)
		s.logger.Error("Python service error",
			zap.Int("status_code", resp.StatusCode),
			zap.String("response", string(body)))
		c.JSON(resp.StatusCode, gin.H{
			"error":      "Agent service error",
			"error_code": errorCode,
		})
		return
	}

	// Set SSE headers (必须在写入响应体之前设置)
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no") // 禁用Nginx缓冲
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Headers", "Cache-Control")

	s.logger.Info("Starting to stream response to client",
		zap.String("session_id", req.SessionID))

	// 立即刷新响应头，确保客户端知道这是流式响应
	c.Writer.Flush()

	// Stream response to client
	streamStartTime := time.Now()
	totalBytesRead := int64(0)
	chunkCount := 0
	buf := make([]byte, 4096)

	// 收集完整响应内容用于保存到会话历史
	var fullResponseContent strings.Builder
	collectingResponse := true

	// 使用 goroutine 来转发流数据，同时监听上下文取消
	done := make(chan error, 1)
	go func() {
		for {
			// 检查上下文是否已取消
			select {
			case <-c.Request.Context().Done():
				done <- c.Request.Context().Err()
				return
			default:
			}

			// 读取数据
			n, err := resp.Body.Read(buf)
			if n > 0 {
				totalBytesRead += int64(n)
				chunkCount++

				// 收集响应内容（解析 SSE 格式）
				if collectingResponse {
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
									collectingResponse = false
								}
							}
						}
					}
				}

				// 写入并立即刷新
				if _, writeErr := c.Writer.Write(buf[:n]); writeErr != nil {
					done <- writeErr
					return
				}
				c.Writer.Flush()

				// 每10个chunk记录一次详细信息
				if chunkCount%10 == 0 {
					s.logger.Info("Streaming progress",
						zap.String("session_id", req.SessionID),
						zap.Int64("total_bytes", totalBytesRead),
						zap.Int("chunk_count", chunkCount),
						zap.Duration("stream_duration", time.Since(streamStartTime)))
				} else {
					s.logger.Debug("Stream chunk written",
						zap.String("session_id", req.SessionID),
						zap.Int("bytes_written", n),
						zap.Int64("total_bytes", totalBytesRead),
						zap.Int("chunk_count", chunkCount))
				}
			}

			if err != nil {
				done <- err
				return
			}
		}
	}()

	// 等待复制完成或上下文取消
	select {
	case err := <-done:
		if err != nil && err != io.EOF {
			s.logger.Error("Error copying stream",
				zap.Error(err),
				zap.String("session_id", req.SessionID),
				zap.Int64("total_bytes", totalBytesRead),
				zap.Int("chunk_count", chunkCount),
				zap.Duration("stream_duration", time.Since(streamStartTime)))
		} else {
			s.logger.Info("Stream completed",
				zap.String("session_id", req.SessionID),
				zap.Int64("total_bytes", totalBytesRead),
				zap.Int("chunk_count", chunkCount),
				zap.Duration("stream_duration", time.Since(streamStartTime)))
		}
	case <-c.Request.Context().Done():
		s.logger.Warn("Client disconnected during streaming",
			zap.String("session_id", req.SessionID),
			zap.Int64("total_bytes", totalBytesRead),
			zap.Int("chunk_count", chunkCount),
			zap.Duration("stream_duration", time.Since(streamStartTime)))
		return
	}

	// Add assistant message to session after streaming completes
	if s.requestService.SessionService().IsAvailable() {
		// 保存收集到的完整响应内容
		responseContent := fullResponseContent.String()
		if responseContent == "" {
			// 如果未能解析出内容，使用占位符
			responseContent = "[Streaming response completed]"
		}
		err = s.requestService.SessionService().AddMessage(req.SessionID, "assistant", responseContent, nil)
		if err != nil {
			s.logger.Error("Failed to add assistant message to session", zap.Error(err),
				zap.String("session_id", req.SessionID))
		} else {
			s.logger.Debug("Saved assistant response to session",
				zap.String("session_id", req.SessionID),
				zap.Int("response_length", len(responseContent)))
		}
	}

	s.logger.Info("Chat stream completed",
		zap.String("session_id", req.SessionID),
		zap.String("user_message", req.Message[:min(50, len(req.Message))]))
}

// Helper function
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
