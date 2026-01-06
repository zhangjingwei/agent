package filters

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// HealthCheckHandler 返回过滤器健康检查处理器
func (fm *FilterManager) HealthCheckHandler() gin.HandlerFunc {
	return func(c *gin.Context) {
		metrics := fm.GetMetrics()

		c.JSON(http.StatusOK, gin.H{
			"status": "healthy",
			"enabled": fm.IsEnabled(),
			"metrics": gin.H{
				"total_executions":      metrics.TotalExecutions,
				"successful_executions": metrics.SuccessfulExecutions,
				"failed_executions":     metrics.FailedExecutions,
				"avg_duration_ms":       metrics.AvgDuration.Milliseconds(),
				"min_duration_ms":       metrics.MinDuration.Milliseconds(),
				"max_duration_ms":       metrics.MaxDuration.Milliseconds(),
				"filter_stats":         metrics.FilterStats,
			},
		})
	}
}