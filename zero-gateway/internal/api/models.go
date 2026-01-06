package api

import (
	"time"
)

// ChatRequest represents a chat request
type ChatRequest struct {
	SessionID string                 `json:"session_id" binding:"required"`
	Message   string                 `json:"message" binding:"required"`
	Stream    bool                   `json:"stream,omitempty"` // 是否使用流式响应，默认为false（兼容：如果请求中没有此字段，默认为false）
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// CreateSessionRequest represents a session creation request
type CreateSessionRequest struct {
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// ChatResponse represents a chat response
type ChatResponse struct {
	Message        string     `json:"message"`
	ToolCalls      []ToolCall `json:"tool_calls,omitempty"`
	Usage          Usage      `json:"usage"`
	ProcessingTime float64    `json:"processing_time"`
}

// ToolCall represents a tool call in the response
type ToolCall struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	Arguments     map[string]interface{} `json:"arguments"`
	Result        interface{}            `json:"result,omitempty"`
	Error         string                 `json:"error,omitempty"`
	ExecutionTime float64                `json:"execution_time,omitempty"`
}

// Usage represents token usage information
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// Session represents a chat session
type Session struct {
	ID        string                 `json:"id"`
	AgentID   string                 `json:"agent_id"`
	CreatedAt time.Time              `json:"created_at"`
	UpdatedAt time.Time              `json:"updated_at"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// Message represents a chat message
type Message struct {
	ID        string                 `json:"id"`
	Role      string                 `json:"role"`
	Content   string                 `json:"content"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// Tool represents an available tool
type Tool struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  map[string]interface{} `json:"parameters,omitempty"`
}

// ErrorResponse represents an error response (OpenAPI standard format)
type ErrorResponse struct {
	Error struct {
		Code    string                 `json:"code"`              // 错误码（字符串，如 "INVALID_REQUEST"）
		Message string                 `json:"message"`           // 错误消息
		Details map[string]interface{} `json:"details,omitempty"` // 错误详情
	} `json:"error"`
	ErrorCode int `json:"error_code,omitempty"` // 向后兼容：数值错误码
}

// SuccessResponse represents a successful response (OpenAPI standard format)
type SuccessResponse struct {
	Data interface{}            `json:"data"`           // 响应数据
	Meta map[string]interface{} `json:"meta,omitempty"` // 元数据（如分页信息、请求ID等）
}
