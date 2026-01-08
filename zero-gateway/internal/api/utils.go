package api

import (
	"encoding/json"

	"github.com/gin-gonic/gin"
)

// bindJSON 从 context 获取已验证的数据或绑定 JSON
// 优先使用 input_validation 过滤器已验证的数据，避免重复读取请求体
func bindJSON(c *gin.Context, obj interface{}) error {
	// 优先从 context 获取原始请求体字节（如果 input_validation 过滤器已经验证过）
	if bodyBytes, exists := c.Get("request_body_bytes"); exists {
		if bytes, ok := bodyBytes.([]byte); ok {
			// 直接解析原始字节，避免类型转换问题
			if err := json.Unmarshal(bytes, obj); err == nil {
				return nil
			}
		}
	}

	// 如果没有原始字节，尝试从已验证的map转换（备用方案）
	if validatedBody, exists := c.Get("validated_body"); exists {
		if bodyMap, ok := validatedBody.(map[string]interface{}); ok {
			bodyJSON, err := json.Marshal(bodyMap)
			if err == nil {
				if err := json.Unmarshal(bodyJSON, obj); err == nil {
					return nil
				}
			}
		}
	}

	// 如果都没有，尝试直接绑定（此时请求体应该还在）
	return c.ShouldBindJSON(obj)
}

// min 返回两个整数中的较小值
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// NewSuccessResponse 创建OpenAPI标准成功响应
func NewSuccessResponse(data interface{}) SuccessResponse {
	return SuccessResponse{
		Data: data,
		Meta: make(map[string]interface{}),
	}
}

// NewSuccessResponseWithMeta 创建带元数据的成功响应
func NewSuccessResponseWithMeta(data interface{}, meta map[string]interface{}) SuccessResponse {
	return SuccessResponse{
		Data: data,
		Meta: meta,
	}
}