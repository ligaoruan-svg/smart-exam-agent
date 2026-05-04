"""
api/main.py - FastAPI 主入口

启动：
  uvicorn api.main:app --host 0.0.0.0 --port 8900 --reload

启动前必须先启动 MCP server（独立进程，SSE 模式）：
  cd gk_mcp && MCP_MODE=sse python mcp_server.py

[round 3] 新增:
  - 注册 paper_routes / pdf_routes
  - lifespan 启动 PDF 后台 worker
"""
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 必须最早 import config，让日志在所有 import 前初始化
from api.config import setup_logging, get_logger, API_HOST, API_PORT, API_BASE
setup_logging()
log = get_logger("api")

from api.db import test_connection
from api.mcp_client import get_mcp_client
from api.auth_routes import router as auth_router
from api.chat_routes import router as chat_router
from api.practice import router as practice_router
# [round 3] 新增
from api.paper_routes import router as paper_router
from api.pdf_routes import router as pdf_router
from api.pdf_worker import start_worker, stop_worker
# [round 4] 错题本（新增）
from api.mistake_routes import router as mistake_router
# [round 5] 题目反馈
from api.feedback_routes import router as feedback_router
# [autogen] 多 Agent 路由
from api.autogen_routes import router as autogen_router


# ============================================================
# 每日配额重置任务（每天凌晨 0 点归零 daily_used）
# ============================================================
async def _daily_quota_reset():
    """每天凌晨 0 点把所有用户的 daily_used 重置为 0"""
    from api.db import execute as db_execute
    while True:
        now = __import__('datetime').datetime.now()
        # 计算距离下一个凌晨 0 点的秒数
        tomorrow = (now + __import__('datetime').timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        seconds_until_midnight = (tomorrow - now).total_seconds()
        log.info(f"[quota_reset] 下次重置在 {tomorrow.strftime('%Y-%m-%d %H:%M:%S')}（{int(seconds_until_midnight/3600)}小时后）")
        await asyncio.sleep(seconds_until_midnight)
        try:
            db_execute("UPDATE users SET daily_used = 0 WHERE plan = 'free' OR plan IS NULL")
            log.info("[quota_reset] ✅ 每日配额已重置")
        except Exception as e:
            log.error(f"[quota_reset] ❌ 重置失败：{e}")


# ============================================================
# 启动 / 关闭钩子
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("FastAPI 启动")
    log.info(f"  API: {API_BASE}")
    log.info("=" * 60)

    # 1. 数据库
    if not test_connection():
        log.warning("⚠️  数据库连接失败，但继续启动（运行时会重试）")

    # 2. MCP server 健康检查
    mcp = get_mcp_client()
    try:
        ok = await mcp.health_check()
        if ok:
            log.info("✅ MCP server 连接成功")
        else:
            log.warning("⚠️  MCP server 不可达，请确认 MCP server 已启动")
    except Exception as e:
        log.warning(f"⚠️  MCP server 检查异常: {e}")

    # 3. [round 3] 启动 PDF 后台 worker
    try:
        start_worker()
        log.info("✅ PDF worker 已启动")
    except Exception as e:
        log.warning(f"⚠️  PDF worker 启动失败: {e}")

    # 4. 启动每日配额重置任务
    reset_task = asyncio.create_task(_daily_quota_reset())
    log.info("✅ 每日配额重置任务已启动")

    yield   # ← 应用运行中

    # ---------- shutdown ----------
    reset_task.cancel()
    log.info("FastAPI 关闭")
    try:
        await stop_worker()
    except Exception as e:
        log.warning(f"PDF worker 停止异常: {e}")


# ============================================================
# App 实例
# ============================================================
app = FastAPI(
    title="公考小智 API",
    version="2.1.0",   # round 3
    description="公考小智 v2 BFF（FastAPI + MCP 编排 + DeepSeek）",
    lifespan=lifespan,
)


# CORS - 只允许指定域名访问
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://your-domain.com",  # 上线前替换成真实域名
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Disposition"],
)


# ============================================================
# 根接口
# ============================================================
@app.get("/")
def root():
    return {
        "name": "公考小智 API",
        "version": "2.1.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    """健康检查 - 顺便测下 MCP 和 DB"""
    mcp = get_mcp_client()
    db_ok = test_connection()
    mcp_ok = await mcp.health_check()
    return {
        "ok": db_ok and mcp_ok,
        "db": db_ok,
        "mcp": mcp_ok,
    }


# ============================================================
# 注册所有路由
# ============================================================
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(practice_router)
# [round 3] 新增
app.include_router(paper_router)
app.include_router(pdf_router)
# [round 4] 错题本
app.include_router(mistake_router)
# [round 5] 题目反馈
app.include_router(feedback_router)
# [autogen] 多 Agent
app.include_router(autogen_router)


# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info",
    )