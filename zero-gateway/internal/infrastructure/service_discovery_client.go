package infrastructure

import (
	"context"
	"fmt"
	"io"
	"net/url"
	"sync"
	"time"

	"github.com/go-kit/kit/endpoint"
	"github.com/go-kit/kit/sd"
	"github.com/go-kit/kit/sd/lb"
	kitlog "github.com/go-kit/log"
	"go.uber.org/zap"

	"zero-gateway/internal/config"
)

// ServiceInfo 服务信息（避免循环导入）
type ServiceInfo struct {
	ID           string
	Name         string
	Address      string
	Port         int
	Protocol     string
	HealthCheck  string
	Metadata     map[string]string
	RegisteredAt time.Time
	LastSeen     time.Time
	TTL          time.Duration
}

// ServiceDiscoveryInterface 服务发现接口（避免循环导入）
type ServiceDiscoveryInterface interface {
	DiscoverServices(ctx context.Context, serviceName string) ([]*ServiceInfo, error)
}

// LoadBalanceStrategy 负载均衡策略类型
type LoadBalanceStrategy string

const (
	StrategyRoundRobin    LoadBalanceStrategy = "round_robin"
	StrategyLeastConn     LoadBalanceStrategy = "least_conn"
	StrategyRandom        LoadBalanceStrategy = "random"
	StrategyWeightedRound LoadBalanceStrategy = "weighted_round"
)

