package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"sync"
	"time"

	"zero-gateway/internal/infrastructure"
)

// ServiceInfo represents service registration information
type ServiceInfo struct {
	ID           string            `json:"id"`
	Name         string            `json:"name"`
	Address      string            `json:"address"`
	Port         int               `json:"port"`
	Protocol     string            `json:"protocol"` // "grpc", "http"
	HealthCheck  string            `json:"health_check"`
	Metadata     map[string]string `json:"metadata"`
	RegisteredAt time.Time         `json:"registered_at"`
	LastSeen     time.Time         `json:"last_seen"`
	TTL          time.Duration     `json:"ttl"`
}

// UnmarshalJSON 自定义 JSON 反序列化，处理 ISO 8601 时间格式
func (s *ServiceInfo) UnmarshalJSON(data []byte) error {
	// 使用临时结构体来解析 JSON
	type Alias ServiceInfo
	aux := &struct {
		RegisteredAt string `json:"registered_at"`
		LastSeen     string `json:"last_seen"`
		*Alias
	}{
		Alias: (*Alias)(s),
	}

	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	// 解析时间字符串（支持 ISO 8601 格式）
	// Python datetime.utcnow().isoformat() 格式: "2026-01-08T17:23:38.960110"
	// 尝试多种时间格式
	timeFormats := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.999999",
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
	}

	if aux.RegisteredAt != "" {
		var err error
		for _, format := range timeFormats {
			s.RegisteredAt, err = time.Parse(format, aux.RegisteredAt)
			if err == nil {
				break
			}
		}
		if err != nil {
			// 如果所有格式都失败，记录警告但继续
			s.RegisteredAt = time.Now()
		}
	}

	if aux.LastSeen != "" {
		var err error
		for _, format := range timeFormats {
			s.LastSeen, err = time.Parse(format, aux.LastSeen)
			if err == nil {
				break
			}
		}
		if err != nil {
			// 如果所有格式都失败，使用当前时间
			s.LastSeen = time.Now()
		}
	}

	return nil
}

// ServiceDiscovery manages service registration and discovery
type ServiceDiscovery struct {
	cache *RedisCache
}

// NewServiceDiscovery creates a new service discovery instance
func NewServiceDiscovery(cache *RedisCache) *ServiceDiscovery {
	return &ServiceDiscovery{
		cache: cache,
	}
}

// RegisterService registers a service
func (sd *ServiceDiscovery) RegisterService(ctx context.Context, info *ServiceInfo) error {
	key := fmt.Sprintf("service:%s:%s", info.Name, info.ID)

	info.RegisteredAt = time.Now()
	info.LastSeen = time.Now()

	return sd.cache.Set(ctx, key, info, info.TTL)
}

// UnregisterService removes a service registration
func (sd *ServiceDiscovery) UnregisterService(ctx context.Context, serviceName, serviceID string) error {
	key := fmt.Sprintf("service:%s:%s", serviceName, serviceID)
	return sd.cache.Delete(ctx, key)
}

// LoadBalanceStrategy 负载均衡策略类型
type LoadBalanceStrategy string

const (
	StrategyRoundRobin    LoadBalanceStrategy = "round_robin"    // 轮询
	StrategyLeastConn     LoadBalanceStrategy = "least_conn"     // 最少连接
	StrategyRandom        LoadBalanceStrategy = "random"         // 随机
	StrategyWeightedRound LoadBalanceStrategy = "weighted_round" // 加权轮询
)

// ServiceSelector 服务选择器，用于负载均衡
type ServiceSelector struct {
	strategy LoadBalanceStrategy
	mu       sync.Mutex
	index    map[string]int // 用于轮询策略的索引
	conns    map[string]int // 用于最少连接策略的连接数
}

// NewServiceSelector 创建服务选择器
func NewServiceSelector(strategy LoadBalanceStrategy) *ServiceSelector {
	return &ServiceSelector{
		strategy: strategy,
		index:    make(map[string]int),
		conns:    make(map[string]int),
	}
}

