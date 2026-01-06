# 部署指南

## 部署架构

### 单机部署

最简单的部署方式，适合开发和小型应用：

```
┌─────────────────────────────────────┐
│           Universal Agent           │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  │ LLM │ │Tool │ │Orch.│ │ API │   │
│  │Layer│ │Layer│ │Layer│ │Layer│   │
│  └─────┘ └─────┘ └─────┘ └─────┘   │
└─────────────────────────────────────┘
```

### 负载均衡部署

生产环境的推荐部署方式：

```
┌─────────────┐    ┌─────────────┐
│   Load      │    │   Monitor   │
│  Balancer   │    │   (Metrics) │
│             │    │             │
└─────────────┘    └─────────────┘
        │                  │
┌─────────────┐    ┌─────────────┐
│   API层     │    │   Cache     │
│ (Multiple)  │────│   (Redis)   │
└─────────────┘    └─────────────┘
        │
┌─────────────┐    ┌─────────────┐
│   编排层    │    │   状态      │
│ (Workflow)  │────│  (SQLite/   │
│             │    │   Redis)    │
└─────────────┘    └─────────────┘
        │
┌─────────────┐    ┌─────────────┐
│   工具层    │    │   LLM       │
│ (Tools)     │────│  (External  │
│             │    │   APIs)     │
└─────────────┘    └─────────────┘
```

## Docker部署

### 使用Dockerfile

```dockerfile
# 使用官方Python镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt pyproject.toml ./

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["python", "-m", "scripts.start"]
```

### 构建和运行

```bash
# 构建镜像
docker build -t zero-agent .

# 运行容器
docker run -d \
  --name agent-container \
  -p 8080:8080 \
  -e OPENAI_API_KEY="your-api-key" \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  zero-agent

# 查看日志
docker logs -f agent-container

# 进入容器调试
docker exec -it agent-container bash
```

## Docker Compose部署

### 基础配置

```yaml
# docker/docker-compose.yml
version: '3.8'

services:
  agent:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - API_HOST=0.0.0.0
      - API_PORT=8080
    env_file:
      - ../.env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    volumes:
      - logs:/app/logs
      - ./config:/app/config:ro

volumes:
  logs:
```

### 生产配置

```yaml
# docker/docker-compose.prod.yml
version: '3.8'

services:
  agent:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8080:8080"
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=WARNING
      - API_HOST=0.0.0.0
      - API_PORT=8080
    env_file:
      - ../.env.prod
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 40s
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config:ro
      - ./data:/app/data
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # Redis缓存（可选）
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Nginx反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - agent
    restart: unless-stopped

volumes:
  redis_data:
```

