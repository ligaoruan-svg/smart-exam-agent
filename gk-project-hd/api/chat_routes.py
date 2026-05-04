"""
api/chat_routes.py - 对话相关接口

  GET  /api/chat/sessions               列出对话会话
  POST /api/chat/sessions               新建对话
  DELETE /api/chat/sessions/{id}        删除对话
  GET  /api/chat/sessions/{id}/messages 获取某会话的消息历史
  POST /api/chat/stream                 ★ 核心：流式对话（SSE）
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from api.config import get_logger
from api.auth import current_user
from api.db import query_one, query_all, execute
from api.chat_engine import (
    stream_chat, create_chat_session, list_chat_sessions,
)
import httpx

# AutoGen 触发关键词
_AUTOGEN_KEYWORDS = [
    "学习计划", "备考计划", "冲刺计划", "帮我规划",
    "复习计划", "备考建议", "深度分析学习",
]

def _should_use_autogen(message: str) -> bool:
    """判断是否需要走 AutoGen 多 Agent"""
    return any(kw in message for kw in _AUTOGEN_KEYWORDS)


# ============================================================
# 配额检查（复用 practice.bak.py 里的逻辑，直接内联避免循环 import）
# ============================================================
def _check_and_consume_chat_quota(user: dict) -> None:
    """
    检查并扣减 AI 对话每日配额。
    pro/enterprise 用户不限次数。
    免费用户默认每日 20 次（daily_limit 字段控制）。
    """
    if user.get("plan") in ("pro", "enterprise"):
        return  # 付费用户直接放行

    used = user.get("daily_used") or 0
    limit = user.get("daily_limit") or 20

    if used >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"今日免费 AI 对话次数已用完（{used}/{limit}），升级 Pro 解锁不限次数",
        )

    # 扣减配额
    execute(
        "UPDATE users SET daily_used = daily_used + 1 WHERE id = %s",
        (user["id"],),
    )


log = get_logger("chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ============================================================
# 用户画像构建（每次对话自动注入，让 AI 了解用户）
# ============================================================
def _build_user_profile(user_id: int, username: str) -> str:
    """
    从数据库读取用户学习数据，生成简洁的用户画像文字，
    注入到 system 消息，让 AI 一开始就知道在跟谁说话。
    失败不影响主流程，返回空字符串。
    """
    try:
        # 1. 基础答题情况
        u = query_one(
            "SELECT total_answered, total_correct, plan, daily_used, daily_limit "
            "FROM users WHERE id = %s", (user_id,)
        )
        if not u:
            return ""

        total = u["total_answered"] or 0
        correct = u["total_correct"] or 0
        rate = round(correct / total * 100) if total else 0

        lines = [
            f"【当前用户画像】",
            f"用户：{username}（{u.get('plan') or 'free'}版）",
            f"答题总数：{total} 题，综合正确率：{rate}%",
        ]

        # 2. 薄弱点
        w = query_one(
            "SELECT rate_yanyu, rate_panduan, rate_shuliang, "
            "       rate_changshi, rate_tuli, rate_ziliao "
            "FROM user_weaknesses WHERE user_id = %s", (user_id,)
        )
        if w:
            type_map = {
                "言语理解": float(w.get("rate_yanyu") or 0),
                "判断推理": float(w.get("rate_panduan") or 0),
                "数量关系": float(w.get("rate_shuliang") or 0),
                "常识判断": float(w.get("rate_changshi") or 0),
            }
            weak = [(k, v) for k, v in type_map.items() if v > 0]
            weak.sort(key=lambda x: -x[1])
            if weak:
                top3 = "、".join(f"{k}({round(v * 100)}%错误率)" for k, v in weak[:3])
                lines.append(f"薄弱题型（前3）：{top3}")
                lines.append(f"最弱模块：{weak[0][0]}（重点关注）")

        # 3. 未掌握错题数
        wrong = query_one(
            "SELECT COUNT(*) AS n FROM wrong_questions "
            "WHERE user_id = %s AND is_mastered = 0", (user_id,)
        )
        if wrong and wrong["n"]:
            lines.append(f"待复习错题：{wrong['n']} 道")

        # 4. 最近一次练习
        last = query_one(
            "SELECT question_type, correct_count, answered_count, started_at "
            "FROM quiz_sessions WHERE user_id = %s AND status = 'completed' "
            "ORDER BY started_at DESC LIMIT 1", (user_id,)
        )
        if last and last["started_at"]:
            date = str(last["started_at"])[:10]
            qt = last["question_type"] or "混合"
            score = f"{last['correct_count']}/{last['answered_count']}"
            lines.append(f"最近练习：{date} 做了{qt} {score}")

        lines.append("（以上数据供你主动关怀用户、智能推荐使用，无需用户重复说明）")
        return "\n".join(lines)

    except Exception as e:
        log.warning(f"[chat] 构建用户画像失败 user_id={user_id} err={e}")
        return ""


# ------------------------------------------------------------
# 历史卡片摘要：让 LLM 在多轮对话中"看见"自己之前发过什么
# 这是防幻觉的关键 — 没有这一步，LLM 会假装"上面有 ZIP/PDF"
# ------------------------------------------------------------
def _describe_card_for_history(card: dict) -> str:
    """把一张 ui_card 浓缩成一行文字，给 LLM 看"""
    if not isinstance(card, dict):
        return "未知卡片"
    ctype = card.get("type", "?")
    data = card.get("data") or {}
    if ctype == "pack_ready":
        label = data.get("file_label") or f"{data.get('province', '?')}公考真题"
        cnt = data.get("paper_count")
        size = data.get("size_mb")
        bits = [f"📦 {label} (ZIP)"]
        if cnt: bits.append(f"{cnt} 份")
        if size: bits.append(f"{size} MB")
        return ", ".join(bits)
    if ctype == "pdf_generating":
        cnt = data.get("count", "?")
        qt = data.get("question_type") or "混合"
        prov = data.get("province") or "全部"
        return f"📄 实时生成的 PDF 练习卷 ({cnt} 题, {qt}, {prov})"
    if ctype == "practice_ready":
        cnt = data.get("count", "?")
        qt = data.get("question_type") or "混合"
        return f"📝 在线练习 session ({cnt} 题, {qt})"
    return f"{ctype} 卡片"


class StreamPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None  # 不传则创建新会话


class CreateSessionPayload(BaseModel):
    title: Optional[str] = None


# ============================================================
# 会话管理
# ============================================================

@router.get("/sessions")
def list_sessions(user: dict = Depends(current_user)):
    sessions = list_chat_sessions(user["id"])
    return {"sessions": sessions}


@router.post("/sessions")
def new_session(payload: CreateSessionPayload, user: dict = Depends(current_user)):
    sid = create_chat_session(user["id"], payload.title)
    return {"id": sid, "title": payload.title or "新对话"}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user: dict = Depends(current_user)):
    sess = query_one("SELECT user_id FROM chat_sessions WHERE id = %s", (session_id,))
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    if sess["user_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权删除")
    execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, user: dict = Depends(current_user)):
    sess = query_one("SELECT user_id FROM chat_sessions WHERE id = %s", (session_id,))
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    if sess["user_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看")

    messages = query_all(
        "SELECT id, role, content, ui_cards, created_at FROM chat_messages "
        "WHERE session_id = %s ORDER BY created_at ASC LIMIT 200",
        (session_id,),
    )
    out = []
    for m in messages:
        cards = m.get("ui_cards")
        if isinstance(cards, str):
            try:
                cards = json.loads(cards)
            except Exception:
                cards = None
        out.append({
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "ui_cards": cards or [],
            "created_at": str(m["created_at"]),
        })
    return {"messages": out}


# ============================================================
# 流式对话（核心）
# ============================================================

@router.post("/stream")
async def stream(
        payload: StreamPayload,
        request: Request,
        user: dict = Depends(current_user),
):
    """
    流式对话。返回 text/event-stream（SSE）。

    前端用法（浏览器原生 fetch + ReadableStream）：
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({ message, session_id }),
        });
        const reader = resp.body.getReader();
        // ... 解析 event: xxx\ndata: {...}\n\n
    """
    # 配额检查（防止滥用烧钱）
    _check_and_consume_chat_quota(user)

    # 如果没传 session_id，自动创建
    sid = payload.session_id
    if not sid:
        sid = create_chat_session(user["id"], payload.message[:30])
        log.info(f"[chat] 新建会话 {sid} for user {user['id']}")

    # 拉历史
    # 只取最近 12 条（约 6 个对话回合），太多会稀释 LLM 注意力，导致后续调工具失败
    history_rows = query_all(
        "SELECT role, content, ui_cards FROM chat_messages "
        "WHERE session_id = %s ORDER BY created_at DESC LIMIT 20",
        (sid,),
    )
    # 注意上面是 DESC（取最新 N 条），需要再倒回来变成时间正序
    history_rows = list(reversed(history_rows))
    history = []
    # 同时收集"本对话已发出的卡片"清单 —— 用来给 LLM 一个独立的 system 消息
    # （不污染 assistant.content，避免 LLM 复述）
    all_card_summaries: list[str] = []
    for r in history_rows:
        history.append({"role": r["role"], "content": r["content"] or ""})
        if r["role"] == "assistant" and r.get("ui_cards"):
            try:
                cards = json.loads(r["ui_cards"]) if isinstance(r["ui_cards"], str) else r["ui_cards"]
            except Exception:
                cards = []
            for c in (cards or []):
                all_card_summaries.append(_describe_card_for_history(c))

    async def event_generator():
        # 先告诉前端 session_id（万一是新建的，前端要用）
        yield f"event: session\ndata: {json.dumps({'session_id': sid})}\n\n"

        # ── AutoGen 路由判断 ──
        if _should_use_autogen(payload.message):
            log.info(f"[chat] 路由到 AutoGen | user={user['id']} msg={payload.message[:50]}")
            try:
                # 调用 AutoGen 流式接口，透传 SSE 事件给前端
                async with httpx.AsyncClient(timeout=180) as client:
                    async with client.stream(
                        "POST",
                        "http://localhost:8900/api/autogen/stream",
                        json={"message": payload.message, "session_id": sid},
                        headers={"Authorization": request.headers.get("Authorization", "")},
                    ) as resp:
                        async for chunk in resp.aiter_bytes():
                            if chunk:
                                yield chunk
            except Exception as e:
                log.error(f"[autogen] 调用失败: {e}")
                yield f"event: text_delta\ndata: {json.dumps({'delta': f'多Agent系统暂时不可用：{e}'}, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'total_ms': 0, 'message_id': None})}\n\n"
            return

        # ── 普通 MCP Agent ──
        # 构建用户画像（每次对话自动注入）
        user_profile = _build_user_profile(user["id"], user.get("username", ""))

        async for chunk in stream_chat(
                user_id=user["id"],
                user_message=payload.message,
                chat_session_id=sid,
                history=history,
                cards_history=all_card_summaries,
                user_profile=user_profile,
        ):
            # 客户端断开就停止
            if await request.is_disconnected():
                log.info(f"[chat] 客户端断开 session={sid}")
                return
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
            "Connection": "keep-alive",
        },
    )