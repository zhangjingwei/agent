package api

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// SetupRoutes 设置API路由
func SetupRoutes(r *gin.Engine, handler *Handler) {

	// 健康检查端点
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status": "ok",
		})
	})

	apiV1 := r.Group("/api/v1")
	{
		// Chat endpoint (unified for both streaming and non-streaming)
		apiV1.POST("/chat", handler.Chat)
		apiV1.POST("/sessions", handler.CreateSession)
		apiV1.GET("/sessions/:session_id/history", handler.GetHistory)
		apiV1.DELETE("/sessions/:session_id", handler.ClearSession)

		// Tools endpoints
		apiV1.GET("/tools", handler.ListTools)
	}
}
