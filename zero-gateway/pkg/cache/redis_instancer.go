package cache

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/go-kit/kit/sd"
	"go.uber.org/zap"

	"zero-gateway/internal/infrastructure"
)

// RedisInstancer 实现 go-kit 的 sd.Instancer 接口，从 Redis 发现服务
type RedisInstancer struct {
	discovery     *ServiceDiscovery
	serviceName   string
	logger        *zap.Logger
	mu            sync.RWMutex
	instances     []string
	eventChan     chan<- sd.Event
	stopChan      chan struct{}
	refreshTicker *time.Ticker
}

// NewRedisInstancer 创建基于 Redis 的服务实例发现器
func NewRedisInstancer(
	discovery *ServiceDiscovery,
	serviceName string,
	logger *zap.Logger,
) *RedisInstancer {
	instancer := &RedisInstancer{
		discovery:     discovery,
		serviceName:   serviceName,
		logger:        logger,
		instances:     make([]string, 0),
		eventChan:     nil, // 将在 Register 时设置
		stopChan:      make(chan struct{}),
		refreshTicker: time.NewTicker(5 * time.Second),
	}

	// 启动后台刷新任务
	go instancer.refreshLoop()

	return instancer
}

// Register 注册事件通道，当服务实例变化时发送事件
func (r *RedisInstancer) Register(ch chan<- sd.Event) {
	r.mu.Lock()
	r.eventChan = ch
	// 获取当前实例列表的副本
	instances := make([]string, len(r.instances))
	copy(instances, r.instances)
	r.mu.Unlock()

	// 立即发送一次当前状态（阻塞发送，确保 NewEndpointer 能收到初始事件）
	// 这是必需的，因为 NewEndpointer 会等待第一个事件
	if len(instances) > 0 {
		ch <- sd.Event{Instances: instances}
	} else {
		// 即使没有实例，也发送空事件，避免 NewEndpointer 阻塞
		ch <- sd.Event{Instances: []string{}}
	}

	// 在后台刷新服务列表（刷新后会自动发送更新事件，如果列表有变化）
	go func() {
		// 稍微延迟，确保 Register 完成后再刷新
		time.Sleep(50 * time.Millisecond)
		ctx := context.Background()
		r.refresh(ctx)
	}()
}

// Deregister 注销事件通道
func (r *RedisInstancer) Deregister(ch chan<- sd.Event) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.eventChan == ch {
		r.eventChan = nil
	}
}

// Stop 停止实例发现器
func (r *RedisInstancer) Stop() {
	close(r.stopChan)
	r.refreshTicker.Stop()
	r.mu.Lock()
	r.eventChan = nil
	r.mu.Unlock()
}

// refreshLoop 后台刷新循环
func (r *RedisInstancer) refreshLoop() {
	ctx := context.Background()

	// 立即执行一次刷新（在 goroutine 中，避免阻塞）
	go func() {
		time.Sleep(100 * time.Millisecond) // 给 Register 时间完成
		r.refresh(ctx)
	}()

	for {
		select {
		case <-r.stopChan:
			return
		case <-r.refreshTicker.C:
			r.refresh(ctx)
		}
	}
}

// refresh 刷新服务实例列表
func (r *RedisInstancer) refresh(ctx context.Context) {
	services, err := r.discovery.DiscoverServices(ctx, r.serviceName)
	if err != nil {
		r.logger.Warn("Failed to discover services", zap.Error(err))
		return
	}

	// 过滤健康的服务并转换为实例地址
	now := time.Now()
	newInstances := make([]string, 0)
	healthyServices := make([]*infrastructure.ServiceInfo, 0)

	for _, svc := range services {
		// 检查服务是否健康（30秒内有心跳）
		if now.Sub(svc.LastSeen) < 30*time.Second {
			instance := fmt.Sprintf("http://%s:%d", svc.Address, svc.Port)
			newInstances = append(newInstances, instance)
			healthyServices = append(healthyServices, &infrastructure.ServiceInfo{
				ID:           svc.ID,
				Name:         svc.Name,
				Address:      svc.Address,
				Port:         svc.Port,
				Protocol:     svc.Protocol,
				HealthCheck:  svc.HealthCheck,
				Metadata:     svc.Metadata,
				RegisteredAt: svc.RegisteredAt,
				LastSeen:     svc.LastSeen,
				TTL:          svc.TTL,
			})
		}
	}

	r.mu.Lock()
	oldInstances := r.instances
	r.instances = newInstances
	r.mu.Unlock()

	// 如果实例列表发生变化，发送事件
	if !instancesEqual(oldInstances, newInstances) {
		r.logger.Debug("Service instances changed",
			zap.String("service_name", r.serviceName),
			zap.Int("old_count", len(oldInstances)),
			zap.Int("new_count", len(newInstances)),
		)
		r.sendEvent()
	}
}

// sendEvent 发送服务实例变化事件
func (r *RedisInstancer) sendEvent() {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if r.eventChan == nil {
		return
	}

	// 创建实例列表的副本
	instances := make([]string, len(r.instances))
	copy(instances, r.instances)

	// 发送事件（非阻塞，如果通道满则跳过，避免阻塞）
	select {
	case r.eventChan <- sd.Event{Instances: instances}:
		// 成功发送
	default:
		// 如果通道已满，静默跳过（这是正常的，因为刷新频率可能高于消费速度）
		// 下次刷新时会再次尝试发送
	}
}

// instancesEqual 比较两个实例列表是否相等
func instancesEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// GetInstances 获取当前服务实例列表（用于调试）
func (r *RedisInstancer) GetInstances() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	instances := make([]string, len(r.instances))
	copy(instances, r.instances)
	return instances
}
