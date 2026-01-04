package cache

import (
	"context"
	"fmt"
	"time"
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

// DiscoverService finds a service by name
func (sd *ServiceDiscovery) DiscoverService(ctx context.Context, serviceName string) (*ServiceInfo, error) {
	// Get all instances of this service
	pattern := fmt.Sprintf("service:%s:*", serviceName)
	keys, err := sd.cache.GetClient().Keys(ctx, pattern).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to discover service: %w", err)
	}

	if len(keys) == 0 {
		return nil, fmt.Errorf("service not found: %s", serviceName)
	}

	// For now, return the first available service
	// In production, you might implement load balancing
	var service ServiceInfo
	if err := sd.cache.Get(ctx, keys[0], &service); err != nil {
		return nil, fmt.Errorf("failed to get service info: %w", err)
	}

	return &service, nil
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
