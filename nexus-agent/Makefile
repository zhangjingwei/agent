# Universal Agent MVP Makefile

.PHONY: help install run test clean docker-build docker-run demo

help: ## 显示帮助信息
	@echo "Universal Agent MVP - 可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖
	pip install -e .

run: ## 启动服务
	python -m scripts.start

test: ## 运行测试
	pytest tests/ -v

clean: ## 清理缓存文件
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete

docker-build: ## 构建Docker镜像
	docker build -t nexus-agent -f docker/Dockerfile .

docker-run: ## 运行Docker容器
	docker run -p 8080:8080 --env-file .env nexus-agent

docker-compose-up: ## 启动Docker Compose服务
	docker-compose -f docker/docker-compose.yml up --build

docker-compose-down: ## 停止Docker Compose服务
	docker-compose -f docker/docker-compose.yml down

demo: ## 运行演示脚本
	python demo.py

lint: ## 代码格式检查
	black llm tools api core config orchestration scripts tests
	isort llm tools api core config orchestration scripts tests
	flake8 llm tools api core config orchestration scripts tests

type-check: ## 类型检查
	mypy llm tools api core config orchestration scripts

setup-dev: ## 设置开发环境
	pip install -e ".[dev]"

check-health: ## 检查服务健康状态
	curl -s http://localhost:8080/health | python -m json.tool

check-tools: ## 检查可用工具
	curl -s http://localhost:8080/tools | python -m json.tool
