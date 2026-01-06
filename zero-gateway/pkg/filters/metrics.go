package filters

import (
	"sync"
	"time"
)

// FilterMetrics 过滤器性能指标
type FilterMetrics struct {
	mu sync.RWMutex

	// 执行统计
	TotalExecutions   int64            `json:"total_executions"`
	SuccessfulExecutions int64         `json:"successful_executions"`
	FailedExecutions  int64            `json:"failed_executions"`
	
	// 性能统计
	TotalDuration     time.Duration   `json:"total_duration"`
	MinDuration       time.Duration   `json:"min_duration"`
	MaxDuration       time.Duration   `json:"max_duration"`
	AvgDuration       time.Duration   `json:"avg_duration"`
	
	// 按过滤器名称的统计
	FilterStats       map[string]*FilterStats `json:"filter_stats"`
}

// FilterStats 单个过滤器的统计信息
type FilterStats struct {
	Name              string          `json:"name"`
	TotalExecutions   int64           `json:"total_executions"`
	SuccessfulExecutions int64        `json:"successful_executions"`
	FailedExecutions  int64           `json:"failed_executions"`
	TotalDuration     time.Duration   `json:"total_duration"`
	MinDuration       time.Duration   `json:"min_duration"`
	MaxDuration       time.Duration   `json:"max_duration"`
	AvgDuration       time.Duration   `json:"avg_duration"`
}

// NewFilterMetrics 创建过滤器指标收集器
func NewFilterMetrics() *FilterMetrics {
	return &FilterMetrics{
		FilterStats: make(map[string]*FilterStats),
		MinDuration: time.Hour, // 初始化为一个很大的值
	}
}

// RecordExecution 记录过滤器执行
func (fm *FilterMetrics) RecordExecution(filterName string, success bool, duration time.Duration) {
	fm.mu.Lock()
	defer fm.mu.Unlock()

	// 更新总体统计
	fm.TotalExecutions++
	if success {
		fm.SuccessfulExecutions++
	} else {
		fm.FailedExecutions++
	}

	fm.TotalDuration += duration
	if duration < fm.MinDuration {
		fm.MinDuration = duration
	}
	if duration > fm.MaxDuration {
		fm.MaxDuration = duration
	}
	fm.AvgDuration = fm.TotalDuration / time.Duration(fm.TotalExecutions)

	// 更新单个过滤器统计
	stats, exists := fm.FilterStats[filterName]
	if !exists {
		stats = &FilterStats{
			Name:            filterName,
			MinDuration:     time.Hour,
		}
		fm.FilterStats[filterName] = stats
	}

	stats.TotalExecutions++
	if success {
		stats.SuccessfulExecutions++
	} else {
		stats.FailedExecutions++
	}

	stats.TotalDuration += duration
	if duration < stats.MinDuration {
		stats.MinDuration = duration
	}
	if duration > stats.MaxDuration {
		stats.MaxDuration = duration
	}
	stats.AvgDuration = stats.TotalDuration / time.Duration(stats.TotalExecutions)
}

// GetMetrics 获取指标快照
func (fm *FilterMetrics) GetMetrics() FilterMetrics {
	fm.mu.RLock()
	defer fm.mu.RUnlock()

	// 创建副本
	snapshot := FilterMetrics{
		TotalExecutions:      fm.TotalExecutions,
		SuccessfulExecutions: fm.SuccessfulExecutions,
		FailedExecutions:     fm.FailedExecutions,
		TotalDuration:        fm.TotalDuration,
		MinDuration:          fm.MinDuration,
		MaxDuration:          fm.MaxDuration,
		AvgDuration:          fm.AvgDuration,
		FilterStats:          make(map[string]*FilterStats),
	}

	// 复制过滤器统计
	for name, stats := range fm.FilterStats {
		snapshot.FilterStats[name] = &FilterStats{
			Name:                stats.Name,
			TotalExecutions:    stats.TotalExecutions,
			SuccessfulExecutions: stats.SuccessfulExecutions,
			FailedExecutions:     stats.FailedExecutions,
			TotalDuration:        stats.TotalDuration,
			MinDuration:          stats.MinDuration,
			MaxDuration:          stats.MaxDuration,
			AvgDuration:          stats.AvgDuration,
		}
	}

	return snapshot
}

// Reset 重置指标
func (fm *FilterMetrics) Reset() {
	fm.mu.Lock()
	defer fm.mu.Unlock()

	fm.TotalExecutions = 0
	fm.SuccessfulExecutions = 0
	fm.FailedExecutions = 0
	fm.TotalDuration = 0
	fm.MinDuration = time.Hour
	fm.MaxDuration = 0
	fm.AvgDuration = 0
	fm.FilterStats = make(map[string]*FilterStats)
}