### Nginx配置

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream agent_backend {
        server agent:8080;
    }

    server {
        listen 80;
        server_name your-domain.com;

        # 重定向到HTTPS（可选）
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL配置
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        # 代理设置
        location / {
            proxy_pass http://agent_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket支持（如果需要）
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            # 超时设置
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # 健康检查端点
        location /health {
            proxy_pass http://agent_backend;
            access_log off;
        }

        # 静态文件缓存
        location /static/ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

## 裸机部署

### 系统要求

#### Ubuntu/Debian
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python
sudo apt install python3.11 python3.11-venv python3-pip

# 安装依赖
sudo apt install gcc g++ libffi-dev curl

# 创建用户
sudo useradd --create-home --shell /bin/bash agent
sudo usermod -aG sudo agent
```

#### CentOS/RHEL
```bash
# 更新系统
sudo yum update -y

# 安装Python
sudo yum install python311 python311-pip

# 安装依赖
sudo yum install gcc gcc-c++ libffi-devel

# 创建用户
sudo useradd --create-home --shell /bin/bash agent
```

### 应用部署

```bash
# 切换到应用用户
sudo su - agent

# 克隆代码
git clone https://github.com/your-repo/zero-agent.git
cd zero-agent

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env  # 配置API密钥等

# 测试运行
python -m scripts.start

# 退出测试
Ctrl+C
```

### Systemd服务

```ini
# /etc/systemd/system/universal-agent.service
[Unit]
Description=Universal Agent MVP
After=network.target
Wants=network.target

[Service]
Type=simple
User=agent
Group=agent
WorkingDirectory=/home/agent/zero-agent
Environment=PATH=/home/agent/zero-agent/venv/bin
ExecStart=/home/agent/zero-agent/venv/bin/python -m scripts.start
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5

# 资源限制
MemoryLimit=1G
CPUQuota=100%

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=universal-agent

[Install]
WantedBy=multi-user.target
```

```bash
# 重新加载systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start universal-agent

# 设置开机自启
sudo systemctl enable universal-agent

# 查看状态
sudo systemctl status universal-agent

# 查看日志
sudo journalctl -u universal-agent -f
```

### 日志轮转

```bash
# /etc/logrotate.d/universal-agent
/home/agent/zero-agent/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 agent agent
    postrotate
        systemctl reload universal-agent
    endscript
}
```

## 云平台部署

### AWS ECS/Fargate

#### ECS任务定义

```json
{
    "family": "universal-agent-task",
    "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole",
    "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "containerDefinitions": [
        {
            "name": "agent",
            "image": "your-registry/zero-agent:latest",
            "essential": true,
            "portMappings": [
                {
                    "containerPort": 8080,
                    "hostPort": 8080,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {"name": "ENVIRONMENT", "value": "production"},
                {"name": "LOG_LEVEL", "value": "INFO"},
                {"name": "API_HOST", "value": "0.0.0.0"},
                {"name": "API_PORT", "value": "8080"}
            ],
            "secrets": [
                {
                    "name": "OPENAI_API_KEY",
                    "valueFrom": "arn:aws:secretsmanager:region:account:secret:openai-key"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/universal-agent",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}
```

#### ECS服务配置

```yaml
# ecs-service.yml
service:
  name: universal-agent-service
  cluster: your-cluster
  taskDefinition: universal-agent-task
  desiredCount: 2
  launchType: FARGATE
  networkConfiguration:
    awsvpcConfiguration:
      subnets:
        - subnet-12345
        - subnet-67890
      securityGroups:
        - sg-abcdef
      assignPublicIp: ENABLED
  loadBalancers:
    - targetGroupArn: arn:aws:elasticloadbalancing:region:account:targetgroup/agent-tg
      containerName: agent
      containerPort: 8080
  serviceRegistries:
    - registryArn: arn:aws:servicediscovery:region:account:service/srv-registry
```

### Google Cloud Run

```yaml
# cloud-run.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: universal-agent
spec:
  template:
    spec:
      containers:
      - image: gcr.io/your-project/zero-agent:latest
        ports:
        - containerPort: 8080
        env:
        - name: ENVIRONMENT
          value: production
        - name: LOG_LEVEL
          value: INFO
        - name: API_HOST
          value: "0.0.0.0"
        - name: API_PORT
          value: "8080"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-api-key
              key: key
        resources:
          limits:
            cpu: 1000m
            memory: 1Gi
        startupProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
```

### Azure Container Apps

```yaml
# container-app.yaml
location: eastus
name: universal-agent
resourceGroup: your-resource-group
type: Microsoft.App/containerApps
properties:
  managedEnvironmentId: /subscriptions/.../managedEnvironments/env-name
  configuration:
    activeRevisionsMode: Single
    secrets:
    - name: openai-api-key
      value: your-api-key
    - name: siliconflow-api-key
      value: your-siliconflow-key
  template:
    containers:
    - image: your-registry.azurecr.io/zero-agent:latest
      name: agent
      env:
      - name: ENVIRONMENT
        value: production
      - name: LOG_LEVEL
        value: INFO
      - name: OPENAI_API_KEY
        secretRef: openai-api-key
      resources:
        cpu: 0.5
        memory: 1.0Gi
    scale:
      minReplicas: 1
      maxReplicas: 10
      rules:
      - name: http-scaling
        http:
          metadata:
            concurrentRequests: '10'
```

## 监控和日志

### 应用指标

```python
# api/metrics.py
from fastapi import APIRouter, Depends
from prometheus_client import Counter, Histogram, generate_latest
import time

router = APIRouter()

# 定义指标
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)

CHAT_REQUESTS = Counter(
    'chat_requests_total',
    'Total number of chat requests'
)

TOOL_EXECUTIONS = Counter(
    'tool_executions_total',
    'Total number of tool executions',
    ['tool_name', 'status']
)

@router.get("/metrics")
async def metrics():
    """Prometheus指标端点"""
    return generate_latest()

def track_request(method: str, endpoint: str, status: int, duration: float):
    """跟踪请求"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

def track_chat_request():
    """跟踪聊天请求"""
    CHAT_REQUESTS.inc()

def track_tool_execution(tool_name: str, success: bool):
    """跟踪工具执行"""
    status = "success" if success else "failure"
    TOOL_EXECUTIONS.labels(tool_name=tool_name, status=status).inc()
```

### 日志聚合

#### ELK Stack配置

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /app/logs/*.log
  fields:
    service: universal-agent
    environment: production

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "universal-agent-%{+yyyy.MM.dd}"
```

#### Loki + Promtail

```yaml
# promtail.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: universal-agent
    static_configs:
      - targets:
          - localhost
        labels:
          job: universal-agent
          environment: production
          __path__: /app/logs/*.log
```

## 备份和恢复

### 数据备份

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/opt/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# 备份数据库
sqlite3 /app/data/agent.db ".backup '$BACKUP_DIR/agent.db'"

# 备份配置文件
cp -r /app/config $BACKUP_DIR/

# 备份日志（最近7天）
find /app/logs -name "*.log" -mtime -7 -exec cp {} $BACKUP_DIR/logs/ \;

# 压缩备份
tar -czf $BACKUP_DIR.tar.gz -C $BACKUP_DIR .
rm -rf $BACKUP_DIR

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### 灾难恢复

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

# 停止服务
systemctl stop universal-agent

# 解压备份
tar -xzf $BACKUP_FILE -C /tmp/

# 恢复数据库
cp /tmp/backup/agent.db /app/data/agent.db

# 恢复配置
cp -r /tmp/backup/config/* /app/config/

# 启动服务
systemctl start universal-agent

echo "Restore completed"
```

## 安全配置

### API密钥管理

```bash
# 使用环境变量
export OPENAI_API_KEY="your-secure-key"

# 或使用Docker secrets
echo "your-secure-key" | docker secret create openai_api_key -

# 或使用Kubernetes secrets
kubectl create secret generic agent-secrets \
  --from-literal=openai-api-key=your-secure-key
```

### 网络安全

```nginx
# nginx.conf - 安全配置
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL配置
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:...;

    # 安全头
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # 限制请求大小
    client_max_body_size 10m;

    # 速率限制
    limit_req zone=api burst=10 nodelay;

    location / {
        proxy_pass http://agent_backend;

        # 隐藏内部头信息
        proxy_hide_header X-Powered-By;
        proxy_hide_header Server;
    }
}
```

### 防火墙配置

```bash
# UFW配置
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Docker防火墙
sudo ufw allow 8080/tcp
sudo ufw reload
```

## 性能优化

### 应用层优化

```python
# api/app.py - 性能优化
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI()

# Gzip压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 信任主机
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["your-domain.com", "*.your-domain.com"]
)

# 连接池配置
import httpx
client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(10.0)
)
```

### 系统层优化

```bash
# 内核参数优化
sudo tee /etc/sysctl.d/99-agent.conf << EOF
# 网络优化
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 1024
net.ipv4.ip_local_port_range = 1024 65535

# 内存优化
vm.swappiness = 10
vm.dirty_ratio = 60
vm.dirty_background_ratio = 2
EOF

sudo sysctl --system
```

### 监控性能

```python
# performance_monitor.py
import psutil
import time
from typing import Dict, Any

class PerformanceMonitor:
    def __init__(self):
        self.process = psutil.Process()

    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            "cpu_percent": self.process.cpu_percent(),
            "memory_mb": self.process.memory_info().rss / 1024 / 1024,
            "threads": self.process.num_threads(),
            "open_files": len(self.process.open_files()),
            "connections": len(self.process.connections()),
            "timestamp": time.time()
        }

    def log_performance(self, interval: int = 60):
        """定期记录性能"""
        while True:
            metrics = self.get_metrics()
            logger.info("Performance metrics", **metrics)
            time.sleep(interval)

# 在应用启动时开始监控
import threading
monitor = PerformanceMonitor()
threading.Thread(target=monitor.log_performance, daemon=True).start()
```

## 故障排除

### 常见部署问题

#### 端口冲突
```bash
# 检查端口占用
sudo netstat -tulpn | grep :8080
sudo lsof -i :8080

# 杀死进程
sudo kill -9 $(sudo lsof -t -i:8080)
```

#### 内存不足
```bash
# 检查内存使用
free -h
df -h

# 查看进程内存使用
ps aux --sort=-%mem | head -10
```

#### 磁盘空间不足
```bash
# 检查磁盘使用
df -h

# 清理日志
find /var/log -name "*.log" -mtime +30 -delete

# 清理Docker
docker system prune -a --volumes
```

#### 网络连接问题
```bash
# 测试网络连接
ping api.openai.com
curl -I https://api.openai.com

# 检查DNS
nslookup api.openai.com

# 检查防火墙
sudo ufw status
sudo iptables -L
```

## 升级策略

### 滚动升级

```bash
# 蓝绿部署
# 1. 部署新版本到蓝色环境
docker tag universal-agent:v1 universal-agent:v2
docker build -t universal-agent:v2 .

# 2. 切换流量到新版本
docker-compose up -d agent-v2
docker-compose stop agent-v1

# 3. 验证新版本正常
curl http://localhost:8080/health

# 4. 清理旧版本
docker-compose rm agent-v1
```

### 零停机部署

```yaml
# docker-compose.zero-downtime.yml
version: '3.8'

services:
  agent-v1:
    image: universal-agent:v1
    deploy:
      replicas: 2

  agent-v2:
    image: universal-agent:v2
    deploy:
      replicas: 0  # 初始为0

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx-upstream.conf:/etc/nginx/nginx.conf
```

```nginx
# nginx-upstream.conf
upstream agent_backend {
    server agent-v1:8080 weight=2;
    server agent-v2:8080 weight=0;
}

server {
    location / {
        proxy_pass http://agent_backend;
    }
}
```

```bash
# 执行零停机升级
# 1. 启动v2实例
docker-compose up -d agent-v2 --scale agent-v2=1

# 2. 逐渐切换流量
# nginx reload with updated weights

# 3. 停止v1实例
docker-compose up -d agent-v1 --scale agent-v1=0

# 4. 清理
docker-compose rm agent-v1
```

这个部署指南提供了从简单单机部署到复杂分布式部署的完整解决方案。
