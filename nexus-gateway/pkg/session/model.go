// pkg/session/model.go
package session

import "time"

type Session struct {
	ID        string                 `json:"id"`
	UserID    string                 `json:"user_id,omitempty"`
	AgentID   string                 `json:"agent_id"`
	Messages  []*Message             `json:"messages"`
	Metadata  map[string]interface{} `json:"metadata"`
	CreatedAt time.Time              `json:"created_at"`
	UpdatedAt time.Time              `json:"updated_at"`
}

type Message struct {
	ID        string                 `json:"id"`
	Role      string                 `json:"role"` // user/assistant
	Content   string                 `json:"content"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}
