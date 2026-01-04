# Nexus Gateway Makefile

.PHONY: help build clean test docker-build docker-run proto-gen

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOCLEAN=$(GOCMD) clean
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod

# Binary names
API_GATEWAY_BINARY=api-gateway

# Build directories
BUILD_DIR=build
CMD_DIR=cmd

help: ## Display this help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build API Gateway
	@echo "Building API Gateway..."
	@mkdir -p $(BUILD_DIR)
	$(GOBUILD) -o $(BUILD_DIR)/$(API_GATEWAY_BINARY) $(CMD_DIR)/api-gateway/main.go
	@echo "Build completed!"

clean: ## Clean build artifacts
	$(GOCLEAN)
	@rm -rf $(BUILD_DIR)
	@echo "Clean completed!"

test: ## Run all tests
	$(GOTEST) -v ./...

test-coverage: ## Run tests with coverage
	$(GOTEST) -v -coverprofile=coverage.out ./...
	$(GOCMD) tool cover -html=coverage.out -o coverage.html

deps: ## Download dependencies
	$(GOMOD) download
	$(GOMOD) tidy

docker-build: ## Build Docker image
	@echo "Building API Gateway Docker image..."
	docker build -f docker/Dockerfile.api-gateway -t nexus-gateway/api-gateway:latest .

docker-run: ## Run API Gateway in Docker
	docker run -p 8080:8080 --env-file .env nexus-gateway/api-gateway:latest

proto-gen: ## Generate protobuf code
	@echo "Generating protobuf code..."
	@which protoc >/dev/null || (echo "protoc not found, please install protobuf compiler" && exit 1)
	@which protoc-gen-go >/dev/null || $(GOCMD) install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	@which protoc-gen-go-grpc >/dev/null || $(GOCMD) install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
	protoc --go_out=. --go-grpc_out=. proto/*.proto

run: ## Run API Gateway locally
	$(GOCMD) run $(CMD_DIR)/api-gateway/main.go

lint: ## Run golangci-lint
	@which golangci-lint >/dev/null || $(GOCMD) install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	golangci-lint run

fmt: ## Format Go code
	$(GOCMD) fmt ./...

vet: ## Run go vet
	$(GOCMD) vet ./...

check: fmt vet lint ## Run all checks (format, vet, lint)

# Development helpers
dev-setup: ## Setup development environment
	@echo "Setting up development environment..."
	$(GOMOD) tidy
	@which golangci-lint >/dev/null || $(GOCMD) install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	@echo "Development environment setup complete!"

bench: ## Run benchmarks
	$(GOTEST) -bench=. -benchmem ./...

# CI/CD helpers
ci: check test ## Run CI pipeline locally
