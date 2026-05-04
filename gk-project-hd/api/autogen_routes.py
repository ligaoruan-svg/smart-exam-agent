"""
api/autogen_routes.py - AutoGen 多 Agent 接口（真流式版 v5）

核心流程：
  1. Coordinator 判断意图（同步 LLM.chat）
  2. 调 MCP 工具（同步，推送 tool_call_start/done）
  3. LLM 流式生成回答（在子线程事件循环里跑 LLM.stream()，逐 token 推送）
  4. 发 ui_card + 保存历史
"""
import os
import sys
import asyncio
import json
import time
import re
import threading
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from api.auth import current_user
from api.config import get_logger
from api.db import execute

log = get_logger("autogen")

router = APIRouter(prefix="/api/autogen", tags=["autogen"])

AUTOGEN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "autogen-gk"
)


def _run_autogen_with_queue(
    message: str,
    user_id: int,
    session_id: Optional[str],
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """子线程入口"""

    def put_nowait(event: dict):
        loop.call_soon_threadsafe(queue.put_nowait, event)

    asyncio.set_event_loop(loop)

    if AUTOGEN_DIR not in sys.path:
        sys.path.insert(0, AUTOGEN_DIR)

    try:
        from api.llm import LLM
        from api.mcp_client import get_mcp_client
        from agents.coordinator import create_coordinator
        from agents.quiz_agent import create_quiz_agent
        from agents.study_agent import create_study_agent
        from agents.plan_agent import create_plan_agent
    except ImportError as e:
        put_nowait({"type": "error", "message": f"模块加载失败: {e}"})
        put_nowait({"type": "done"})
        return

    llm = LLM()
    mcp = get_mcp_client()

    llm_config = {
        "config_list": [{
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        }],
        "temperature": 0.3,
    }

    # ================================================================
    # Step 1: Coordinator 判断意图
    # ================================================================
    put_nowait({"type": "thinking_start", "label": "Coordinator 分析意图"})

    coordinator = create_coordinator(llm_config)
    coord_resp = llm.chat(
        [
            {"role": "system", "content": coordinator.system_message},
            {"role": "user", "content": message},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    intent = (coord_resp.content or "").strip()

    # ================================================================
    # Step 2: 确定工具调用序列
    # ================================================================
    tool_sequence = []
    agent_type = None

    if intent.startswith("QUIZ_AGENT:"):
        agent_type = "quiz"
        count_match = re.search(r'(\d+)\s*道', message)
        count = int(count_match.group(1)) if count_match else 5
        tool_sequence.append(("prepare_practice_session", {
            "user_id": user_id,
            "count": count,
        }))

    elif intent.startswith("STUDY_AGENT:"):
        agent_type = "study"
        tool_sequence.append(("get_user_study_overview", {"user_id": user_id}))
        tool_sequence.append(("get_user_weakness", {"user_id": user_id}))
        tool_sequence.append(("get_recent_wrongs", {"user_id": user_id, "limit": 3}))

    elif intent.startswith("PLAN_AGENT:"):
        agent_type = "plan"
        tool_sequence.append(("get_user_study_overview", {"user_id": user_id}))
        tool_sequence.append(("get_user_weakness", {"user_id": user_id}))

    # ================================================================
    # Step 3: 调 MCP 工具
    # ================================================================
    put_nowait({
        "type": "thinking_step",
        "detail": f"路由 → {'出题' if agent_type == 'quiz' else '学情分析' if agent_type == 'study' else '制定计划'}",
    })

    tool_results = {}
    cards_collected = []

    for tname, targs in tool_sequence:
        t_start = time.time()
        put_nowait({
            "type": "tool_call_start",
            "name": tname,
            "arguments": targs,
        })

        try:
            result = mcp.call_tool_sync(tname, targs)
            elapsed = int((time.time() - t_start) * 1000)
            r = result.get("result", {})
            tool_results[tname] = r

            # 检测 ui_card
            if isinstance(r, dict) and "ui_card" in r:
                cards_collected.append(r["ui_card"])
                put_nowait({"type": "ui_card", "card": r["ui_card"]})

            put_nowait({
                "type": "tool_call_done",
                "name": tname,
                "ok": True,
                "elapsed_ms": elapsed,
                "summary": _summarize_tool_result(tname, result),
            })
        except Exception as e:
            elapsed = int((time.time() - t_start) * 1000)
            tool_results[tname] = {"error": str(e)}
            put_nowait({
                "type": "tool_call_done",
                "name": tname,
                "ok": False,
                "elapsed_ms": elapsed,
                "summary": f"失败: {e}",
                "error": str(e),
            })

    # ================================================================
    # Step 4: 选 Agent，构建 messages
    # ================================================================
    if agent_type == "quiz":
        agent = create_quiz_agent(llm_config, user_id)
    elif agent_type == "study":
        agent = create_study_agent(llm_config, user_id)
    elif agent_type == "plan":
        agent = create_plan_agent(llm_config, user_id)
    else:
        put_nowait({"type": "text_delta", "delta": intent})
        if session_id:
            execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'assistant', %s)",
                (session_id, intent),
            )
        put_nowait({"type": "done"})
        return

    tool_context = json.dumps(tool_results, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": agent.system_message},
        {"role": "system", "content": f"【工具返回的真实数据，禁止编造】\n{tool_context}"},
        {"role": "user", "content": message},
    ]

    # ================================================================
    # Step 5: ★ 真流式 LLM（跨线程提交到主事件循环）
    # ================================================================
    full_text = []
    result_queue = asyncio.Queue()

    async def _stream_llm():
        try:
            async for chunk in llm.stream(messages, max_tokens=4000):
                ctype = chunk.get("type")
                if ctype == "text":
                    put_nowait({"type": "text_delta", "delta": chunk["delta"]})
                    full_text.append(chunk["delta"])
                elif ctype == "error":
                    put_nowait({"type": "error", "message": chunk["message"]})
                    await result_queue.put("error")
                    return
                elif ctype == "done":
                    break
            await result_queue.put("ok")
        except Exception as e:
            put_nowait({"type": "error", "message": str(e)})
            await result_queue.put("error")

    # 提交协程到主事件循环
    asyncio.run_coroutine_threadsafe(_stream_llm(), loop)

    # 轮询等待结果
    while True:
        try:
            # 用 call_soon_threadsafe 从主循环拉结果
            future = asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(result_queue.get(), timeout=120),
                loop
            )
            status = future.result(timeout=130)
            if status in ("ok", "error"):
                break
        except (asyncio.TimeoutError, TimeoutError, Exception):
            put_nowait({"type": "error", "message": "LLM 流式超时"})
            break

    final_text = "".join(full_text)

    # ================================================================
    # Step 6: 发 ui_card（如果 MCP 工具没带）
    # ================================================================
    if not cards_collected:
        card_data = None
        if agent_type == "quiz":
            practice_sid = tool_results.get("prepare_practice_session", {}).get("session_id")
            d = tool_results.get("prepare_practice_session", {}).get("data", {})
            card_data = {
                "type": "practice_ready",
                "session_id": practice_sid,
                "data": {
                    "count": d.get("count", 5),
                    "question_type": d.get("question_type", "混合"),
                    "source": "全题库随机",
                    "estimated_minutes": d.get("estimated_minutes", 15),
                },
            }
        elif agent_type == "study":
            overview = tool_results.get("get_user_study_overview", {})
            weakness = tool_results.get("get_user_weakness", {})
            card_data = {
                "type": "study_report",
                "data": {
                    "total": overview.get("total_answered", 0),
                    "correct_rate": overview.get("correct_rate", 0),
                    "weakest": weakness.get("weakest", ""),
                    "modules": weakness.get("rates", {}),
                    "has_data": weakness.get("has_data", False),
                },
            }
        if card_data:
            cards_collected.append(card_data)
            put_nowait({"type": "ui_card", "card": card_data})

    # ================================================================
    # Step 7: 保存历史
    # ================================================================
    if session_id and final_text:
        try:
            execute(
                "INSERT INTO chat_messages (session_id, role, content, ui_cards) "
                "VALUES (%s, 'assistant', %s, %s)",
                (
                    session_id,
                    final_text,
                    json.dumps(cards_collected, ensure_ascii=False),
                ),
            )
            execute(
                "UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
        except Exception as e:
            log.warning(f"[autogen] 写历史失败: {e}")

    put_nowait({"type": "done"})


def _summarize_tool_result(tname: str, result: dict) -> str:
    r = result.get("result", {})
    if not isinstance(r, dict):
        return "已完成"
    if "summary" in r:
        return r["summary"]
    if "session_id" in r:
        return f"已准备{r.get('data', {}).get('count', '?')}道题"
    if "total_answered" in r:
        return f"{r.get('total_answered', 0)}题, 正确率{r.get('correct_rate', 0)}%"
    if "weakest" in r:
        return f"最弱: {r['weakest']}"
    return "已完成"


def sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class AutogenStreamPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


@router.post("/stream")
async def autogen_stream(
    payload: AutogenStreamPayload,
    user: dict = Depends(current_user),
):
    user_id = user["id"]
    sid = payload.session_id
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    start_time = time.time()

    thread = threading.Thread(
        target=_run_autogen_with_queue,
        args=(payload.message, user_id, sid, queue, loop),
        daemon=True,
    )
    thread.start()

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120)
            except asyncio.TimeoutError:
                yield sse_event("error", {"message": "AutoGen 超时"})
                break

            etype = event.get("type")

            if etype == "done":
                total_ms = int((time.time() - start_time) * 1000)
                yield sse_event("done", {"total_ms": total_ms})
                break

            elif etype == "error":
                yield sse_event("error", {"message": event.get("message", "未知错误")})
                break

            elif etype == "thinking_start":
                yield sse_event("thinking_start", {
                    "label": event.get("label", "思考中"),
                })

            elif etype == "thinking_step":
                yield sse_event("thinking_step", {
                    "detail": event.get("detail", ""),
                })

            elif etype == "tool_call_start":
                yield sse_event("tool_call_start", {
                    "name": event.get("name", ""),
                    "arguments": event.get("arguments", {}),
                })

            elif etype == "tool_call_done":
                yield sse_event("tool_call_done", {
                    "name": event.get("name", ""),
                    "ok": event.get("ok", True),
                    "elapsed_ms": event.get("elapsed_ms", 0),
                    "summary": event.get("summary", "完成"),
                    "error": event.get("error"),
                })

            elif etype == "text_delta":
                yield sse_event("text_delta", {
                    "delta": event.get("delta", ""),
                })

            elif etype == "ui_card":
                yield sse_event("ui_card", {
                    "card": event.get("card", {}),
                })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )