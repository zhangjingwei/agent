// pkg/session/store.go
package session

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

type RedisSessionStore struct {
	redis *redis.Client
	ttl   time.Duration
}

func (s *RedisSessionStore) CreateSession(agentID string, metadata map[string]interface{}) (*Session, error) {
	sessionID := uuid.New().String()
	session := &Session{
		ID:        sessionID,
		AgentID:   agentID,
		Messages:  []*Message{},
		Metadata:  metadata,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	return s.saveSession(session)
}

func (s *RedisSessionStore) GetSession(sessionID string) (*Session, error) {
	key := "session:" + sessionID
	data, err := s.redis.Get(context.Background(), key).Result()
	if err != nil {
		return nil, err
	}

	var session Session
	if err := json.Unmarshal([]byte(data), &session); err != nil {
		return nil, err
	}

	return &session, nil
}

func (s *RedisSessionStore) UpdateSession(sessionID string, messages []*Message) error {
	session, err := s.GetSession(sessionID)
	if err != nil {
		return err
	}

	session.Messages = messages
	session.UpdatedAt = time.Now()

	_, err = s.saveSession(session)
	return err
}

func (s *RedisSessionStore) saveSession(session *Session) (*Session, error) {
	data, err := json.Marshal(session)
	if err != nil {
		return nil, err
	}

	key := "session:" + session.ID
	return session, s.redis.Set(context.Background(), key, data, s.ttl).Err()
}

func (rs *RedisSessionStore) CreateSessionWithID(sessionID, agentID string, metadata map[string]interface{}) (*Session, error) {
	session := &Session{
		ID:        sessionID,
		AgentID:   agentID,
		CreatedAt: time.Now(),
		Metadata:  metadata,
		Messages:  []*Message{},
	}

	data, err := json.Marshal(session)
	if err != nil {
		return nil, err
	}

	key := "session:" + sessionID
	return session, rs.redis.Set(context.Background(), key, data, rs.ttl).Err()
}
