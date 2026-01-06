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
	client *http.Client
	config *config.PythonConfig
	logger *zap.Logger
}

// NewHTTPClient 创建新的 HTTP 客户端
func NewHTTPClient(cfg *config.Config, logger *zap.Logger) *HTTPClient {
	// 设置连接超时为5秒
	connectionTimeout := 5 * time.Second
	transport := &http2.Transport{
		AllowHTTP: true, // 允许非加密连接（h2c - HTTP/2 over cleartext）
		DialTLS: func(network, addr string, cfg *tls.Config) (net.Conn, error) {
			// 对于 h2c，不使用 TLS，直接建立普通 TCP 连接
			dialer := &net.Dialer{
				Timeout:   connectionTimeout,
				KeepAlive: 30 * time.Second, // 保持连接活跃
			}
			return dialer.DialContext(context.Background(), network, addr)
		},
		MaxHeaderListSize: 262144, // 256KB - HTTP/2 最大头部列表大小
	}

	httpClient := &http.Client{
		Transport: transport,
		Timeout:   cfg.Python.Timeout,
	}

	return &HTTPClient{
		client: httpClient,
		config: &cfg.Python,
		logger: logger,
	}
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
func (c *HTTPClient) BuildURL(path string) string {
	return fmt.Sprintf("http://%s:%d%s", c.config.Host, c.config.Port, path)
}
