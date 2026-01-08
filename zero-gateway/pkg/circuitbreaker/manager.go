package circuitbreaker

import (
	"sync"
	"time"
)

// Manager 分层熔断器管理器
// 支持用户级和Agent级熔断
type Manager struct {
	// 用户级熔断器：key = session_id 或 user_id
	userBreakers map[string]*CircuitBreaker
	// Agent级熔断器：key = agent_id
	agentBreakers map[string]*CircuitBreaker

	// 配置
	userConfig  Config
	agentConfig Config

	// 清理过期熔断器的间隔
	cleanupInterval time.Duration
	// 熔断器过期时间（无请求后多久删除）
	breakerTTL time.Duration

	mu sync.RWMutex
}

// NewManager 创建分层熔断器管理器
func NewManager(userConfig, agentConfig Config) *Manager {
	m := &Manager{
		userBreakers:    make(map[string]*CircuitBreaker),
		agentBreakers:   make(map[string]*CircuitBreaker),
		userConfig:      userConfig,
		agentConfig:     agentConfig,
		cleanupInterval: 5 * time.Minute,
		breakerTTL:      30 * time.Minute,
	}

	// 启动清理goroutine
	go m.cleanup()

	return m
}

// DefaultManager 创建使用默认配置的管理器
func DefaultManager() *Manager {
	// 用户级：更严格的配置，快速熔断问题用户
	userConfig := Config{
		FailureThreshold: 3,              // 3次失败就熔断
		SuccessThreshold: 1,              // 1次成功就恢复
		Timeout:          30 * time.Second, // 30秒后尝试恢复
	}

	// Agent级：更宽松的配置，保护整个服务
	agentConfig := Config{
		FailureThreshold: 10,             // 10次失败才熔断
		SuccessThreshold: 3,              // 3次成功才恢复
		Timeout:          60 * time.Second, // 60秒后尝试恢复
	}

	return NewManager(userConfig, agentConfig)
}

// GetUserBreaker 获取用户级熔断器
func (m *Manager) GetUserBreaker(userKey string) *CircuitBreaker {
	m.mu.Lock()
	defer m.mu.Unlock()

	breaker, exists := m.userBreakers[userKey]
	if !exists {
		breaker = NewCircuitBreaker("user:"+userKey, m.userConfig)
		m.userBreakers[userKey] = breaker
	}

	return breaker
}

// GetAgentBreaker 获取Agent级熔断器
func (m *Manager) GetAgentBreaker(agentID string) *CircuitBreaker {
	m.mu.Lock()
	defer m.mu.Unlock()

	breaker, exists := m.agentBreakers[agentID]
	if !exists {
		breaker = NewCircuitBreaker("agent:"+agentID, m.agentConfig)
		m.agentBreakers[agentID] = breaker
	}

	return breaker
}

// AllowRequest 检查是否允许请求（同时检查用户级和Agent级）
// 返回：是否允许，用户级是否熔断，Agent级是否熔断
func (m *Manager) AllowRequest(userKey, agentID string) (allowed bool, userOpen bool, agentOpen bool) {
	userBreaker := m.GetUserBreaker(userKey)
	agentBreaker := m.GetAgentBreaker(agentID)

	userOpen = userBreaker.GetState() == StateOpen
	agentOpen = agentBreaker.GetState() == StateOpen

	// 只要有一个熔断器打开，就不允许请求
	allowed = !userOpen && !agentOpen

	return allowed, userOpen, agentOpen
}

// RecordSuccess 记录成功（同时更新用户级和Agent级）
func (m *Manager) RecordSuccess(userKey, agentID string) {
	userBreaker := m.GetUserBreaker(userKey)
	agentBreaker := m.GetAgentBreaker(agentID)

	userBreaker.OnSuccess()
	agentBreaker.OnSuccess()
}

// RecordFailure 记录失败（同时更新用户级和Agent级）
// isRateLimit: 是否为429速率限制错误（不应该触发熔断）
func (m *Manager) RecordFailure(userKey, agentID string, isRateLimit bool) {
	if isRateLimit {
		// 429错误是上游的速率限制，不应该触发熔断
		// 只记录日志，不更新熔断器状态
		return
	}

	userBreaker := m.GetUserBreaker(userKey)
	agentBreaker := m.GetAgentBreaker(agentID)

	userBreaker.OnFailure()
	agentBreaker.OnFailure()
}

// GetUserBreakerStats 获取用户级熔断器统计信息
func (m *Manager) GetUserBreakerStats(userKey string) map[string]interface{} {
	breaker := m.GetUserBreaker(userKey)
	return breaker.GetStats()
}

// GetAgentBreakerStats 获取Agent级熔断器统计信息
func (m *Manager) GetAgentBreakerStats(agentID string) map[string]interface{} {
	breaker := m.GetAgentBreaker(agentID)
	return breaker.GetStats()
}

// ResetUserBreaker 重置用户级熔断器
func (m *Manager) ResetUserBreaker(userKey string) {
	breaker := m.GetUserBreaker(userKey)
	breaker.Reset()
}

// ResetAgentBreaker 重置Agent级熔断器
func (m *Manager) ResetAgentBreaker(agentID string) {
	breaker := m.GetAgentBreaker(agentID)
	breaker.Reset()
}

// cleanup 定期清理过期的熔断器
func (m *Manager) cleanup() {
	ticker := time.NewTicker(m.cleanupInterval)
	defer ticker.Stop()

	for range ticker.C {
		m.mu.Lock()
		now := time.Now()

		// 清理用户级熔断器
		for key, breaker := range m.userBreakers {
			stats := breaker.GetStats()
			if lastFailure, ok := stats["last_failure_time"].(string); ok && lastFailure != "" {
				if t, err := time.Parse(time.RFC3339, lastFailure); err == nil {
					if now.Sub(t) > m.breakerTTL && breaker.GetState() == StateClosed {
						delete(m.userBreakers, key)
					}
				}
			}
		}

		// 清理Agent级熔断器
		for key, breaker := range m.agentBreakers {
			stats := breaker.GetStats()
			if lastFailure, ok := stats["last_failure_time"].(string); ok && lastFailure != "" {
				if t, err := time.Parse(time.RFC3339, lastFailure); err == nil {
					if now.Sub(t) > m.breakerTTL && breaker.GetState() == StateClosed {
						delete(m.agentBreakers, key)
					}
				}
			}
		}

		m.mu.Unlock()
	}
}
