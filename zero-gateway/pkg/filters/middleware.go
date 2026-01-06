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
				// 错误已经在过滤器中处理，直接返回
				return
			}
		}

		// 存储过滤器上下文到Gin上下文中
		c.Set("filter_context", ctx)
		c.Set("request_filter_results", requestResults)

		// 创建响应记录器来捕获响应
		responseRecorder := &responseRecorder{
			ResponseWriter: c.Writer,
			body:           &bytes.Buffer{},
		}
		c.Writer = responseRecorder

		// 处理请求
		c.Next()

		// 执行响应过滤器链
		response := &http.Response{
			StatusCode:    responseRecorder.Status(),
			Header:        responseRecorder.Header(),
			Body:          io.NopCloser(bytes.NewReader(responseRecorder.body.Bytes())),
			ContentLength: int64(responseRecorder.body.Len()),
		}

		responseResults := fm.manager.ExecuteResponseFilters(ctx, c, response)

		// 存储响应过滤器结果
		c.Set("response_filter_results", responseResults)

		// 如果响应被过滤器修改，需要重新写入响应
		if responseRecorder.body.Len() > 0 {
			// 将修改后的响应写回
			c.Writer.Write(responseRecorder.body.Bytes())
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
	r.body.Write(data)
	return r.ResponseWriter.Write(data)
}

func (r *responseRecorder) WriteHeader(statusCode int) {
	r.status = statusCode
	r.ResponseWriter.WriteHeader(statusCode)
}

func (r *responseRecorder) Status() int {
	if r.status != 0 {
		return r.status
	}
	return r.ResponseWriter.Status()
}