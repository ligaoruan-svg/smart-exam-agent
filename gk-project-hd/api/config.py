"""
api/config.py - 集中配置 + 日志系统

所有模块从这里读配置，不要散在各处。
日志系统：
  - logs/api.log         主进程日志（INFO+）
  - logs/mcp.log         MCP 调用日志（每次工具调用的入参/返回/耗时）
  - logs/error.log       错误日志（ERROR 级别）
  - logs/chat.log        对话日志（用户消息 + LLM 响应）
  日志按天分割，保留 30 天。
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# 1. 加载 .env
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    print(f"⚠️  .env 文件不存在：{ENV_FILE}，将使用默认值/系统环境变量",
          file=sys.stderr)


# ============================================================
# 2. 配置项（环境变量 → Python 常量）
# ============================================================

# 数据库
DB_HOST     = os.environ.get("DB_HOST", "localhost")
DB_PORT     = int(os.environ.get("DB_PORT", "3306"))
DB_USER     = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME     = os.environ.get("DB_NAME", "cs_v2")

# DeepSeek
DEEPSEEK_API_KEY  = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL    = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# JWT
JWT_SECRET        = os.environ.get("JWT_SECRET", "change-me-in-prod")
JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "720"))
JWT_ALGORITHM     = "HS256"

# MCP
MCP_URL  = os.environ.get("MCP_URL", "http://localhost:8765/sse")
MCP_PORT = int(os.environ.get("MCP_PORT", "8765"))

# FastAPI
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8900"))
API_BASE = os.environ.get("API_BASE", f"http://localhost:{API_PORT}")

# 日志
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_DIR   = Path(os.environ.get("LOG_DIR", str(PROJECT_ROOT / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 3. 日志系统
# ============================================================
_loggers_setup = False


def _make_handler(filename: str, level=logging.INFO) -> logging.Handler:
    """创建一个按天分割的日志 handler"""
    h = TimedRotatingFileHandler(
        LOG_DIR / filename,
        when="midnight",
        backupCount=30,       # 保留 30 天
        encoding="utf-8",
    )
    h.setLevel(level)
    h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    return h


def _make_console_handler(level=logging.INFO) -> logging.Handler:
    """控制台 handler，开发时方便看"""
    h = logging.StreamHandler(sys.stderr)
    h.setLevel(level)
    h.setFormatter(logging.Formatter(
        "\033[36m%(asctime)s\033[0m [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    return h


def setup_logging():
    """
    主入口调用一次。建立 4 类 logger:
      - api      主进程 → api.log + 控制台
      - mcp      MCP 调用 → mcp.log
      - chat     对话流水 → chat.log
      - error    所有错误 → error.log（任何 logger 的 ERROR 都会进这里）
    """
    global _loggers_setup
    if _loggers_setup:
        return
    _loggers_setup = True

    level = getattr(logging, LOG_LEVEL, logging.INFO)

    # 全局 root 配置：错误日志聚合
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    error_handler = _make_handler("error.log", level=logging.ERROR)
    root.addHandler(error_handler)

    # api logger（主进程）
    api_log = logging.getLogger("api")
    api_log.setLevel(level)
    api_log.addHandler(_make_handler("api.log", level=level))
    api_log.addHandler(_make_console_handler(level=level))
    api_log.propagate = True   # 让 ERROR 也进 root（→ error.log）

    # mcp logger
    mcp_log = logging.getLogger("mcp")
    mcp_log.setLevel(level)
    mcp_log.addHandler(_make_handler("mcp.log", level=level))
    mcp_log.propagate = True

    # chat logger
    chat_log = logging.getLogger("chat")
    chat_log.setLevel(level)
    chat_log.addHandler(_make_handler("chat.log", level=level))
    chat_log.propagate = True

    # 抑制第三方库的喧闹日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    api_log.info("=" * 60)
    api_log.info(f"日志系统初始化完成 | level={LOG_LEVEL} | dir={LOG_DIR}")
    api_log.info("=" * 60)


# 导出快捷 logger
def get_logger(name: str = "api") -> logging.Logger:
    """获取 logger，未初始化则先初始化"""
    if not _loggers_setup:
        setup_logging()
    return logging.getLogger(name)

# SMTP 邮件配置
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
