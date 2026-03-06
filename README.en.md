# Zero Agent

**Language**: [简体中文](README.md) | English

Production-oriented AI agent system with a **Go gateway + Python agent core** architecture, focused on orchestration extensibility, tool ecosystem integration, and runtime reliability.

## Positioning

- **Two-service split**: `zero-gateway` handles API ingress and traffic governance; `zero-agent` handles reasoning, workflow orchestration, and tool execution.
- **Reliability first**: supports degraded startup when MCP servers are unavailable.
- **Progressive context loading**: skills support `metadata/full/resources` to balance context quality and token cost.
- **Operational readiness**: service discovery, load balancing, circuit breaker, structured logs, and health checks.

## Table of Contents

- [Core Features](#core-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Core Features

### High-performance architecture

- **Go API gateway** (Gin): high concurrency, routing, traffic control.
- **Python AI core** (FastAPI + Hypercorn): async processing and streaming output.
- **Redis-backed service discovery** for multi-instance deployment.
- **Load balancing strategies**: round-robin, least-connection, random.

### AI capabilities

- **Multi-LLM support**: OpenAI, Anthropic, SiliconFlow.
- **LangGraph orchestration** for stateful workflows.
- **Tool integration**: builtin tools + MCP tools.
- **Skill system** with progressive load levels.
- **SSE streaming** for real-time responses.

### Production-grade capabilities

- Circuit breaker and failure recovery.
- Structured logs and health checks.
- MCP degraded mode (startup is not blocked by MCP failures).

## Architecture

```text
Client
  -> zero-gateway (Go)
     - /api/v1/chat, /api/v1/sessions, /api/v1/tools
  -> zero-agent (Python)
     - /agents/{agent_id}/chat?stream=true|false
     - /agents/{agent_id}/tools
  -> LLM providers + MCP servers
```

For full details:

- `docs/architecture/overview.md`
- `docs/architecture/streaming.md`

## Quick Start

### Option A: simple local startup (recommended for development)

Terminal 1:

```bash
cd zero-agent
source ../venv/bin/activate
python -m scripts.start
```

Terminal 2:

```bash
cd zero-gateway
make run
```

### Option B: production-style startup (service discovery + load balancing)

Enable Redis and set env vars before startup:

```bash
export PYTHON_USE_SERVICE_DISCOVERY=true
export PYTHON_SERVICE_NAME=zero-agent
export PYTHON_LOAD_BALANCE_STRATEGY=round_robin
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

Start multiple `zero-agent` instances on different ports, then start `zero-gateway`.

## Requirements

- Python 3.9+
- Go 1.24+
- Redis 6.0+
- Git 2.x+

## Configuration

Primary agent config:

- `zero-agent/config/agents/default_agent.yaml`

Key areas:

- LLM provider/model
- builtin tools
- MCP servers/tools
- skills (`load_level`)
- filters and function-calling options

## Usage

### Health check

```bash
curl http://localhost:8080/health
```

### Create session

```bash
curl -X POST http://localhost:8080/api/v1/sessions -H "Content-Type: application/json" -d '{}'
```

### Non-streaming chat

```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess_xxx","message":"calculate 1+2","stream":false}'
```

### Streaming chat (SSE)

```bash
curl -N -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"sess_xxx","message":"explain LangGraph","stream":true}'
```

More examples:

- `docs/api/reference.md`
- `docs/api/examples.md`

## Project Structure

```text
prodject/
├── zero-gateway/      # Go gateway
├── zero-agent/        # Python AI core
└── docs/              # Documentation
```

## Development

- Development guide: `docs/development/guide.md`
- Testing guide: `docs/development/testing.md`
- Deployment guide: `docs/development/deployment.md`

## Troubleshooting

- MCP tools unavailable: check MCP server command/network, service will run in degraded mode.
- Redis/service discovery issues: verify Redis host/port and discovery env vars.
- Streaming not working: use `/api/v1/chat` with `stream=true` (no separate `/chat/stream` endpoint).

## Contributing

Please read the canonical contribution guide:

- `docs/project/contributing.md`

## License

MIT License.

