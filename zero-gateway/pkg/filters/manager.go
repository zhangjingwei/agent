package filters

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// FilterManager 过滤器管理器
type FilterManager struct {
	chain      *FilterChain
	logger     *zap.Logger
	enabled    bool
	metrics    *FilterMetrics
	mu         sync.RWMutex
}

// NewFilterManager 创建过滤器管理器
func NewFilterManager(logger *zap.Logger) *FilterManager {
	return &FilterManager{
		chain:   NewFilterChain(),
		logger:  logger,
		enabled: true,
		metrics: NewFilterMetrics(),
	}
}

// Enable 启用过滤器
func (fm *FilterManager) Enable() {
	fm.mu.Lock()
	defer fm.mu.Unlock()
	fm.enabled = true
	fm.logger.Info("Filter manager enabled")
}

// Disable 禁用过滤器
func (fm *FilterManager) Disable() {
	fm.mu.Lock()
	defer fm.mu.Unlock()
	fm.enabled = false
	fm.logger.Info("Filter manager disabled")
}

// IsEnabled 检查过滤器是否启用
func (fm *FilterManager) IsEnabled() bool {
	fm.mu.RLock()
	defer fm.mu.RUnlock()
	return fm.enabled
}

// RegisterRequestFilter 注册请求过滤器
func (fm *FilterManager) RegisterRequestFilter(filter RequestFilter) {
	fm.mu.Lock()
	defer fm.mu.Unlock()
	fm.chain.AddRequestFilter(filter)
	fm.logger.Info("Registered request filter",
		zap.String("filter_name", filter.Name()),
		zap.Int("priority", filter.Priority()))
}

// RegisterResponseFilter 注册响应过滤器
func (fm *FilterManager) RegisterResponseFilter(filter ResponseFilter) {
	fm.mu.Lock()
	defer fm.mu.Unlock()
	fm.chain.AddResponseFilter(filter)
	fm.logger.Info("Registered response filter",
		zap.String("filter_name", filter.Name()),
		zap.Int("priority", filter.Priority()))
}

// ExecuteRequestFilters 执行请求过滤器链
func (fm *FilterManager) ExecuteRequestFilters(ctx *FilterContext, c *gin.Context) []FilterResult {
	fm.mu.RLock()
	enabled := fm.enabled
	chain := fm.chain
	fm.mu.RUnlock()

	if !enabled {
		return nil
	}

	results := make([]FilterResult, 0, len(chain.RequestFilters))

	for _, filter := range chain.RequestFilters {
		if !filter.ShouldFilter(ctx, c) {
			continue
		}

		start := time.Now()
		success := filter.Process(ctx, c)
		duration := time.Since(start)

		result := FilterResult{
			FilterName: filter.Name(),
			Success:    success,
			Duration:   duration.Nanoseconds(),
		}

		// 记录指标
		fm.metrics.RecordExecution(filter.Name(), success, duration)

		if !success {
			result.Error = c.Errors.Last()
			fm.logger.Warn("Request filter failed",
				zap.String("filter_name", filter.Name()),
				zap.Error(result.Error),
				zap.Duration("duration", duration))
		} else {
			fm.logger.Debug("Request filter executed",
				zap.String("filter_name", filter.Name()),
				zap.Duration("duration", duration))
		}

		results = append(results, result)

		// 如果过滤器返回false，停止执行后续过滤器
		if !success {
			break
		}
	}

	return results
}

// ExecuteResponseFilters 执行响应过滤器链
func (fm *FilterManager) ExecuteResponseFilters(ctx *FilterContext, c *gin.Context, response *http.Response) []FilterResult {
	fm.mu.RLock()
	enabled := fm.enabled
	chain := fm.chain
	fm.mu.RUnlock()

	if !enabled {
		return nil
	}

	results := make([]FilterResult, 0, len(chain.ResponseFilters))

	for _, filter := range chain.ResponseFilters {
		if !filter.ShouldFilter(ctx, c) {
			continue
		}

		start := time.Now()
		success := filter.Process(ctx, c, response)
		duration := time.Since(start)

		result := FilterResult{
			FilterName: filter.Name(),
			Success:    success,
			Duration:   duration.Nanoseconds(),
		}

		// 记录指标
		fm.metrics.RecordExecution(filter.Name(), success, duration)

		if !success {
			result.Error = c.Errors.Last()
			fm.logger.Warn("Response filter failed",
				zap.String("filter_name", filter.Name()),
				zap.Error(result.Error),
				zap.Duration("duration", duration))
		} else {
			fm.logger.Debug("Response filter executed",
				zap.String("filter_name", filter.Name()),
				zap.Duration("duration", duration))
		}

		results = append(results, result)

		// 如果过滤器返回false，停止执行后续过滤器
		if !success {
			break
		}
	}

	return results
}

// GetFilterChain 返回过滤器链的副本
func (fm *FilterManager) GetFilterChain() *FilterChain {
	fm.mu.RLock()
	defer fm.mu.RUnlock()

	// 创建副本避免并发问题
	chain := NewFilterChain()
	chain.RequestFilters = make([]RequestFilter, len(fm.chain.RequestFilters))
	copy(chain.RequestFilters, fm.chain.RequestFilters)
	chain.ResponseFilters = make([]ResponseFilter, len(fm.chain.ResponseFilters))
	copy(chain.ResponseFilters, fm.chain.ResponseFilters)

	return chain
}

// CreateFilterContext 创建过滤器上下文
func (fm *FilterManager) CreateFilterContext(c *gin.Context) *FilterContext {
	// 从请求头或上下文中获取信息
	requestID := c.GetHeader("X-Request-ID")
	if requestID == "" {
		requestID = c.GetString("request_id") // 从中间件设置
	}

	sessionID := c.GetHeader("X-Session-ID")
	userID := c.GetHeader("X-User-ID")

	return &FilterContext{
		RequestID: requestID,
		SessionID: sessionID,
		UserID:    userID,
		ClientIP:  c.ClientIP(),
		UserAgent: c.GetHeader("User-Agent"),
		Metadata:  make(map[string]interface{}),
		TraceInfo: make(map[string]interface{}),
	}
}

// GetMetrics 获取过滤器性能指标
func (fm *FilterManager) GetMetrics() FilterMetrics {
	return fm.metrics.GetMetrics()
}

// ResetMetrics 重置指标
func (fm *FilterManager) ResetMetrics() {
	fm.metrics.Reset()
}