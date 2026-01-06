package builtin

import (
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/your-org/zero-gateway/pkg/filters"
)

// AuditFilter 审计过滤器
type AuditFilter struct {
	logger *zap.Logger
	config AuditConfig
}

// AuditConfig 审计配置
type AuditConfig struct {
	EnableRequestLogging  bool     `json:"enable_request_logging"`  // 启用请求日志
	EnableResponseLogging bool     `json:"enable_response_logging"` // 启用响应日志
	LogSensitiveData      bool     `json:"log_sensitive_data"`      // 是否记录敏感数据
	SensitiveFields       []string `json:"sensitive_fields"`        // 敏感字段列表
	MaxLogSize            int      `json:"max_log_size"`            // 最大日志大小
	LogLevel              string   `json:"log_level"`               // 日志级别
}

// NewAuditFilter 创建审计过滤器
func NewAuditFilter(logger *zap.Logger, config AuditConfig) *AuditFilter {
	// 设置默认配置
	if config.MaxLogSize == 0 {
		config.MaxLogSize = 1024
	}
	if config.LogLevel == "" {
		config.LogLevel = "info"
	}
	if len(config.SensitiveFields) == 0 {
		config.SensitiveFields = []string{"password", "token", "secret", "key", "authorization"}
	}

	return &AuditFilter{
		logger: logger,
		config: config,
	}
}

// Name 返回过滤器名称
func (f *AuditFilter) Name() string {
	return "audit"
}

// Priority 返回过滤器优先级
func (f *AuditFilter) Priority() int {
	return 10 // 最高优先级，最先执行
}

// ShouldFilter 判断是否需要执行此过滤器
func (f *AuditFilter) ShouldFilter(ctx *filters.FilterContext, c *gin.Context) bool {
	// 对所有请求都执行审计
	return true
}

// Process 执行审计
func (f *AuditFilter) Process(ctx *filters.FilterContext, c *gin.Context) bool {
	if f.config.EnableRequestLogging {
		f.logRequest(ctx, c)
	}

	// 记录审计开始时间
	ctx.Metadata["audit_start_time"] = time.Now()

	return true
}

// logRequest 记录请求日志
func (f *AuditFilter) logRequest(ctx *filters.FilterContext, c *gin.Context) {
	fields := []zap.Field{
		zap.String("request_id", ctx.RequestID),
		zap.String("session_id", ctx.SessionID),
		zap.String("user_id", ctx.UserID),
		zap.String("client_ip", ctx.ClientIP),
		zap.String("user_agent", ctx.UserAgent),
		zap.String("method", c.Request.Method),
		zap.String("path", c.Request.URL.Path),
		zap.String("query", c.Request.URL.RawQuery),
		zap.String("content_type", c.GetHeader("Content-Type")),
		zap.Int("content_length", int(c.Request.ContentLength)),
	}

	// 记录请求头（过滤敏感信息）
	headers := f.filterSensitiveHeaders(c.Request.Header)
	if len(headers) > 0 {
		fields = append(fields, zap.Any("headers", headers))
	}

	// 记录请求体（如果启用且不包含敏感数据）
	if f.config.LogSensitiveData && c.Request.ContentLength > 0 && c.Request.ContentLength < int64(f.config.MaxLogSize) {
		if body := f.getRequestBody(c); body != nil {
			fields = append(fields, zap.String("body", string(body)))
		}
	}

	f.logger.Info("Request audit", fields...)
}

// filterSensitiveHeaders 过滤敏感头信息
func (f *AuditFilter) filterSensitiveHeaders(headers http.Header) map[string]string {
	filtered := make(map[string]string)

	for key, values := range headers {
		lowerKey := strings.ToLower(key)
		isSensitive := false

		for _, sensitive := range f.config.SensitiveFields {
			if strings.Contains(lowerKey, strings.ToLower(sensitive)) {
				isSensitive = true
				break
			}
		}

		if !isSensitive && len(values) > 0 {
			filtered[key] = values[0] // 只记录第一个值
		}
	}

	return filtered
}

