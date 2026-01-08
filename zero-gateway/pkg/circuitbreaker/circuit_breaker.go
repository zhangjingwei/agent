package circuitbreaker

import (
	"sync"
	"time"
)

// State 熔断器状态
type State string

const (
	StateClosed   State = "closed"    // 关闭：正常状态，允许请求通过
	StateOpen     State = "open"      // 打开：熔断状态，拒绝请求
	StateHalfOpen State = "half_open" // 半开：尝试恢复，允许少量请求通过
)

// CircuitBreaker 熔断器实现
type CircuitBreaker struct {
	name             string
	failureThreshold int           // 连续失败次数阈值
	successThreshold int           // 半开状态下成功次数阈值（用于恢复）
	timeout          time.Duration // 熔断持续时间

	state           State
	failureCount    int
	successCount    int
	lastFailureTime *time.Time
	mu              sync.RWMutex
}

// Config 熔断器配置
type Config struct {
	FailureThreshold int           // 触发熔断的连续失败次数
	SuccessThreshold int           // 半开状态下需要连续成功的次数
	Timeout          time.Duration // 熔断持续时间
}

// DefaultConfig 返回默认配置
func DefaultConfig() Config {
	return Config{
		FailureThreshold: 5,
		SuccessThreshold: 2,
		Timeout:          60 * time.Second,
	}
}

// NewCircuitBreaker 创建新的熔断器
func NewCircuitBreaker(name string, config Config) *CircuitBreaker {
	return &CircuitBreaker{
		name:             name,
		failureThreshold: config.FailureThreshold,
		successThreshold: config.SuccessThreshold,
		timeout:          config.Timeout,
		state:            StateClosed,
		failureCount:     0,
		successCount:     0,
	}
}

// Allow 检查是否允许请求通过
func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()

	// 如果处于打开状态，检查是否超时
	if cb.state == StateOpen {
		if cb.lastFailureTime != nil && now.Sub(*cb.lastFailureTime) >= cb.timeout {
			// 超时，进入半开状态
			cb.state = StateHalfOpen
			cb.successCount = 0
			return true
		}
		// 仍在熔断期内，拒绝请求
		return false
	}

	// 关闭或半开状态，允许请求
	return true
}

// OnSuccess 记录成功
func (cb *CircuitBreaker) OnSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if cb.state == StateHalfOpen {
		cb.successCount++
		if cb.successCount >= cb.successThreshold {
			// 连续成功达到阈值，恢复关闭状态
			cb.state = StateClosed
			cb.failureCount = 0
			cb.successCount = 0
		}
	} else {
		// 关闭状态下，重置失败计数
		cb.failureCount = 0
	}
}

// OnFailure 记录失败
func (cb *CircuitBreaker) OnFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()
	cb.lastFailureTime = &now

	if cb.state == StateHalfOpen {
		// 半开状态下失败，立即重新打开
		cb.state = StateOpen
		cb.successCount = 0
	} else {
		// 关闭状态下，增加失败计数
		cb.failureCount++
		if cb.failureCount >= cb.failureThreshold {
			// 达到失败阈值，打开熔断器
			cb.state = StateOpen
		}
	}
}

// GetState 获取当前状态
func (cb *CircuitBreaker) GetState() State {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// Reset 手动重置熔断器
func (cb *CircuitBreaker) Reset() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.state = StateClosed
	cb.failureCount = 0
	cb.successCount = 0
	cb.lastFailureTime = nil
}

// GetStats 获取统计信息
func (cb *CircuitBreaker) GetStats() map[string]interface{} {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	stats := map[string]interface{}{
		"name":              cb.name,
		"state":             string(cb.state),
		"failure_count":     cb.failureCount,
		"success_count":     cb.successCount,
		"failure_threshold": cb.failureThreshold,
		"success_threshold": cb.successThreshold,
		"timeout":           cb.timeout.String(),
	}

	if cb.lastFailureTime != nil {
		stats["last_failure_time"] = cb.lastFailureTime.Format(time.RFC3339)
	}

	return stats
}
