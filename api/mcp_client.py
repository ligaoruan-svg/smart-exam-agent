"""
api/mcp_client.py - FastAPI 内嵌 MCP 客户端

⚠️ 文件最上面有一段代理补丁:macOS 开了系统代理 (Clash/V2Ray/Surge) 时,
   httpx 默认会读 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY,导致连本地 localhost:8765
   被代理劫持返回 502 Bad Gateway。这段补丁强制 httpx 绕过代理。
   对没开代理的环境也安全(no-op)。

通过 SSE 连接到独立运行的 MCP server (gk_mcp/mcp_server.py),
列出工具、转换成 OpenAI function calling 格式喂给 LLM,
LLM 决定调工具时再回过来调 MCP。

关键设计:
  - 单例:整个 FastAPI 进程共享一个 MCP client
  - 启动时连接一次,缓存 tools 列表
  - 每次调工具新建一个会话 (避免长连接断开)
  - 失败时自动重连
"""

# ============================================================
# 🔧 代理补丁:必须在 import mcp.client.sse 之前执行
# ============================================================
import os as _os

# 1. 进程级:清掉本进程的代理环境变量,并把 localhost 加进 NO_PROXY
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    _os.environ.pop(_k, None)
_os.environ["NO_PROXY"] = "*"
_os.environ["no_proxy"] = "*"

# 2. httpx 库级:让所有新建的 AsyncClient 默认不读环境、不挂任何代理
import httpx as _httpx

_orig_async_init = _httpx.AsyncClient.__init__
_orig_sync_init = _httpx.Client.__init__


def _patched_async_init(self, *args, **kwargs):
    kwargs.setdefault("trust_env", False)
    kwargs.setdefault("mounts", {})
    return _orig_async_init(self, *args, **kwargs)


def _patched_sync_init(self, *args, **kwargs):
    kwargs.setdefault("trust_env", False)
    kwargs.setdefault("mounts", {})
    return _orig_sync_init(self, *args, **kwargs)


_httpx.AsyncClient.__init__ = _patched_async_init
_httpx.Client.__init__ = _patched_sync_init
# ============================================================
# 补丁结束
# ============================================================

import json
import time
import asyncio
from typing import Optional, Any
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client

from api.config import MCP_URL, get_logger

log = get_logger("mcp")


class MCPClient:
    """MCP client 单例"""

    def __init__(self, url: str = MCP_URL):
        self.url = url
        self._tools_cache: Optional[list[dict]] = None
        self._tools_openai_schema: Optional[list[dict]] = None

    # ---------- 列工具 (用于喂给 LLM) ----------
    async def list_tools(self, force_refresh: bool = False) -> list[dict]:
        if self._tools_cache is not None and not force_refresh:
            return self._tools_cache

        try:
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    self._tools_cache = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": t.inputSchema,
                        }
                        for t in result.tools
                    ]
                    log.info(f"✅ 从 MCP server 拉到 {len(self._tools_cache)} 个工具")
                    return self._tools_cache
        except Exception as e:
            log.error(f"❌ 连接 MCP server 失败 | {self.url} | {e}", exc_info=True)
            raise

    async def list_tools_for_openai(self, force_refresh: bool = False) -> list[dict]:
        if self._tools_openai_schema is not None and not force_refresh:
            return self._tools_openai_schema

        tools = await self.list_tools(force_refresh)
        self._tools_openai_schema = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        return self._tools_openai_schema

    # ---------- 调用工具 ----------
    async def call_tool(self, name: str, arguments: dict) -> dict:
        start = time.time()
        log.info(f"→ 调用工具 {name} | args={json.dumps(arguments, ensure_ascii=False)[:200]}")

        try:
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)

            elapsed = int((time.time() - start) * 1000)

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                try:
                    parsed = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    parsed = {"raw": text}
            else:
                parsed = {}

            log.info(f"← {name} | ok | {elapsed}ms | "
                     f"keys={list(parsed.keys())[:8] if isinstance(parsed, dict) else type(parsed).__name__}")

            return {
                "ok": not result.isError,
                "result": parsed,
                "elapsed_ms": elapsed,
                "error": None,
            }
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            log.error(f"← {name} | failed | {elapsed}ms | {e}", exc_info=True)
            return {
                "ok": False,
                "result": {},
                "elapsed_ms": elapsed,
                "error": str(e),
            }

    # ---------- 同步调用工具（给子线程用） ----------
    def call_tool_sync(self, name: str, arguments: dict, timeout: int = 30) -> dict:
        """
        同步版 call_tool，内部创建新事件循环执行异步调用。
        专门给 autogen_routes.py 的子线程使用。
        """
        async def _run():
            return await self.call_tool(name, arguments)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    asyncio.wait_for(_run(), timeout=timeout)
                )
            finally:
                loop.close()
        except asyncio.TimeoutError:
            return {
                "ok": False,
                "result": {"error": f"工具 {name} 超时（{timeout}秒）"},
                "elapsed_ms": timeout * 1000,
                "error": "timeout",
            }
        except Exception as e:
            return {
                "ok": False,
                "result": {"error": str(e)},
                "elapsed_ms": 0,
                "error": str(e),
            }

    # ---------- 健康检查 ----------
    async def health_check(self) -> bool:
        try:
            await self.list_tools(force_refresh=True)
            return True
        except Exception:
            return False


# ============================================================
# 全局单例
# ============================================================
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client