// Select 根据策略选择一个服务实例
func (ss *ServiceSelector) Select(services []*ServiceInfo) *ServiceInfo {
	if len(services) == 0 {
		return nil
	}

	// 过滤健康的服务（LastSeen 在最近 30 秒内）
	healthyServices := make([]*ServiceInfo, 0)
	now := time.Now()
	for _, svc := range services {
		if now.Sub(svc.LastSeen) < 30*time.Second {
			healthyServices = append(healthyServices, svc)
		}
	}

	if len(healthyServices) == 0 {
		// 如果没有健康服务，返回第一个（降级策略）
		return services[0]
	}

	switch ss.strategy {
	case StrategyRoundRobin:
		return ss.selectRoundRobin(healthyServices)
	case StrategyLeastConn:
		return ss.selectLeastConn(healthyServices)
	case StrategyRandom:
		return ss.selectRandom(healthyServices)
	case StrategyWeightedRound:
		return ss.selectWeightedRound(healthyServices)
	default:
		return ss.selectRoundRobin(healthyServices)
	}
}

func (ss *ServiceSelector) selectRoundRobin(services []*ServiceInfo) *ServiceInfo {
	ss.mu.Lock()
	defer ss.mu.Unlock()

	key := services[0].Name
	idx := ss.index[key] % len(services)
	ss.index[key] = (ss.index[key] + 1) % len(services)

	return services[idx]
}

func (ss *ServiceSelector) selectLeastConn(services []*ServiceInfo) *ServiceInfo {
	ss.mu.Lock()
	defer ss.mu.Unlock()

	if len(services) == 0 {
		return nil
	}

	selected := services[0]
	minConns := ss.conns[selected.ID]

	for _, svc := range services[1:] {
		conns := ss.conns[svc.ID]
		if conns < minConns {
			minConns = conns
			selected = svc
		}
	}

	ss.conns[selected.ID]++
	return selected
}

func (ss *ServiceSelector) selectRandom(services []*ServiceInfo) *ServiceInfo {
	return services[rand.Intn(len(services))]
}

func (ss *ServiceSelector) selectWeightedRound(services []*ServiceInfo) *ServiceInfo {
	// 简单实现：根据权重选择（权重存储在 Metadata 中）
	// 如果没有权重，使用轮询
	return ss.selectRoundRobin(services)
}

// Release 释放连接（用于最少连接策略）
func (ss *ServiceSelector) Release(serviceID string) {
	ss.mu.Lock()
	defer ss.mu.Unlock()

	if conns := ss.conns[serviceID]; conns > 0 {
		ss.conns[serviceID]--
	}
}

// DiscoverService finds a service by name with load balancing
func (sd *ServiceDiscovery) DiscoverService(ctx context.Context, serviceName string) (*ServiceInfo, error) {
	services, err := sd.DiscoverServices(ctx, serviceName)
	if err != nil {
		return nil, err
	}

	if len(services) == 0 {
		return nil, fmt.Errorf("service not found: %s", serviceName)
	}

	// 使用轮询策略作为默认策略
	selector := NewServiceSelector(StrategyRoundRobin)
	return selector.Select(services), nil
}

// DiscoverServiceWithStrategy finds a service with specified load balance strategy
func (sd *ServiceDiscovery) DiscoverServiceWithStrategy(ctx context.Context, serviceName string, strategy LoadBalanceStrategy) (*ServiceInfo, error) {
	services, err := sd.DiscoverServices(ctx, serviceName)
	if err != nil {
		return nil, err
	}

	if len(services) == 0 {
		return nil, fmt.Errorf("service not found: %s", serviceName)
	}

	selector := NewServiceSelector(strategy)
	return selector.Select(services), nil
}

// DiscoverServices finds all instances of a service
func (sd *ServiceDiscovery) DiscoverServices(ctx context.Context, serviceName string) ([]*ServiceInfo, error) {
	pattern := fmt.Sprintf("service:%s:*", serviceName)
	keys, err := sd.cache.GetClient().Keys(ctx, pattern).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to discover services: %w", err)
	}

	var services []*ServiceInfo
	for _, key := range keys {
		var service ServiceInfo
		if err := sd.cache.Get(ctx, key, &service); err != nil {
			continue // Skip invalid entries
		}
		services = append(services, &service)
	}

	return services, nil
}

