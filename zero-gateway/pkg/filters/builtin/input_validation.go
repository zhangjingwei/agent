package builtin

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"zero-gateway/pkg/filters"
)

// InputValidationFilter 输入验证过滤器
type InputValidationFilter struct {
	logger *zap.Logger
	config InputValidationConfig
}

// InputValidationConfig 输入验证配置
type InputValidationConfig struct {
	MaxMessageLength    int      `json:"max_message_length"`
	MaxMetadataSize     int      `json:"max_metadata_size"`
	BlockedWords        []string `json:"blocked_words"`
	RequiredFields      []string `json:"required_fields"`
	AllowedContentTypes []string `json:"allowed_content_types"`
}

// NewInputValidationFilter 创建输入验证过滤器
func NewInputValidationFilter(logger *zap.Logger, config InputValidationConfig) *InputValidationFilter {
	// 设置默认配置
	if config.MaxMessageLength == 0 {
		config.MaxMessageLength = 10000
	}
	if config.MaxMetadataSize == 0 {
		config.MaxMetadataSize = 1024
	}

	return &InputValidationFilter{
		logger: logger,
		config: config,
	}
}

// Name 返回过滤器名称
func (f *InputValidationFilter) Name() string {
	return "input_validation"
}

// Priority 返回过滤器优先级
func (f *InputValidationFilter) Priority() int {
	return 100 // 高优先级，在其他过滤器之前执行
}

// ShouldFilter 判断是否需要执行此过滤器
func (f *InputValidationFilter) ShouldFilter(ctx *filters.FilterContext, c *gin.Context) bool {
	// 跳过GET、HEAD、OPTIONS等没有请求体的HTTP方法
	method := c.Request.Method
	if method == http.MethodGet || method == http.MethodHead || method == http.MethodOptions {
		return false
	}

	// 跳过健康检查和指标端点
	path := c.Request.URL.Path
	if path == "/health" || path == "/ready" || strings.HasPrefix(path, "/metrics") {
		return false
	}

	// 对其他请求执行输入验证
	return true
}

// Process 执行输入验证
func (f *InputValidationFilter) Process(ctx *filters.FilterContext, c *gin.Context) bool {
	// 对于没有请求体的HTTP方法，跳过验证
	method := c.Request.Method
	if method == http.MethodGet || method == http.MethodHead || method == http.MethodOptions {
		return true
	}

	// 检查Content-Type是否为允许的内容类型
	contentType := c.GetHeader("Content-Type")
	if contentType != "" && !f.isAllowedContentType(contentType) {
		f.logger.Warn("Invalid content type",
			zap.String("content_type", contentType),
			zap.Strings("allowed_types", f.config.AllowedContentTypes))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Unsupported content type",
		})
		c.Abort()
		return false
	}

	// 验证请求体
	if contentType != "" {
		// 读取原始请求体字节，保存以便后续使用
		bodyBytes, err := io.ReadAll(c.Request.Body)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Failed to read request body"})
			c.Abort()
			return false
		}

		bodyBytes = bytes.TrimSpace(bodyBytes)
		// 如果请求体为空，不允许
		if len(bodyBytes) == 0 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Request body is required"})
			c.Abort()
			return false
		}

		// 恢复请求体
		c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

		// 解析JSON进行验证
		var requestBody map[string]interface{}
		if err := json.Unmarshal(bodyBytes, &requestBody); err != nil {
			f.logger.Warn("Failed to parse request body", zap.Error(err))
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid JSON format"})
			c.Abort()
			return false
		}

		// 验证必需字段
		if !f.validateRequiredFields(requestBody) {
			f.logger.Warn("Missing required fields")
			c.JSON(http.StatusBadRequest, gin.H{"error": "Missing required fields"})
			c.Abort()
			return false
		}

		// 验证消息长度
		if message, ok := requestBody["message"].(string); ok {
			if len(message) > f.config.MaxMessageLength {
				f.logger.Warn("Message too long",
					zap.Int("length", len(message)),
					zap.Int("max_length", f.config.MaxMessageLength))
				c.JSON(http.StatusBadRequest, gin.H{
					"error":      "Message too long",
					"max_length": f.config.MaxMessageLength,
				})
				c.Abort()
				return false
			}

			// 检查屏蔽词
			if f.containsBlockedWords(message) {
				f.logger.Warn("Message contains blocked words",
					zap.String("client_ip", ctx.ClientIP))
				c.JSON(http.StatusBadRequest, gin.H{"error": "Message contains inappropriate content"})
				c.Abort()
				return false
			}
		}

		// 验证元数据大小
		if metadata, ok := requestBody["metadata"]; ok {
			metadataSize := f.calculateSize(metadata)
			if metadataSize > f.config.MaxMetadataSize {
				f.logger.Warn("Metadata too large",
					zap.Int("size", metadataSize),
					zap.Int("max_size", f.config.MaxMetadataSize))
				c.JSON(http.StatusBadRequest, gin.H{
					"error":    "Metadata too large",
					"max_size": f.config.MaxMetadataSize,
				})
				c.Abort()
				return false
			}
		}

		// 将解析后的数据存储在上下文中，供后续使用
		c.Set("validated_body", requestBody)
	}

	f.logger.Debug("Input validation passed")
	return true
}

// isAllowedContentType 检查是否为允许的内容类型
func (f *InputValidationFilter) isAllowedContentType(contentType string) bool {
	if len(f.config.AllowedContentTypes) == 0 {
		return true
	}

	for _, allowed := range f.config.AllowedContentTypes {
		if strings.Contains(contentType, allowed) {
			return true
		}
	}
	return false
}

// validateRequiredFields 验证必需字段
func (f *InputValidationFilter) validateRequiredFields(body map[string]interface{}) bool {
	for _, field := range f.config.RequiredFields {
		if _, exists := body[field]; !exists {
			return false
		}
	}
	return true
}

// containsBlockedWords 检查是否包含屏蔽词
func (f *InputValidationFilter) containsBlockedWords(text string) bool {
	lowerText := strings.ToLower(text)
	for _, word := range f.config.BlockedWords {
		if strings.Contains(lowerText, strings.ToLower(word)) {
			return true
		}
	}
	return false
}

// calculateSize 计算对象的大致大小（用于元数据大小检查）
func (f *InputValidationFilter) calculateSize(obj interface{}) int {
	// 简单估算：将对象序列化为字符串并计算长度
	// 在生产环境中可能需要更精确的计算
	size := 0
	switch v := obj.(type) {
	case string:
		size = len(v)
	case map[string]interface{}:
		for k, val := range v {
			size += len(k) + f.calculateSize(val)
		}
	case []interface{}:
		for _, val := range v {
			size += f.calculateSize(val)
		}
	default:
		size = 8 // 估算其他类型的大小
	}
	return size
}
