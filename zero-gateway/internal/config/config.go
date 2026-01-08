// Package config manages application configuration
package config

import (
	"fmt"
	"time"

	"github.com/spf13/viper"
)

// Config holds all configuration for the application
type Config struct {
	Server   ServerConfig   `mapstructure:"server"`
	Python   PythonConfig   `mapstructure:"python"`
	Redis    RedisConfig    `mapstructure:"redis"`
	File     FileConfig     `mapstructure:"file"`
	Logging  LoggingConfig  `mapstructure:"logging"`
	Metrics  MetricsConfig  `mapstructure:"metrics"`
	Security SecurityConfig `mapstructure:"security"`
}

// ServerConfig holds server-related configuration
type ServerConfig struct {
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
	IdleTimeout  time.Duration `mapstructure:"idle_timeout"`
}

// PythonConfig holds Python agent service configuration
type PythonConfig struct {
	Host                string        `mapstructure:"host"`
	Port                int           `mapstructure:"port"`
	Timeout             time.Duration `mapstructure:"timeout"`
	InsecureSkipVerify  bool          `mapstructure:"insecure_skip_verify"`
	MaxIdleConns        int           `mapstructure:"max_idle_conns"`          // 最大空闲连接数
	MaxIdleConnsPerHost int           `mapstructure:"max_idle_conns_per_host"` // 每个主机的最大空闲连接数
	MaxConnsPerHost     int           `mapstructure:"max_conns_per_host"`      // 每个主机的最大连接数
	IdleConnTimeout     time.Duration `mapstructure:"idle_conn_timeout"`       // 空闲连接超时时间
	UseServiceDiscovery bool          `mapstructure:"use_service_discovery"`   // 是否使用服务发现
	ServiceName         string        `mapstructure:"service_name"`            // 服务名称
	LoadBalanceStrategy string        `mapstructure:"load_balance_strategy"`   // 负载均衡策略
}

// RedisConfig holds Redis configuration
type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
	PoolSize int    `mapstructure:"pool_size"`
}

// FileConfig holds file service configuration
type FileConfig struct {
	MaxSize      string   `mapstructure:"max_size"`
	Workers      int      `mapstructure:"workers"`
	QueueSize    int      `mapstructure:"queue_size"`
	AllowedPaths []string `mapstructure:"allowed_paths"`
	TempDir      string   `mapstructure:"temp_dir"`
}

// LoggingConfig holds logging configuration
type LoggingConfig struct {
	Level      string `mapstructure:"level"`
	Format     string `mapstructure:"format"`
	OutputFile string `mapstructure:"output_file"` // 日志文件路径，为空则输出到 stderr
	LogDir     string `mapstructure:"log_dir"`     // 日志目录（如果 output_file 是相对路径）
}

// MetricsConfig holds metrics configuration
type MetricsConfig struct {
	Port           int           `mapstructure:"port"`
	Path           string        `mapstructure:"path"`
	HealthInterval time.Duration `mapstructure:"health_interval"`
}

// SecurityConfig holds security-related configuration
type SecurityConfig struct {
	RateLimitRequests int                  `mapstructure:"rate_limit_requests"`
	RateLimitWindow   time.Duration        `mapstructure:"rate_limit_window"`
	RequestTimeout    time.Duration        `mapstructure:"request_timeout"`
	MaxRequestSize    string               `mapstructure:"max_request_size"`
	CORSOrigins       []string             `mapstructure:"cors_origins"`
	CircuitBreaker    CircuitBreakerConfig `mapstructure:"circuit_breaker"`
}

// CircuitBreakerConfig holds circuit breaker configuration
type CircuitBreakerConfig struct {
	Enabled               bool          `mapstructure:"enabled"`                 // 是否启用熔断器
	UserFailureThreshold  int           `mapstructure:"user_failure_threshold"`  // 用户级失败阈值
	UserSuccessThreshold  int           `mapstructure:"user_success_threshold"`  // 用户级成功阈值
	UserTimeout           time.Duration `mapstructure:"user_timeout"`            // 用户级熔断超时
	AgentFailureThreshold int           `mapstructure:"agent_failure_threshold"` // Agent级失败阈值
	AgentSuccessThreshold int           `mapstructure:"agent_success_threshold"` // Agent级成功阈值
	AgentTimeout          time.Duration `mapstructure:"agent_timeout"`           // Agent级熔断超时
}

// Load loads configuration from environment variables and config files
func Load() (*Config, error) {
	// Set defaults
	setDefaults()

	// Environment variable bindings
	bindEnvVars()

	// Config file (optional)
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AddConfigPath("./config")

	// Read config
	if err := viper.ReadInConfig(); err != nil {
		// Config file is optional, so ignore not found errors
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, err
		}
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, err
	}

	// Validate configuration
	if err := config.Validate(); err != nil {
		return nil, fmt.Errorf("configuration validation failed: %w", err)
	}

	return &config, nil
}

// LoadAndValidate loads and validates configuration
func LoadAndValidate() (*Config, error) {
	config, err := Load()
	if err != nil {
		return nil, err
	}

	// Validate environment
	if err := config.ValidateEnv(); err != nil {
		return nil, fmt.Errorf("environment validation failed: %w", err)
	}

	return config, nil
}

