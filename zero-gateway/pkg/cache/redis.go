package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

// RedisCache implements a Redis-based cache
type RedisCache struct {
	client *redis.Client
}

// NewRedisCache creates a new Redis cache instance
func NewRedisCache(host string, port int, password string, db int, poolSize int) (*RedisCache, error) {
	// 计算最小空闲连接数，至少为池大小的 20%，但不少于 5
	minIdleConns := poolSize / 5
	if minIdleConns < 5 {
		minIdleConns = 5
	}
	
	client := redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%d", host, port),
		Password:     password,
		DB:           db,
		PoolSize:     poolSize,
		MinIdleConns: minIdleConns, // 动态计算最小空闲连接数
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolTimeout:  4 * time.Second, // 连接池获取连接的超时时间
		IdleTimeout:  5 * time.Minute,  // 空闲连接超时时间
		IdleCheckFrequency: 1 * time.Minute, // 检查空闲连接的频率
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if _, err := client.Ping(ctx).Result(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &RedisCache{
		client: client,
	}, nil
}

// Set stores a value in cache with expiration
func (c *RedisCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal value: %w", err)
	}

	return c.client.Set(ctx, key, data, expiration).Err()
}

// Get retrieves a value from cache
func (c *RedisCache) Get(ctx context.Context, key string, dest interface{}) error {
	data, err := c.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return fmt.Errorf("key not found")
		}
		return fmt.Errorf("failed to get value: %w", err)
	}

	return json.Unmarshal([]byte(data), dest)
}

// Delete removes a key from cache
func (c *RedisCache) Delete(ctx context.Context, key string) error {
	return c.client.Del(ctx, key).Err()
}

// Exists checks if a key exists
func (c *RedisCache) Exists(ctx context.Context, key string) (bool, error) {
	count, err := c.client.Exists(ctx, key).Result()
	return count > 0, err
}

// SetSession stores session data
func (c *RedisCache) SetSession(ctx context.Context, sessionID string, data interface{}) error {
	key := fmt.Sprintf("session:%s", sessionID)
	return c.Set(ctx, key, data, 24*time.Hour) // 24 hour expiration
}

// GetSession retrieves session data
func (c *RedisCache) GetSession(ctx context.Context, sessionID string, dest interface{}) error {
	key := fmt.Sprintf("session:%s", sessionID)
	return c.Get(ctx, key, dest)
}

// DeleteSession removes session data
func (c *RedisCache) DeleteSession(ctx context.Context, sessionID string) error {
	key := fmt.Sprintf("session:%s", sessionID)
	return c.Delete(ctx, key)
}

// SetCache stores general cache data
func (c *RedisCache) SetCache(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	cacheKey := fmt.Sprintf("cache:%s", key)
	return c.Set(ctx, cacheKey, value, expiration)
}

// GetCache retrieves general cache data
func (c *RedisCache) GetCache(ctx context.Context, key string, dest interface{}) error {
	cacheKey := fmt.Sprintf("cache:%s", key)
	return c.Get(ctx, cacheKey, dest)
}

// SetWithTags stores a value with tags for batch operations
func (c *RedisCache) SetWithTags(ctx context.Context, key string, value interface{}, tags []string, expiration time.Duration) error {
	// Store the main value
	if err := c.Set(ctx, key, value, expiration); err != nil {
		return err
	}

	// Store tag relationships
	for _, tag := range tags {
		tagKey := fmt.Sprintf("tag:%s", tag)
		if err := c.client.SAdd(ctx, tagKey, key).Err(); err != nil {
			return fmt.Errorf("failed to add tag: %w", err)
		}
		// Set expiration for tag set
		c.client.Expire(ctx, tagKey, expiration)
	}

	return nil
}

// DeleteByTag deletes all keys with a specific tag
func (c *RedisCache) DeleteByTag(ctx context.Context, tag string) error {
	tagKey := fmt.Sprintf("tag:%s", tag)

	// Get all keys with this tag
	keys, err := c.client.SMembers(ctx, tagKey).Result()
	if err != nil {
		return fmt.Errorf("failed to get tag members: %w", err)
	}

	// Delete all keys
	if len(keys) > 0 {
		if err := c.client.Del(ctx, keys...).Err(); err != nil {
			return fmt.Errorf("failed to delete keys: %w", err)
		}
	}

	// Delete the tag set
	return c.client.Del(ctx, tagKey).Err()
}

// Close closes the Redis connection
func (c *RedisCache) Close() error {
	return c.client.Close()
}

// GetClient returns the underlying Redis client (for advanced operations)
func (c *RedisCache) GetClient() *redis.Client {
	return c.client
}

// Health checks Redis connectivity
func (c *RedisCache) Health(ctx context.Context) error {
	return c.client.Ping(ctx).Err()
}
