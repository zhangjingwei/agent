package cache

import (
	"context"
	"fmt"
	"time"

	"github.com/your-org/nexus-gateway/pkg/api"
)

// SessionManager manages chat sessions using Redis
type SessionManager struct {
	cache *RedisCache
}

// NewSessionManager creates a new session manager
func NewSessionManager(cache *RedisCache) *SessionManager {
	return &SessionManager{
		cache: cache,
	}
}

// CreateSession creates a new chat session
func (sm *SessionManager) CreateSession(ctx context.Context, agentID string, metadata map[string]interface{}) (*api.Session, error) {
	sessionID := generateSessionID()

	session := &api.Session{
		ID:        sessionID,
		AgentID:   agentID,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
		Metadata:  metadata,
	}

	if err := sm.cache.SetSession(ctx, sessionID, session); err != nil {
		return nil, fmt.Errorf("failed to store session: %w", err)
	}

	return session, nil
}

// GetSession retrieves a session by ID
func (sm *SessionManager) GetSession(ctx context.Context, sessionID string) (*api.Session, error) {
	var session api.Session
	if err := sm.cache.GetSession(ctx, sessionID, &session); err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	return &session, nil
}

// UpdateSession updates session data
func (sm *SessionManager) UpdateSession(ctx context.Context, session *api.Session) error {
	session.UpdatedAt = time.Now()

	if err := sm.cache.SetSession(ctx, session.ID, session); err != nil {
		return fmt.Errorf("failed to update session: %w", err)
	}

	return nil
}

// DeleteSession removes a session
func (sm *SessionManager) DeleteSession(ctx context.Context, sessionID string) error {
	if err := sm.cache.DeleteSession(ctx, sessionID); err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}

	return nil
}

// AddMessage adds a message to session history
func (sm *SessionManager) AddMessage(ctx context.Context, sessionID string, message *api.Message) error {
	session, err := sm.GetSession(ctx, sessionID)
	if err != nil {
		return fmt.Errorf("failed to get session: %w", err)
	}

	// Initialize messages slice if nil
	if session.Metadata == nil {
		session.Metadata = make(map[string]interface{})
	}

	// Get existing messages
	var messages []api.Message
	if msgs, ok := session.Metadata["messages"]; ok {
		if msgSlice, ok := msgs.([]api.Message); ok {
			messages = msgSlice
		}
	}

	// Add new message
	messages = append(messages, *message)
	session.Metadata["messages"] = messages

	// Update session
	return sm.UpdateSession(ctx, session)
}

// GetHistory retrieves message history for a session
func (sm *SessionManager) GetHistory(ctx context.Context, sessionID string, limit int) ([]api.Message, error) {
	session, err := sm.GetSession(ctx, sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	if session.Metadata == nil {
		return []api.Message{}, nil
	}

	msgs, ok := session.Metadata["messages"]
	if !ok {
		return []api.Message{}, nil
	}

	messages, ok := msgs.([]api.Message)
	if !ok {
		return []api.Message{}, nil
	}

	// Apply limit
	if limit > 0 && len(messages) > limit {
		start := len(messages) - limit
		messages = messages[start:]
	}

	return messages, nil
}

// SessionExists checks if a session exists
func (sm *SessionManager) SessionExists(ctx context.Context, sessionID string) (bool, error) {
	return sm.cache.Exists(ctx, fmt.Sprintf("session:%s", sessionID))
}

// ListSessions returns a list of active session IDs (for admin purposes)
func (sm *SessionManager) ListSessions(ctx context.Context, pattern string, limit int) ([]string, error) {
	// This is a simplified implementation
	// In production, you might want to use Redis SCAN or maintain a separate index
	keys, err := sm.cache.client.Keys(ctx, fmt.Sprintf("session:%s*", pattern)).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to list sessions: %w", err)
	}

	// Remove "session:" prefix
	sessionIDs := make([]string, len(keys))
	for i, key := range keys {
		if len(key) > 8 { // len("session:")
			sessionIDs[i] = key[8:]
		}
	}

	// Apply limit
	if limit > 0 && len(sessionIDs) > limit {
		sessionIDs = sessionIDs[:limit]
	}

	return sessionIDs, nil
}

// CleanupExpiredSessions removes expired sessions (Redis handles expiration automatically)
// This method could be used for manual cleanup or analytics
func (sm *SessionManager) CleanupExpiredSessions(ctx context.Context) error {
	// Redis TTL handles automatic cleanup
	// This method could be implemented for manual cleanup if needed
	return nil
}

// generateSessionID generates a unique session ID
func generateSessionID() string {
	return fmt.Sprintf("sess_%d_%d", time.Now().Unix(), time.Now().UnixNano()%1000000)
}
