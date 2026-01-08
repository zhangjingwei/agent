package infrastructure

import (
	"context"
	"crypto/tls"
	"fmt"
	"net"
	"net/http"
	"time"

	"go.uber.org/zap"
	"golang.org/x/net/http2"

	"zero-gateway/internal/config"
)

// HTTPClient 封装 HTTP/2 客户端，提供与 Python 服务通信的基础设施
type HTTPClient struct {
	client              *http.Client
	config              *config.PythonConfig
	logger              *zap.Logger
	serviceDiscovery    *ServiceDiscoveryClient
	useServiceDiscovery bool
}

// NewHTTPClient 创建新的 HTTP 客户端
func NewHTTPClient(cfg *config.Config, logger *zap.Logger, serviceDiscovery *ServiceDiscoveryClient) *HTTPClient {
	// 设置连接超时为5秒
	connectionTimeout := 5 * time.Second

	// 创建底层 HTTP Transport，配置连接池参数
	// 然后通过 http2.ConfigureTransport 升级到 HTTP/2
	transport := &http.Transport{
		MaxIdleConns:        cfg.Python.MaxIdleConns,
		MaxIdleConnsPerHost: cfg.Python.MaxIdleConnsPerHost,
		MaxConnsPerHost:     cfg.Python.MaxConnsPerHost,
		IdleConnTimeout:     cfg.Python.IdleConnTimeout,
		DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			dialer := &net.Dialer{
				Timeout:   connectionTimeout,
				KeepAlive: 30 * time.Second, // 保持连接活跃
			}
			return dialer.DialContext(ctx, network, addr)
		},
		DisableKeepAlives: false, // 启用连接复用
		ForceAttemptHTTP2: true,  // 尝试使用 HTTP/2
	}

	// 配置 HTTP/2 支持（h2c - HTTP/2 over cleartext）
	// 注意：http2.ConfigureTransport 主要用于 TLS，对于 h2c 我们需要特殊处理
	// 如果服务器支持 HTTP/2，transport 会自动升级
	// 对于 h2c，我们使用 http2.Transport
	http2Transport := &http2.Transport{
		AllowHTTP: true, // 允许非加密连接（h2c）
		DialTLS: func(network, addr string, tlsCfg *tls.Config) (net.Conn, error) {
			// 使用底层 transport 的 DialContext
			return transport.DialContext(context.Background(), network, addr)
		},
		MaxHeaderListSize: 262144, // 256KB - HTTP/2 最大头部列表大小
	}

	httpClient := &http.Client{
		Transport: http2Transport,
		Timeout:   cfg.Python.Timeout,
	}

	logger.Info("HTTP/2 client initialized with connection pool",
		zap.String("host", cfg.Python.Host),
		zap.Int("port", cfg.Python.Port),
		zap.Duration("timeout", cfg.Python.Timeout),
		zap.Int("max_idle_conns", cfg.Python.MaxIdleConns),
		zap.Int("max_idle_conns_per_host", cfg.Python.MaxIdleConnsPerHost),
		zap.Int("max_conns_per_host", cfg.Python.MaxConnsPerHost),
		zap.Duration("idle_conn_timeout", cfg.Python.IdleConnTimeout),
		zap.String("note", "HTTP/2 uses multiplexing, connection limits are advisory"),
	)

	httpClientInstance := &HTTPClient{
		client:              httpClient,
		config:              &cfg.Python,
		logger:              logger,
		serviceDiscovery:    serviceDiscovery,
		useServiceDiscovery: cfg.Python.UseServiceDiscovery,
	}

	if cfg.Python.UseServiceDiscovery && serviceDiscovery != nil {
		logger.Info("HTTP client initialized with service discovery",
			zap.String("service_name", cfg.Python.ServiceName),
			zap.String("load_balance_strategy", cfg.Python.LoadBalanceStrategy),
		)
	} else {
		logger.Info("HTTP client initialized with static configuration",
			zap.String("host", cfg.Python.Host),
			zap.Int("port", cfg.Python.Port),
		)
	}

	return httpClientInstance
}

// Do 执行 HTTP 请求
func (c *HTTPClient) Do(req *http.Request) (*http.Response, error) {
	return c.client.Do(req)
}

// NewStreamClient 创建用于流式响应的客户端（无超时）
func (c *HTTPClient) NewStreamClient() *http.Client {
	return &http.Client{
		Transport: c.client.Transport,
		Timeout:   0, // 无超时，让流式响应可以持续进行
	}
}

// BuildURL 构建 Python 服务的 URL
func (c *HTTPClient) BuildURL(path string) (string, error) {
	if c.useServiceDiscovery && c.serviceDiscovery != nil {
		// 使用服务发现获取服务实例
		ctx := context.Background()
		service, err := c.serviceDiscovery.GetService(ctx)
		if err != nil {
			return "", fmt.Errorf("failed to discover service: %w", err)
		}
		return c.serviceDiscovery.BuildURL(service, path), nil
	}
	// 使用静态配置
	return fmt.Sprintf("http://%s:%d%s", c.config.Host, c.config.Port, path), nil
}
