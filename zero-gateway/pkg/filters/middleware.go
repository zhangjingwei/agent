package filters

import (
	"bytes"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
)

// FilterMiddleware 过滤器中间件
type FilterMiddleware struct {
	manager *FilterManager
}

// NewFilterMiddleware 创建过滤器中间件
func NewFilterMiddleware(manager *FilterManager) *FilterMiddleware {
	return &FilterMiddleware{
		manager: manager,
	}
}

// Handler 返回Gin中间件处理函数
func (fm *FilterMiddleware) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 创建过滤器上下文
		ctx := fm.manager.CreateFilterContext(c)

		// 执行请求过滤器链
		requestResults := fm.manager.ExecuteRequestFilters(ctx, c)

		// 如果有请求过滤器失败，停止处理
		for _, result := range requestResults {
			if !result.Success {
				c.Abort()
				return
			}
		}

		// 存储过滤器上下文到Gin上下文中
		c.Set("filter_context", ctx)
		c.Set("request_filter_results", requestResults)

		// 创建响应记录器来捕获响应（延迟写入）
		responseRecorder := &responseRecorder{
			ResponseWriter: c.Writer,
			body:           &bytes.Buffer{},
		}
		c.Writer = responseRecorder

		// 处理请求
		c.Next()

		// 保存原始响应体
		originalBody := responseRecorder.body.Bytes()

		// 执行响应过滤器链
		response := &http.Response{
			StatusCode:    responseRecorder.Status(),
			Header:        responseRecorder.Header(),
			Body:          io.NopCloser(bytes.NewReader(originalBody)),
			ContentLength: int64(len(originalBody)),
		}

		responseResults := fm.manager.ExecuteResponseFilters(ctx, c, response)

		// 存储响应过滤器结果
		c.Set("response_filter_results", responseResults)

		// 读取修改后的响应体（如果过滤器修改了响应）
		finalBody := originalBody
		if response.Body != nil {
			if modifiedBody, err := io.ReadAll(response.Body); err == nil && len(modifiedBody) > 0 {
				// 如果成功读取且不为空，使用修改后的响应体
				finalBody = modifiedBody
			}
		}

		// 统一写入最终响应体（只写入一次）
		if len(finalBody) > 0 {
			responseRecorder.ResponseWriter.Write(finalBody)
		}
	}
}

// responseRecorder 响应记录器，用于捕获Gin的响应
type responseRecorder struct {
	gin.ResponseWriter
	body   *bytes.Buffer
	status int
}

func (r *responseRecorder) Write(data []byte) (int, error) {
	// 只写入到 buffer，延迟写入到原始 ResponseWriter
	// 这样可以在过滤器执行后再决定写入什么内容
	return r.body.Write(data)
}

func (r *responseRecorder) WriteHeader(statusCode int) {
	r.status = statusCode
	// 延迟写入状态码，在过滤器执行后再写入
	// 但为了兼容性，这里先写入
	r.ResponseWriter.WriteHeader(statusCode)
}

func (r *responseRecorder) Status() int {
	if r.status != 0 {
		return r.status
	}
	return r.ResponseWriter.Status()
}
