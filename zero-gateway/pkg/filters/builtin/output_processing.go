package builtin

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"zero-gateway/pkg/filters"
)

// OutputProcessingFilter 输出处理过滤器
type OutputProcessingFilter struct {
	logger *zap.Logger
	config OutputProcessingConfig
}

// OutputProcessingConfig 输出处理配置
type OutputProcessingConfig struct {
	SanitizeOutput     bool   `json:"sanitize_output"`      // 是否清理输出
	MaxResponseSize    int    `json:"max_response_size"`    // 最大响应大小
	AddResponseHeaders bool   `json:"add_response_headers"` // 是否添加响应头
	ResponseTimeout    int    `json:"response_timeout"`     // 响应超时时间（秒）
	CompressionEnabled bool   `json:"compression_enabled"`  // 是否启用压缩
	CacheControlHeader string `json:"cache_control_header"` // 缓存控制头
	CORSHeaders        bool   `json:"cors_headers"`         // 是否添加CORS头
}

// NewOutputProcessingFilter 创建输出处理过滤器
func NewOutputProcessingFilter(logger *zap.Logger, config OutputProcessingConfig) *OutputProcessingFilter {
	// 设置默认配置
	if config.MaxResponseSize == 0 {
		config.MaxResponseSize = 10 * 1024 * 1024 // 10MB
	}
	if config.ResponseTimeout == 0 {
		config.ResponseTimeout = 30
	}
	if config.CacheControlHeader == "" {
		config.CacheControlHeader = "no-cache"
	}

	return &OutputProcessingFilter{
		logger: logger,
		config: config,
	}
}

// Name 返回过滤器名称
func (f *OutputProcessingFilter) Name() string {
	return "output_processing"
}

// Priority 返回过滤器优先级
func (f *OutputProcessingFilter) Priority() int {
	return 200 // 中等优先级，在请求过滤器之后执行
}

// ShouldFilter 判断是否需要执行此过滤器
func (f *OutputProcessingFilter) ShouldFilter(ctx *filters.FilterContext, c *gin.Context) bool {
	// 对所有响应都执行输出处理
	return true
}

// Process 处理响应输出
func (f *OutputProcessingFilter) Process(ctx *filters.FilterContext, c *gin.Context, response *http.Response) bool {
	// 添加响应头
	if f.config.AddResponseHeaders {
		f.addResponseHeaders(c, ctx)
	}

	// 检查响应大小
	if f.config.MaxResponseSize > 0 {
		if err := f.checkResponseSize(response); err != nil {
			f.logger.Warn("Response size check failed", zap.Error(err))
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Response too large"})
			return false
		}
	}

	// 清理响应内容
	if f.config.SanitizeOutput {
		if err := f.sanitizeResponse(response); err != nil {
			f.logger.Warn("Response sanitization failed", zap.Error(err))
			// 清理失败不阻止响应，继续处理
		}
	}

	// 添加处理时间戳
	ctx.Metadata["response_processed_at"] = time.Now().Unix()

	f.logger.Debug("Output processing completed",
		zap.String("request_id", ctx.RequestID),
		zap.Int("response_size", f.getResponseSize(response)))

	return true
}

// addResponseHeaders 添加响应头
func (f *OutputProcessingFilter) addResponseHeaders(c *gin.Context, ctx *filters.FilterContext) {
	// 添加标准头
	c.Header("X-Request-ID", ctx.RequestID)
	c.Header("X-Processed-At", time.Now().Format(time.RFC3339))

	// 添加缓存控制
	if f.config.CacheControlHeader != "" {
		c.Header("Cache-Control", f.config.CacheControlHeader)
	}

	// 添加CORS头
	if f.config.CORSHeaders {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
	}

	// 添加安全头
	c.Header("X-Content-Type-Options", "nosniff")
	c.Header("X-Frame-Options", "DENY")
	c.Header("X-XSS-Protection", "1; mode=block")
}

// checkResponseSize 检查响应大小
func (f *OutputProcessingFilter) checkResponseSize(response *http.Response) error {
	if response.Body == nil {
		return nil
	}

	// 读取响应体并检查大小
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return err
	}

	if len(body) > f.config.MaxResponseSize {
		return &ResponseTooLargeError{
			Size:    len(body),
			MaxSize: f.config.MaxResponseSize,
		}
	}

	// 重新设置响应体
	response.Body = io.NopCloser(bytes.NewReader(body))
	return nil
}

// sanitizeResponse 清理响应内容
func (f *OutputProcessingFilter) sanitizeResponse(response *http.Response) error {
	if response.Body == nil {
		return nil
	}

	// 只处理JSON响应
	contentType := response.Header.Get("Content-Type")
	if !strings.Contains(contentType, "application/json") {
		return nil
	}

	// 读取响应体
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return err
	}

	// 解析JSON
	var jsonData interface{}
	if err := json.Unmarshal(body, &jsonData); err != nil {
		return err
	}

	// 清理敏感信息
	f.sanitizeJSONData(jsonData)

	// 重新序列化
	cleanBody, err := json.Marshal(jsonData)
	if err != nil {
		return err
	}

	// 重新设置响应体
	response.Body = io.NopCloser(bytes.NewReader(cleanBody))
	return nil
}

// sanitizeJSONData 清理JSON数据中的敏感信息
func (f *OutputProcessingFilter) sanitizeJSONData(data interface{}) {
	switch v := data.(type) {
	case map[string]interface{}:
		// 清理敏感字段
		sensitiveFields := []string{"password", "token", "secret", "key"}
		for _, field := range sensitiveFields {
			if _, exists := v[field]; exists {
				v[field] = "***REDACTED***"
			}
		}

		// 递归处理嵌套对象
		for _, value := range v {
			f.sanitizeJSONData(value)
		}

	case []interface{}:
		// 处理数组
		for _, item := range v {
			f.sanitizeJSONData(item)
		}
	}
}

// getResponseSize 获取响应大小
func (f *OutputProcessingFilter) getResponseSize(response *http.Response) int {
	if response.Body == nil {
		return 0
	}

	// 尝试从Content-Length头获取
	if length := response.ContentLength; length > 0 {
		return int(length)
	}

	// 如果无法获取，尝试读取并计算
	if body, err := io.ReadAll(response.Body); err == nil {
		// 重新设置响应体
		response.Body = io.NopCloser(bytes.NewReader(body))
		return len(body)
	}

	return 0
}

// ResponseTooLargeError 响应过大错误
type ResponseTooLargeError struct {
	Size    int
	MaxSize int
}

func (e *ResponseTooLargeError) Error() string {
	return "response too large"
}