func setDefaults() {
	// Server defaults
	viper.SetDefault("server.port", 8080)
	viper.SetDefault("server.read_timeout", "30s")
	viper.SetDefault("server.write_timeout", "30s")
	viper.SetDefault("server.idle_timeout", "60s")

	// Python service defaults
	viper.SetDefault("python.host", "localhost")
	viper.SetDefault("python.port", 8082)
	viper.SetDefault("python.timeout", "5m") // 5分钟超时
	viper.SetDefault("python.insecure_skip_verify", true)
	viper.SetDefault("python.max_idle_conns", 100)                  // 最大空闲连接数
	viper.SetDefault("python.max_idle_conns_per_host", 20)          // 每个主机的最大空闲连接数
	viper.SetDefault("python.max_conns_per_host", 50)               // 每个主机的最大连接数
	viper.SetDefault("python.idle_conn_timeout", "90s")             // 空闲连接超时时间
	viper.SetDefault("python.use_service_discovery", false)         // 是否使用服务发现
	viper.SetDefault("python.service_name", "zero-agent")           // 服务名称
	viper.SetDefault("python.load_balance_strategy", "round_robin") // 负载均衡策略

	// Redis defaults
	viper.SetDefault("redis.host", "localhost")
	viper.SetDefault("redis.port", 6379)
	viper.SetDefault("redis.password", "")
	viper.SetDefault("redis.db", 0)
	viper.SetDefault("redis.pool_size", 50) // 从 10 提升到 50，支持更高并发

	// File service defaults
	viper.SetDefault("file.max_size", "100MB")
	viper.SetDefault("file.workers", 100)
	viper.SetDefault("file.queue_size", 1000)
	viper.SetDefault("file.allowed_paths", []string{"/tmp"})
	viper.SetDefault("file.temp_dir", "/tmp/zero-agent")

	// Logging defaults
	viper.SetDefault("logging.level", "info")
	viper.SetDefault("logging.format", "json")

	// Metrics defaults
	viper.SetDefault("metrics.port", 9090)
	viper.SetDefault("metrics.path", "/metrics")
	viper.SetDefault("metrics.health_interval", "30s")

	// Security defaults
	viper.SetDefault("security.rate_limit_requests", 100)
	viper.SetDefault("security.rate_limit_window", "1m")
	viper.SetDefault("security.request_timeout", "30s")
	viper.SetDefault("security.max_request_size", "10MB")
	viper.SetDefault("security.cors_origins", []string{"*"})

	// Circuit breaker defaults
	viper.SetDefault("security.circuit_breaker.enabled", true)
	viper.SetDefault("security.circuit_breaker.user_failure_threshold", 3)   // 用户级：3次失败就熔断
	viper.SetDefault("security.circuit_breaker.user_success_threshold", 1)   // 用户级：1次成功就恢复
	viper.SetDefault("security.circuit_breaker.user_timeout", "30s")         // 用户级：30秒后尝试恢复
	viper.SetDefault("security.circuit_breaker.agent_failure_threshold", 10) // Agent级：10次失败才熔断
	viper.SetDefault("security.circuit_breaker.agent_success_threshold", 3)  // Agent级：3次成功才恢复
	viper.SetDefault("security.circuit_breaker.agent_timeout", "60s")        // Agent级：60秒后尝试恢复
}

func bindEnvVars() {
	// Server environment bindings
	viper.BindEnv("server.port", "FILE_SERVICE_PORT")

	// Python service bindings
	viper.BindEnv("python.host", "PYTHON_AGENT_HOST")
	viper.BindEnv("python.port", "PYTHON_AGENT_PORT")
	viper.BindEnv("python.timeout", "PYTHON_AGENT_TIMEOUT")
	viper.BindEnv("python.insecure_skip_verify", "PYTHON_INSECURE_SKIP_VERIFY")
	viper.BindEnv("python.max_idle_conns", "PYTHON_MAX_IDLE_CONNS")
	viper.BindEnv("python.max_idle_conns_per_host", "PYTHON_MAX_IDLE_CONNS_PER_HOST")
	viper.BindEnv("python.max_conns_per_host", "PYTHON_MAX_CONNS_PER_HOST")
	viper.BindEnv("python.idle_conn_timeout", "PYTHON_IDLE_CONN_TIMEOUT")
	viper.BindEnv("python.use_service_discovery", "PYTHON_USE_SERVICE_DISCOVERY")
	viper.BindEnv("python.service_name", "PYTHON_SERVICE_NAME")
	viper.BindEnv("python.load_balance_strategy", "PYTHON_LOAD_BALANCE_STRATEGY")

	// Redis bindings
	viper.BindEnv("redis.host", "REDIS_HOST")
	viper.BindEnv("redis.port", "REDIS_PORT")
	viper.BindEnv("redis.password", "REDIS_PASSWORD")

	// Logging bindings
	viper.BindEnv("logging.level", "LOG_LEVEL")
	viper.BindEnv("logging.format", "LOG_FORMAT")
	viper.BindEnv("logging.output_file", "LOG_FILE")
	viper.BindEnv("logging.log_dir", "LOG_DIR")

	// File service bindings
	viper.BindEnv("file.workers", "FILE_WORKERS")
	viper.BindEnv("file.max_size", "FILE_MAX_SIZE")
}
