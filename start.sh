#!/bin/bash
# 公考小智 v2 — 一键启动脚本
# 用法：bash start.sh
# 停止：bash start.sh stop

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$PROJECT_DIR/gk_mcp"
FRONTEND_DIR="/Users/ruanligao/Desktop/项目/gongkao-qd"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

# ── 颜色输出 ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

# ── 停止所有进程 ──
stop_all() {
    echo "停止所有服务..."
    pkill -f "redis-server" 2>/dev/null && ok "Redis 已停止" || warn "Redis 未在运行"
    pkill -f "mcp_server.py" 2>/dev/null && ok "MCP Server 已停止" || warn "MCP Server 未在运行"
    pkill -f "uvicorn api.main" 2>/dev/null && ok "FastAPI 已停止" || warn "FastAPI 未在运行"
    pkill -f "vite" 2>/dev/null && ok "前端已停止" || warn "前端未在运行"
    exit 0
}

# ── 检查端口是否被占用 ──
check_port() {
    lsof -i ":$1" &>/dev/null
}

if [ "$1" = "stop" ]; then
    stop_all
fi

echo ""
echo "========================================"
echo "  公考小智 v2 启动脚本"
echo "========================================"
echo ""

# ── 1. 检查 .env ──
if [ ! -f "$PROJECT_DIR/.env" ]; then
    err ".env 文件不存在，请先复制：cp .env.example .env"
    exit 1
fi
ok ".env 存在"

# ── 2. 启动 Redis ──
if check_port 6379; then
    ok "Redis 已在运行（port 6379）"
else
    redis-server --daemonize yes --logfile "$LOG_DIR/redis.log"
    sleep 1
    if check_port 6379; then
        ok "Redis 启动成功"
    else
        err "Redis 启动失败，请检查 $LOG_DIR/redis.log"
        exit 1
    fi
fi

# ── 3. 启动 MCP Server（每次强制重启）──
pkill -f "mcp_server.py" 2>/dev/null
sleep 1
cd "$MCP_DIR"
MCP_MODE=sse nohup python mcp_server.bak.py \
    > "$LOG_DIR/mcp_out.log" 2> "$LOG_DIR/mcp_err.log" &
MCP_PID=$!
sleep 2
if check_port 8765; then
    ok "MCP Server 启动成功（PID $MCP_PID）"
else
    err "MCP Server 启动失败，请检查 $LOG_DIR/mcp_err.log"
    exit 1
fi

# ── 4. 启动 FastAPI（每次强制重启）──
pkill -f "uvicorn api.main" 2>/dev/null
sleep 1
cd "$PROJECT_DIR"
nohup uvicorn api.main:app --host 0.0.0.0 --port 8900 \
    > "$LOG_DIR/api_out.log" 2> "$LOG_DIR/api_err.log" &
API_PID=$!
sleep 2
if check_port 8900; then
    ok "FastAPI 启动成功（PID $API_PID）"
else
    err "FastAPI 启动失败，请检查 $LOG_DIR/api_err.log"
    exit 1
fi

# ── 5. 启动前端（每次强制重启）──
pkill -f "vite" 2>/dev/null
sleep 1
cd "$FRONTEND_DIR"
nohup npm run dev \
    > "$LOG_DIR/frontend_out.log" 2> "$LOG_DIR/frontend_err.log" &
FRONT_PID=$!
sleep 4
if check_port 5173; then
    ok "前端启动成功（PID $FRONT_PID）"
else
    err "前端启动失败，请检查 $LOG_DIR/frontend_err.log"
fi

echo ""
echo "========================================"
ok "所有服务已启动"
echo ""
echo "  前端地址：http://localhost:5173"
echo "  API 地址：http://localhost:8900"
echo "  API 文档：http://localhost:8900/docs"
echo ""
echo "  停止所有服务：bash start.sh stop"
echo "  查看日志目录：$LOG_DIR"
echo "========================================"
echo ""