// getRequestBody 获取请求体（用于日志记录）
func (f *AuditFilter) getRequestBody(c *gin.Context) []byte {
	// 注意：这是一个简化实现，实际使用时需要考虑性能和内存使用
	// 在生产环境中，应该从validated_body中获取已经读取的数据
	if body, exists := c.Get("validated_body"); exists {
		if bodyBytes, ok := body.([]byte); ok {
			return bodyBytes
		}
	}
	return nil
}

// getResponseBody 获取响应体（用于日志记录）
func (f *AuditFilter) getResponseBody(response *http.Response) []byte {
	// 注意：这是一个简化实现，实际使用时需要考虑性能
	// 在生产环境中可能需要包装响应以便记录
	return nil
}

// AuditResponseFilter 审计响应过滤器
type AuditResponseFilter struct {
	logger *zap.Logger
	config AuditConfig
}

// NewAuditResponseFilter 创建审计响应过滤器
func NewAuditResponseFilter(logger *zap.Logger, config AuditConfig) *AuditResponseFilter {
	return &AuditResponseFilter{
		logger: logger,
		config: config,
	}
}

// Name 返回过滤器名称
func (f *AuditResponseFilter) Name() string {
	return "audit_response"
}

// Priority 返回过滤器优先级
func (f *AuditResponseFilter) Priority() int {
	return 10 // 最高优先级，最先执行
}

// ShouldFilter 判断是否需要执行此过滤器
func (f *AuditResponseFilter) ShouldFilter(ctx *filters.FilterContext, c *gin.Context) bool {
	// 对所有响应都执行审计
	return true
}

// Process 处理响应审计
func (f *AuditResponseFilter) Process(ctx *filters.FilterContext, c *gin.Context, response *http.Response) bool {
	if !f.config.EnableResponseLogging {
		return true
	}

	startTime, _ := ctx.Metadata["audit_start_time"].(time.Time)
	duration := time.Since(startTime)

	f.logResponse(ctx, c, response, duration)
	return true
}

// logResponse 记录响应日志
func (f *AuditResponseFilter) logResponse(ctx *filters.FilterContext, c *gin.Context, response *http.Response, duration time.Duration) {
	fields := []zap.Field{
		zap.String("request_id", ctx.RequestID),
		zap.String("session_id", ctx.SessionID),
		zap.String("user_id", ctx.UserID),
		zap.Int("status_code", response.StatusCode),
		zap.Duration("duration", duration),
		zap.String("content_type", response.Header.Get("Content-Type")),
		zap.Int64("content_length", response.ContentLength),
	}

	// 记录响应头（过滤敏感信息）
	headers := f.filterSensitiveHeaders(response.Header)
	if len(headers) > 0 {
		fields = append(fields, zap.Any("response_headers", headers))
	}

	// 记录响应体（如果启用且大小合适）
	if f.config.LogSensitiveData && response.ContentLength > 0 && response.ContentLength < int64(f.config.MaxLogSize) {
		if body := f.getResponseBody(response); body != nil {
			fields = append(fields, zap.String("response_body", string(body)))
		}
	}

	f.logger.Info("Response audit", fields...)
}

// filterSensitiveHeaders 过滤敏感头信息
func (f *AuditResponseFilter) filterSensitiveHeaders(headers http.Header) map[string]string {
	filtered := make(map[string]string)

	for key, values := range headers {
		lowerKey := strings.ToLower(key)
		isSensitive := false

		for _, sensitive := range f.config.SensitiveFields {
			if strings.Contains(lowerKey, strings.ToLower(sensitive)) {
				isSensitive = true
				break
			}
		}

		if !isSensitive && len(values) > 0 {
			filtered[key] = values[0] // 只记录第一个值
		}
	}

	return filtered
}

// getResponseBody 获取响应体（用于日志记录）
func (f *AuditResponseFilter) getResponseBody(response *http.Response) []byte {
	// 注意：这是一个简化实现，实际使用时需要考虑性能
	// 在生产环境中可能需要包装响应以便记录
	return nil
}
