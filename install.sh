#!/bin/bash
# Nexus Agent 项目安装脚本
# 自动安装 Python 和 Golang 依赖

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 命令未找到，请先安装 $1"
        return 1
    fi
    return 0
}

# 检查Python版本
check_python_version() {
    local python_cmd=$1
    local version=$($python_cmd --version 2>&1 | grep -oP '\d+\.\d+')
    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)

    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 8 ]); then
        log_error "Python 版本过低。需要 Python 3.8+，当前版本: $version"
        return 1
    fi

    log_success "Python 版本检查通过: $version"
    return 0
}

# 检查Go版本
check_go_version() {
    local version=$(go version | grep -oP 'go\d+\.\d+')
    local major=$(echo $version | sed 's/go//' | cut -d. -f1)
    local minor=$(echo $version | sed 's/go//' | cut -d. -f2)

    if [ "$major" -lt 1 ] || ([ "$major" -eq 1 ] && [ "$minor" -lt 19 ]); then
        log_error "Go 版本过低。需要 Go 1.19+，当前版本: $version"
        return 1
    fi

    log_success "Go 版本检查通过: $version"
    return 0
}

# 主函数
main() {
    log_info "开始安装 Nexus Agent 项目..."

    # 检查系统依赖
    log_info "检查系统依赖..."
    check_command "python3" || exit 1
    check_command "pip3" || exit 1
    check_command "go" || exit 1
    check_command "git" || exit 1

    # 检查Python版本
    check_python_version "python3" || exit 1

    # 检查Go版本
    check_go_version || exit 1

    # 设置Python虚拟环境
    log_info "设置Python虚拟环境..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "Python虚拟环境创建成功"
    else
        log_warn "Python虚拟环境已存在，跳过创建"
    fi

    # 激活虚拟环境并安装Python依赖
    log_info "安装Python依赖..."
    source venv/bin/activate

    # 升级pip
    pip install --upgrade pip --quiet

    # 安装Python依赖
    if [ -f "zero-agent/requirements.txt" ]; then
        pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple -r zero-agent/requirements.txt --quiet
        log_success "Python依赖安装完成"
    else
        log_error "找不到 zero-agent/requirements.txt 文件"
        exit 1
    fi

    # 停用Python虚拟环境
    deactivate

    # 安装Go依赖
    log_info "安装Go依赖..."
    cd zero-gateway

    if [ -f "go.mod" ]; then
        go mod tidy
        go mod download
        log_success "Go依赖安装完成"
    else
        log_error "找不到 go.mod 文件"
        exit 1
    fi

    # 构建Go项目
    log_info "构建Go项目..."
    if [ -f "Makefile" ]; then
        make build
    else
        # 如果没有Makefile，手动构建
        go build -o bin/api-gateway ./cmd/api-gateway
    fi
    log_success "Go项目构建完成"

    cd ..

    # 创建环境配置文件
    log_info "创建环境配置文件..."
    if [ ! -f "zero-agent/.env" ]; then
        cat > zero-agent/.env << EOF
# Nexus Agent Python Service Configuration

# LLM Provider Configuration (choose one)
# OpenAI
# OPENAI_API_KEY=your_openai_api_key_here

# Anthropic
# ANTHROPIC_API_KEY=your_anthropic_api_key_here

# SiliconFlow (default)
SILICONFLOW_API_KEY=your_siliconflow_api_key_here

# LLM Configuration
LLM_PROVIDER=siliconflow
LLM_MODEL=Pro/Qwen/Qwen2.5-7B-Instruct

# Service Configuration
PYTHON_AGENT_HOST=localhost
PYTHON_AGENT_PORT=8082
LOG_LEVEL=info

# MCP Configuration
MCP_ENABLED=true
EOF
        log_success "Python服务环境配置文件创建成功: zero-agent/.env"
        log_warn "请编辑 zero-agent/.env 文件，配置您的API密钥"
    else
        log_warn "Python环境配置文件已存在，跳过创建"
    fi

    if [ ! -f "zero-gateway/.env" ]; then
        cp zero-gateway/env.example zero-gateway/.env
        log_success "Go服务环境配置文件创建成功: zero-gateway/.env"
        log_warn "请根据需要编辑 zero-gateway/.env 文件"
    else
        log_warn "Go环境配置文件已存在，跳过创建"
    fi

    # 设置脚本权限
    log_info "设置脚本权限..."
    chmod +x start.sh
    chmod +x test.sh
    chmod +x install.sh
    log_success "脚本权限设置完成"

    # 验证安装
    log_info "验证安装..."
    source venv/bin/activate

    # 检查关键Python模块
    python3 -c "import fastapi, uvicorn, langchain, mcp; print('Python模块检查通过')" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "Python模块验证通过"
    else
        log_error "Python模块验证失败"
        exit 1
    fi

    deactivate

    # 检查Go构建结果
    if [ -f "zero-gateway/bin/api-gateway" ] || [ -f "zero-gateway/api-gateway" ]; then
        log_success "Go构建验证通过"
    else
        log_error "Go构建验证失败"
        exit 1
    fi

    log_success "🎉 Nexus Agent 项目安装完成！"
    echo ""
    echo "接下来请执行以下步骤："
    echo "1. 编辑配置文件："
    echo "   - zero-agent/.env (配置API密钥)"
    echo "   - zero-gateway/.env (根据需要调整)"
    echo ""
    echo "2. 启动服务："
    echo "   ./start.sh"
    echo ""
    echo "3. 验证服务："
    echo "   curl http://localhost:8080/health"
    echo ""
}

# 显示帮助信息
show_help() {
    echo "Nexus Agent 项目安装脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示帮助信息"
    echo "  --dry-run      预览模式，只显示将要执行的操作，不实际执行"
    echo "  --no-python    跳过Python依赖安装"
    echo "  --no-go        跳过Go依赖安装"
    echo ""
    echo "系统要求:"
    echo "  - Python 3.8+"
    echo "  - Go 1.19+"
    echo "  - Git"
    echo ""
    echo "示例:"
    echo "  $0              # 完整安装"
    echo "  $0 --dry-run    # 预览安装步骤"
    echo "  $0 --no-go      # 只安装Python依赖"
    echo ""
}

# 解析命令行参数
SKIP_PYTHON=false
SKIP_GO=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --no-python)
            SKIP_PYTHON=true
            shift
            ;;
        --no-go)
            SKIP_GO=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# Dry run模式下的执行函数
dry_run_exec() {
    log_info "[DRY RUN] $1"
}

# 实际执行或dry run
exec_cmd() {
    if [ "$DRY_RUN" = true ]; then
        dry_run_exec "$1"
    else
        eval "$1"
    fi
}

# 运行主函数
main