// Heartbeat updates service last seen time
func (sd *ServiceDiscovery) Heartbeat(ctx context.Context, serviceName, serviceID string) error {
	key := fmt.Sprintf("service:%s:%s", serviceName, serviceID)

	var service ServiceInfo
	if err := sd.cache.Get(ctx, key, &service); err != nil {
		return fmt.Errorf("service not found: %w", err)
	}

	service.LastSeen = time.Now()
	return sd.cache.Set(ctx, key, service, service.TTL)
}

// GetAllServices returns all registered services
func (sd *ServiceDiscovery) GetAllServices(ctx context.Context) (map[string][]*ServiceInfo, error) {
	keys, err := sd.cache.GetClient().Keys(ctx, "service:*").Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get services: %w", err)
	}

	services := make(map[string][]*ServiceInfo)
	for _, key := range keys {
		var service ServiceInfo
		if err := sd.cache.Get(ctx, key, &service); err != nil {
			continue
		}

		services[service.Name] = append(services[service.Name], &service)
	}

	return services, nil
}

// CleanupExpiredServices removes expired service registrations
func (sd *ServiceDiscovery) CleanupExpiredServices(ctx context.Context) error {
	// Redis TTL handles automatic cleanup
	// This method could be used for manual cleanup or reporting
	return nil
}

// ServiceRegistry is a global service registry instance
type ServiceRegistry struct {
	discovery *ServiceDiscovery
	services  map[string]*ServiceInfo
}

// NewServiceRegistry creates a new service registry
func NewServiceRegistry(cache *RedisCache) *ServiceRegistry {
	return &ServiceRegistry{
		discovery: NewServiceDiscovery(cache),
		services:  make(map[string]*ServiceInfo),
	}
}

// Register registers the current service
func (sr *ServiceRegistry) Register(ctx context.Context, info *ServiceInfo) error {
	if err := sr.discovery.RegisterService(ctx, info); err != nil {
		return err
	}

	sr.services[info.ID] = info

	// Start heartbeat goroutine
	go sr.startHeartbeat(ctx, info)

	return nil
}

// Unregister unregisters the current service
func (sr *ServiceRegistry) Unregister(ctx context.Context, serviceID string) error {
	info, exists := sr.services[serviceID]
	if !exists {
		return fmt.Errorf("service not registered: %s", serviceID)
	}

	return sr.discovery.UnregisterService(ctx, info.Name, serviceID)
}

// Discover discovers a service
func (sr *ServiceRegistry) Discover(ctx context.Context, serviceName string) (*ServiceInfo, error) {
	return sr.discovery.DiscoverService(ctx, serviceName)
}

func (sr *ServiceRegistry) startHeartbeat(ctx context.Context, info *ServiceInfo) {
	ticker := time.NewTicker(info.TTL / 4) // Heartbeat every 1/4 of TTL
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := sr.discovery.Heartbeat(ctx, info.Name, info.ID); err != nil {
				// Log error but continue
				fmt.Printf("Heartbeat failed for service %s: %v\n", info.ID, err)
			}
		}
	}
}

// ServiceDiscoveryAdapter 适配器，将 cache.ServiceInfo 转换为 infrastructure.ServiceInfo
// 用于避免循环导入
type ServiceDiscoveryAdapter struct {
	sd *ServiceDiscovery
}

// NewServiceDiscoveryAdapter 创建服务发现适配器
func NewServiceDiscoveryAdapter(cache *RedisCache) *ServiceDiscoveryAdapter {
	return &ServiceDiscoveryAdapter{
		sd: NewServiceDiscovery(cache),
	}
}

// DiscoverServices 发现服务并转换为 infrastructure.ServiceInfo
func (a *ServiceDiscoveryAdapter) DiscoverServices(ctx context.Context, serviceName string) ([]*infrastructure.ServiceInfo, error) {
	services, err := a.sd.DiscoverServices(ctx, serviceName)
	if err != nil {
		return nil, err
	}

	result := make([]*infrastructure.ServiceInfo, len(services))
	for i, svc := range services {
		result[i] = &infrastructure.ServiceInfo{
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
		}
	}

	return result, nil
}
