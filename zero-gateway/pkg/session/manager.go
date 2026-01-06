// pkg/session/manager.go
package session

import (
	"context"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

type SessionManager struct {
	store *RedisSessionStore
}

func NewSessionManager(redis *redis.Client) *SessionManager {
	store := &RedisSessionStore{
		redis: redis,
		ttl:   24 * time.Hour, // 会话24小时过期
	}
	return &SessionManager{store: store}
}

func (sm *SessionManager) CreateSession(agentID string, metadata map[string]interface{}) (*Session, error) {
	return sm.store.CreateSession(agentID, metadata)
}

func (sm *SessionManager) AddMessage(sessionID, role, content string, metadata map[string]interface{}) error {
	session, err := sm.store.GetSession(sessionID)
	if err != nil {
		return err
	}

	message := &Message{
		ID:        uuid.New().String(),
		Role:      role,
		Content:   content,
		Timestamp: time.Now(),
		Metadata:  metadata,
	}

	session.Messages = append(session.Messages, message)
	return sm.store.UpdateSession(sessionID, session.Messages)
}

func (sm *SessionManager) GetHistory(sessionID string, limit *int) ([]*Message, error) {
	session, err := sm.store.GetSession(sessionID)
	if err != nil {
		return nil, err
	}

	messages := session.Messages
	if limit != nil && *limit > 0 && len(messages) > *limit {
		messages = messages[len(messages)-*limit:]
	}

	return messages, nil
}

func (sm *SessionManager) GetSession(sessionID string) (*Session, error) {
	return sm.store.GetSession(sessionID)
}

func (sm *SessionManager) DeleteSession(sessionID string) error {
	// For Redis, we can delete the key directly
	// In a more complex setup, we might want to archive the session first
	return sm.store.redis.Del(context.Background(), "session:"+sessionID).Err()
}