// ServiceSelector 服务选择器
type ServiceSelector struct {
	strategy LoadBalanceStrategy
	mu       sync.Mutex
	index    map[string]int
	conns    map[string]int
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

	// 过滤健康的服务
	healthyServices := make([]*ServiceInfo, 0)
	now := time.Now()
	for _, svc := range services {
		if now.Sub(svc.LastSeen) < 30*time.Second {
			healthyServices = append(healthyServices, svc)
		}
	}

	if len(healthyServices) == 0 {
		return services[0] // 降级策略
	}

	switch ss.strategy {
	case StrategyRoundRobin:
		return ss.selectRoundRobin(healthyServices)
	case StrategyLeastConn:
		return ss.selectLeastConn(healthyServices)
	case StrategyRandom:
		return ss.selectRandom(healthyServices)
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
	return services[time.Now().UnixNano()%int64(len(services))]
}

// ServiceDiscoveryClient 服务发现客户端，用于自动发现和负载均衡 Agent 实例
// 使用 go-kit 的负载均衡器实现
type ServiceDiscoveryClient struct {
	discovery      ServiceDiscoveryInterface // 保留用于获取服务详细信息
	config         *config.Config
	logger         *zap.Logger
	serviceName    string
	strategy       LoadBalanceStrategy
	mu             sync.RWMutex
	cachedServices []*ServiceInfo
	lastRefresh    time.Time
	balancer       lb.Balancer  // go-kit 负载均衡器
	instancer      sd.Instancer // go-kit 服务实例发现器
	stopChan       chan struct{}
}

// NewServiceDiscoveryClient 创建服务发现客户端（使用 go-kit 负载均衡器）
func NewServiceDiscoveryClient(
	instancer sd.Instancer,
	cfg *config.Config,
	logger *zap.Logger,
) *ServiceDiscoveryClient {
	serviceName := cfg.Python.ServiceName
	if serviceName == "" {
		serviceName = "zero-agent"
	}

	strategy := LoadBalanceStrategy(cfg.Python.LoadBalanceStrategy)
	if strategy == "" {
		strategy = StrategyRoundRobin
	}

	// 创建工厂函数：将实例 URL 字符串转换为 endpoint
	// 对于 HTTP 客户端，我们只需要返回实例 URL 字符串
	factory := func(instance string) (endpoint.Endpoint, io.Closer, error) {
		return func(ctx context.Context, request interface{}) (interface{}, error) {
			// 返回实例 URL，供调用者使用
			return instance, nil
		}, nil, nil
	}

	// 创建 go-kit logger 适配器（从 zap.Logger）
	kitLogger := newKitLoggerAdapter(logger)

	// 从 Instancer 创建 Endpointer
	endpointer := sd.NewEndpointer(instancer, factory, kitLogger)

	// 根据策略创建 go-kit 负载均衡器
	var balancer lb.Balancer
	switch strategy {
	case StrategyRoundRobin:
		balancer = lb.NewRoundRobin(endpointer)
	case StrategyRandom:
		balancer = lb.NewRandom(endpointer, time.Now().UnixNano())
	default:
		// 默认使用轮询
		balancer = lb.NewRoundRobin(endpointer)
	}

	sdc := &ServiceDiscoveryClient{
		config:         cfg,
		logger:         logger,
		serviceName:    serviceName,
		strategy:       strategy,
		balancer:       balancer,
		instancer:      instancer,
		stopChan:       make(chan struct{}),
		cachedServices: make([]*ServiceInfo, 0),
	}

	logger.Info("Service discovery client initialized with go-kit load balancer",
		zap.String("service_name", serviceName),
		zap.String("strategy", string(strategy)),
	)

	return sdc
}

// GetService 获取一个可用的服务实例（带负载均衡）
// 使用 go-kit 的负载均衡器选择实例
func (sdc *ServiceDiscoveryClient) GetService(ctx context.Context) (*ServiceInfo, error) {
	// 使用 go-kit 的负载均衡器获取端点
	ep, err := sdc.balancer.Endpoint()
	if err != nil {
		return nil, fmt.Errorf("failed to get endpoint from balancer: %w", err)
	}

	// 调用端点获取实例 URL
	result, err := ep(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get instance from endpoint: %w", err)
	}

	// result 应该是实例的 URL 字符串
	instanceURL, ok := result.(string)
	if !ok {
		return nil, fmt.Errorf("endpoint returned unexpected type: %T", result)
	}

	// 解析 URL 获取地址和端口
	parsedURL, err := url.Parse(instanceURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse instance URL: %w", err)
	}

	host := parsedURL.Hostname()
	port := parsedURL.Port()
	if port == "" {
		// 如果没有端口，使用默认 HTTP 端口
		port = "80"
	}

	// 从缓存中查找对应的服务信息（用于获取完整信息）
	sdc.mu.RLock()
	var service *ServiceInfo
	for _, svc := range sdc.cachedServices {
		if svc.Address == host && fmt.Sprintf("%d", svc.Port) == port {
			service = svc
			break
		}
	}
	sdc.mu.RUnlock()

	// 如果缓存中没有，创建一个基本的服务信息
	if service == nil {
		service = &ServiceInfo{
			Address:  host,
			Port:     parsePort(port),
			Protocol: "http",
		}
	}

	// 记录选择的实例（用于调试）
	sdc.logger.Debug("Selected service instance via go-kit balancer",
		zap.String("instance_url", instanceURL),
		zap.String("address", fmt.Sprintf("%s:%s", host, port)),
		zap.String("strategy", string(sdc.strategy)))

	return service, nil
}

// parsePort 解析端口字符串为整数
func parsePort(portStr string) int {
	var port int
	fmt.Sscanf(portStr, "%d", &port)
	if port == 0 {
		port = 80 // 默认端口
	}
	return port
}

// kitLoggerAdapter 将 zap.Logger 适配为 go-kit/log.Logger
type kitLoggerAdapter struct {
	logger *zap.Logger
}

func newKitLoggerAdapter(logger *zap.Logger) kitlog.Logger {
	return &kitLoggerAdapter{logger: logger}
}

func (k *kitLoggerAdapter) Log(keyvals ...interface{}) error {
	if len(keyvals) == 0 {
		return nil
	}

	// 将 keyvals 转换为 zap fields
	fields := make([]zap.Field, 0, len(keyvals)/2)
	for i := 0; i < len(keyvals)-1; i += 2 {
		key, ok := keyvals[i].(string)
		if !ok {
			continue
		}
		value := keyvals[i+1]
		fields = append(fields, zap.Any(key, value))
	}

	k.logger.Debug("go-kit log", fields...)
	return nil
}

// GetAllServices 获取所有可用的服务实例
func (sdc *ServiceDiscoveryClient) GetAllServices(ctx context.Context) ([]*ServiceInfo, error) {
	sdc.mu.RLock()
	defer sdc.mu.RUnlock()

	if len(sdc.cachedServices) == 0 {
		sdc.mu.RUnlock()
		sdc.refreshServices(ctx)
		sdc.mu.RLock()
	}

	services := make([]*ServiceInfo, len(sdc.cachedServices))
	copy(services, sdc.cachedServices)

	return services, nil
}

// refreshServices 刷新服务列表（用于缓存服务详细信息）
func (sdc *ServiceDiscoveryClient) refreshServices(ctx context.Context) {
	if sdc.discovery == nil {
		return
	}

	sdc.mu.Lock()
	defer sdc.mu.Unlock()

	services, err := sdc.discovery.DiscoverServices(ctx, sdc.serviceName)
	if err != nil {
		sdc.logger.Warn("Failed to discover services", zap.Error(err))
		return
	}

	// 过滤健康的服务
	now := time.Now()
	healthyServices := make([]*ServiceInfo, 0)
	for _, svc := range services {
		if now.Sub(svc.LastSeen) < 30*time.Second {
			healthyServices = append(healthyServices, svc)
		}
	}

	sdc.cachedServices = healthyServices
	sdc.lastRefresh = now

	if len(healthyServices) > 0 {
		sdc.logger.Debug(
			"Services refreshed",
			zap.String("service_name", sdc.serviceName),
			zap.Int("count", len(healthyServices)),
		)
	} else {
		sdc.logger.Warn(
			"No healthy services found",
			zap.String("service_name", sdc.serviceName),
		)
	}
}

// Stop 停止服务发现客户端
func (sdc *ServiceDiscoveryClient) Stop() {
	close(sdc.stopChan)
	if sdc.instancer != nil {
		// 如果 instancer 实现了 Stop 方法，调用它
		if stopper, ok := sdc.instancer.(interface{ Stop() }); ok {
			stopper.Stop()
		}
	}
	sdc.logger.Info("Service discovery client stopped")
}

// BuildURL 根据服务信息构建 URL
func (sdc *ServiceDiscoveryClient) BuildURL(service *ServiceInfo, path string) string {
	return fmt.Sprintf("http://%s:%d%s", service.Address, service.Port, path)
}
