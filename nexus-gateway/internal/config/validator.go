package config

import (
	"fmt"
	"net"
	"os"
	"strconv"
	"time"
)

// ValidateConfig validates the configuration
func (c *Config) Validate() error {
	if err := c.validateServer(); err != nil {
		return fmt.Errorf("server config validation failed: %w", err)
	}

	if err := c.validatePython(); err != nil {
		return fmt.Errorf("python config validation failed: %w", err)
	}

	if err := c.validateRedis(); err != nil {
		return fmt.Errorf("redis config validation failed: %w", err)
	}

	if err := c.validateFile(); err != nil {
		return fmt.Errorf("file config validation failed: %w", err)
	}

	if err := c.validateLogging(); err != nil {
		return fmt.Errorf("logging config validation failed: %w", err)
	}

	if err := c.validateMetrics(); err != nil {
		return fmt.Errorf("metrics config validation failed: %w", err)
	}

	if err := c.validateSecurity(); err != nil {
		return fmt.Errorf("security config validation failed: %w", err)
	}

	return nil
}

func (c *Config) validateServer() error {
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("invalid port: %d", c.Server.Port)
	}

	if c.Server.ReadTimeout < time.Second {
		return fmt.Errorf("read timeout too short: %v", c.Server.ReadTimeout)
	}

	if c.Server.WriteTimeout < time.Second {
		return fmt.Errorf("write timeout too short: %v", c.Server.WriteTimeout)
	}

	return nil
}

func (c *Config) validatePython() error {
	if c.Python.Host == "" {
		return fmt.Errorf("python host is required")
	}

	if net.ParseIP(c.Python.Host) == nil {
		// Try to resolve hostname
		if _, err := net.LookupHost(c.Python.Host); err != nil {
			return fmt.Errorf("invalid python host: %s", c.Python.Host)
		}
	}

	if c.Python.Port < 1 || c.Python.Port > 65535 {
		return fmt.Errorf("invalid python port: %d", c.Python.Port)
	}

	if c.Python.Timeout < time.Second {
		return fmt.Errorf("python timeout too short: %v", c.Python.Timeout)
	}

	return nil
}

func (c *Config) validateRedis() error {
	if c.Redis.Host == "" {
		return fmt.Errorf("redis host is required")
	}

	if c.Redis.Port < 1 || c.Redis.Port > 65535 {
		return fmt.Errorf("invalid redis port: %d", c.Redis.Port)
	}

	if c.Redis.DB < 0 {
		return fmt.Errorf("invalid redis db: %d", c.Redis.DB)
	}

	if c.Redis.PoolSize < 1 {
		return fmt.Errorf("redis pool size must be > 0: %d", c.Redis.PoolSize)
	}

	return nil
}

func (c *Config) validateFile() error {
	if c.File.Workers < 1 {
		return fmt.Errorf("file workers must be > 0: %d", c.File.Workers)
	}

	if c.File.QueueSize < 1 {
		return fmt.Errorf("file queue size must be > 0: %d", c.File.QueueSize)
	}

	// Validate allowed paths exist
	for _, path := range c.File.AllowedPaths {
		if _, err := os.Stat(path); os.IsNotExist(err) {
			// Allow non-existent paths, they might be created at runtime
			continue
		}
	}

	return nil
}

func (c *Config) validateLogging() error {
	validLevels := map[string]bool{
		"debug": true,
		"info":  true,
		"warn":  true,
		"error": true,
		"fatal": true,
	}

	if !validLevels[c.Logging.Level] {
		return fmt.Errorf("invalid log level: %s", c.Logging.Level)
	}

	validFormats := map[string]bool{
		"json": true,
		"text": true,
	}

	if !validFormats[c.Logging.Format] {
		return fmt.Errorf("invalid log format: %s", c.Logging.Format)
	}

	return nil
}

func (c *Config) validateMetrics() error {
	if c.Metrics.Port < 1 || c.Metrics.Port > 65535 {
		return fmt.Errorf("invalid metrics port: %d", c.Metrics.Port)
	}

	if c.Metrics.HealthInterval < time.Second {
		return fmt.Errorf("health interval too short: %v", c.Metrics.HealthInterval)
	}

	return nil
}

func (c *Config) validateSecurity() error {
	if c.Security.RateLimitRequests < 0 {
		return fmt.Errorf("rate limit requests cannot be negative: %d", c.Security.RateLimitRequests)
	}

	if c.Security.RateLimitWindow < time.Second {
		return fmt.Errorf("rate limit window too short: %v", c.Security.RateLimitWindow)
	}

	if c.Security.RequestTimeout < time.Second {
		return fmt.Errorf("request timeout too short: %v", c.Security.RequestTimeout)
	}

	return nil
}

// ValidateEnv validates environment-specific requirements
func (c *Config) ValidateEnv() error {
	// Check required environment variables
	requiredEnvs := map[string]string{
		"API_GATEWAY_PORT": strconv.Itoa(c.Server.Port),
	}

	for env, expected := range requiredEnvs {
		if actual := os.Getenv(env); actual != "" && actual != expected {
			return fmt.Errorf("environment variable %s mismatch: expected %s, got %s", env, expected, actual)
		}
	}

	return nil
}

// SanitizeConfig sanitizes sensitive information from config for logging
func (c *Config) SanitizeConfig() *Config {
	sanitized := *c

	// Remove sensitive information
	if sanitized.Redis.Password != "" {
		sanitized.Redis.Password = "***"
	}

	return &sanitized
}
