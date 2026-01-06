package filters

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// FilterContext 过滤器上下文，包含请求处理的共享信息
type FilterContext struct {
	RequestID    string                 `json:"request_id"`
	SessionID    string                 `json:"session_id,omitempty"`
	UserID       string                 `json:"user_id,omitempty"`
	ClientIP     string                 `json:"client_ip"`
	UserAgent    string                 `json:"user_agent"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	TraceInfo    map[string]interface{} `json:"trace_info,omitempty"`
}

// RequestFilter 请求过滤器接口
type RequestFilter interface {
	// Name 返回过滤器名称
	Name() string

	// Priority 返回过滤器优先级（数字越小优先级越高）
	Priority() int

	// ShouldFilter 判断是否需要执行此过滤器
	ShouldFilter(ctx *FilterContext, c *gin.Context) bool

	// Process 过滤器处理逻辑，如果返回false则停止后续处理
	Process(ctx *FilterContext, c *gin.Context) bool
}

// ResponseFilter 响应过滤器接口
type ResponseFilter interface {
	// Name 返回过滤器名称
	Name() string

	// Priority 返回过滤器优先级（数字越小优先级越高）
	Priority() int

	// ShouldFilter 判断是否需要执行此过滤器
	ShouldFilter(ctx *FilterContext, c *gin.Context) bool

	// Process 过滤器处理逻辑，如果返回false则停止后续处理
	Process(ctx *FilterContext, c *gin.Context, response *http.Response) bool
}

// FilterResult 过滤器执行结果
type FilterResult struct {
	FilterName string `json:"filter_name"`
	Success    bool   `json:"success"`
	Error      error  `json:"error,omitempty"`
	Duration   int64  `json:"duration_ns"` // 执行耗时（纳秒）
}

// FilterChain 过滤器链
type FilterChain struct {
	RequestFilters  []RequestFilter  `json:"request_filters"`
	ResponseFilters []ResponseFilter `json:"response_filters"`
}

// NewFilterChain 创建新的过滤器链
func NewFilterChain() *FilterChain {
	return &FilterChain{
		RequestFilters:  make([]RequestFilter, 0),
		ResponseFilters: make([]ResponseFilter, 0),
	}
}

// AddRequestFilter 添加请求过滤器
func (fc *FilterChain) AddRequestFilter(filter RequestFilter) {
	fc.RequestFilters = append(fc.RequestFilters, filter)
	// 按优先级排序
	fc.sortRequestFilters()
}

// AddResponseFilter 添加响应过滤器
func (fc *FilterChain) AddResponseFilter(filter ResponseFilter) {
	fc.ResponseFilters = append(fc.ResponseFilters, filter)
	// 按优先级排序
	fc.sortResponseFilters()
}

// sortRequestFilters 按优先级排序请求过滤器
func (fc *FilterChain) sortRequestFilters() {
	// 简单冒泡排序，按优先级升序（数字小的优先级高）
	for i := 0; i < len(fc.RequestFilters)-1; i++ {
		for j := 0; j < len(fc.RequestFilters)-i-1; j++ {
			if fc.RequestFilters[j].Priority() > fc.RequestFilters[j+1].Priority() {
				fc.RequestFilters[j], fc.RequestFilters[j+1] = fc.RequestFilters[j+1], fc.RequestFilters[j]
			}
		}
	}
}

// sortResponseFilters 按优先级排序响应过滤器
func (fc *FilterChain) sortResponseFilters() {
	// 简单冒泡排序，按优先级升序（数字小的优先级高）
	for i := 0; i < len(fc.ResponseFilters)-1; i++ {
		for j := 0; j < len(fc.ResponseFilters)-i-1; j++ {
			if fc.ResponseFilters[j].Priority() > fc.ResponseFilters[j+1].Priority() {
				fc.ResponseFilters[j], fc.ResponseFilters[j+1] = fc.ResponseFilters[j+1], fc.ResponseFilters[j]
			}
		}
	}
}