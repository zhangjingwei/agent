package cache

import (
	"fmt"
	"sync"

	"github.com/your-org/nexus-gateway/internal/config"
)

// CacheFactory manages cache instances
type CacheFactory struct {
	caches map[string]interface{}
	mu     sync.RWMutex
}

// NewCacheFactory creates a new cache factory
func NewCacheFactory() *CacheFactory {
	return &CacheFactory{
		caches: make(map[string]interface{}),
	}
}

// GetRedisCache gets or creates a Redis cache instance
func (f *CacheFactory) GetRedisCache(cfg config.RedisConfig) (*RedisCache, error) {
	key := fmt.Sprintf("redis:%s:%d:%d", cfg.Host, cfg.Port, cfg.DB)

	f.mu.RLock()
	if cache, exists := f.caches[key]; exists {
		f.mu.RUnlock()
		if redisCache, ok := cache.(*RedisCache); ok {
			return redisCache, nil
		}
	}
	f.mu.RUnlock()

	f.mu.Lock()
	defer f.mu.Unlock()

	// Double-check after acquiring write lock
	if cache, exists := f.caches[key]; exists {
		if redisCache, ok := cache.(*RedisCache); ok {
			return redisCache, nil
		}
	}

	// Create new instance
	cache, err := NewRedisCache(cfg.Host, cfg.Port, cfg.Password, cfg.DB, cfg.PoolSize)
	if err != nil {
		return nil, fmt.Errorf("failed to create Redis cache: %w", err)
	}

	f.caches[key] = cache
	return cache, nil
}

// GetSessionManager gets or creates a session manager instance
func (f *CacheFactory) GetSessionManager(cfg config.RedisConfig) (*SessionManager, error) {
	key := fmt.Sprintf("session_mgr:%s:%d:%d", cfg.Host, cfg.Port, cfg.DB)

	f.mu.RLock()
	if mgr, exists := f.caches[key]; exists {
		f.mu.RUnlock()
		if sessionMgr, ok := mgr.(*SessionManager); ok {
			return sessionMgr, nil
		}
	}
	f.mu.RUnlock()

	f.mu.Lock()
	defer f.mu.Unlock()

	// Double-check after acquiring write lock
	if mgr, exists := f.caches[key]; exists {
		if sessionMgr, ok := mgr.(*SessionManager); ok {
			return sessionMgr, nil
		}
	}

	// Create Redis cache first
	cache, err := f.GetRedisCache(cfg)
	if err != nil {
		return nil, err
	}

	// Create session manager
	sessionMgr := NewSessionManager(cache)
	f.caches[key] = sessionMgr

	return sessionMgr, nil
}

// Close closes all managed cache instances
func (f *CacheFactory) Close() error {
	f.mu.Lock()
	defer f.mu.Unlock()

	var lastErr error
	for key, cache := range f.caches {
		switch c := cache.(type) {
		case *RedisCache:
			if err := c.Close(); err != nil {
				lastErr = err
			}
		}
		delete(f.caches, key)
	}

	return lastErr
}

// Global cache factory instance
var globalFactory *CacheFactory
var factoryOnce sync.Once

// GetGlobalFactory returns the global cache factory instance
func GetGlobalFactory() *CacheFactory {
	factoryOnce.Do(func() {
		globalFactory = NewCacheFactory()
	})
	return globalFactory
}
