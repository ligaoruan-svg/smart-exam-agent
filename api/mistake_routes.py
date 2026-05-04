"""
api/mistake_routes.py - 错题本相关 REST 接口

主要职责：
  GET    /api/mistake/list                  错题列表（按 status/题型 筛选 + 分页）
  GET    /api/mistake/stats                 按题型统计数量
  POST   /api/mistake/{wrong_id}/master     标为已掌握 (is_mastered=1)
  POST   /api/mistake/{wrong_id}/unmaster   取消已掌握 (is_mastered=0)
  POST   /api/mistake/{wrong_id}/star       切换星标
  DELETE /api/mistake/{wrong_id}            删除某条错题
  POST   /api/mistake/{wrong_id}/ai-explain AI 解析（缓存优先 + LLM 现生成）

依赖表：
  - wrong_questions          已存在
  - questions                题库
  - answer_records           用户每次答题流水（拿"我选了什么"）
  - wrong_question_ai_analysis  AI 解析缓存（用户已建表）
"""
import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.config import get_logger
from api.auth import current_user
from api.db import query_all, query_one, execute
from api.llm import LLM


def _consume_ai_quota(user: dict) -> None:
    """扣减 AI 功能配额（调用 LLM 前检查）。缓存命中时不调此函数。"""
    if user.get("plan") in ("pro", "enterprise"):
        return
    used  = user.get("daily_used") or 0
    limit = user.get("daily_limit") or 20
    if used >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"今日免费 AI 次数已用完（{used}/{limit}），升级 Pro 解锁不限次数",
        )
    execute("UPDATE users SET daily_used = daily_used + 1 WHERE id = %s", (user["id"],))

log = get_logger("api")

router = APIRouter(prefix="/api/mistake", tags=["mistake"])


# ============================================================
# 工具：拿到用户在某道题"最后一次"答错的选项 + 时间
# 答题流水表：answer_records（结构在 schema.sql 里）
# ============================================================
def _get_last_wrong_answer(user_id: int, question_id: int) -> Optional[dict]:
    try:
        return query_one(
            "SELECT user_answer, is_correct, time_spent, created_at "
            "FROM answer_records "
            "WHERE user_id = %s AND question_id = %s AND is_correct = 0 "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, question_id),
        )
    except Exception as e:
        log.warning(f"[mistake] 查 answer_records 失败：{e}")
        return None


def _batch_get_last_wrong_answers(user_id: int, question_ids: list) -> dict:
    """批量获取用户对多道题最后一次答错的记录，避免 N+1 查询。
    返回 {question_id: {user_answer, ...}} 字典。
    """
    if not question_ids:
        return {}
    try:
        placeholders = ",".join(["%s"] * len(question_ids))
        rows = query_all(
            f"SELECT ar.question_id, ar.user_answer, ar.is_correct, "
            f"       ar.time_spent, ar.created_at "
            f"FROM answer_records ar "
            f"INNER JOIN ( "
            f"    SELECT question_id, MAX(created_at) AS max_at "
            f"    FROM answer_records "
            f"    WHERE user_id = %s AND question_id IN ({placeholders}) AND is_correct = 0 "
            f"    GROUP BY question_id "
            f") latest ON ar.question_id = latest.question_id AND ar.created_at = latest.max_at "
            f"WHERE ar.user_id = %s AND ar.is_correct = 0",
            tuple([user_id] + question_ids + [user_id]),
        )
        return {r["question_id"]: r for r in rows}
    except Exception as e:
        log.warning(f"[mistake] 批量查 answer_records 失败：{e}")
        return {}


# ============================================================
# 错题列表
# ============================================================
@router.get("/list")
def list_mistakes(
    status_filter: Optional[str] = Query(None, alias="status",
        description="all/unmastered/mastered，默认 all"),
    question_type: Optional[str] = Query(None,
        description="言语理解/判断推理/数量关系/资料分析/常识判断"),
    province:  Optional[str] = Query(None),
    year:      Optional[str] = Query(None, description="年份筛选"),
    mode:      str = Query("recent", description="recent=按时间 / review=按复习优先级"),
    page:      int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(current_user),
):
    """获取当前用户的错题列表

    mode:
      - recent: 按最近错题时间倒序（普通列表）
      - review: 按"复习优先级"排序（错过次数多、最近错的、未掌握的排前）
                速复习模式专用
    """
    conds = ["w.user_id = %s"]
    params: list = [user["id"]]

    if status_filter == "unmastered":
        conds.append("w.is_mastered = 0")
    elif status_filter == "mastered":
        conds.append("w.is_mastered = 1")

    if question_type:
        conds.append("q.question_type = %s")
        params.append(question_type)

    if province:
        conds.append("q.province = %s")
        params.append(province)

    if year:
        conds.append("q.year = %s")
        params.append(year)

    where = " AND ".join(conds)

    total = query_one(
        f"SELECT COUNT(*) AS n FROM wrong_questions w "
        f"JOIN questions q ON q.id = w.question_id "
        f"WHERE {where}",
        tuple(params),
    )["n"]

    # 智能排序公式（review 模式）：
    #   priority_score = wrong_count * 10                       (错过次数越多越优先)
    #                  + DATEDIFF(NOW(), last_wrong_at) * (-1)  (越近越优先)
    #                  + (is_mastered=1 ? -1000 : 0)            (已掌握的排到最后)
    if mode == "review":
        order_by = (
            "ORDER BY "
            "  (CASE WHEN w.is_mastered = 1 THEN -1000 ELSE 0 END) DESC, "
            "  w.wrong_count DESC, "
            "  w.last_wrong_at DESC, "
            "  w.id DESC"
        )
    else:
        order_by = "ORDER BY w.last_wrong_at DESC, w.id DESC"

    offset = (page - 1) * page_size
    rows = query_all(
        f"SELECT w.id, w.question_id, w.wrong_count, w.is_mastered, w.is_starred, "
        f"       w.note, w.last_wrong_at, "
        f"       q.province, q.year, q.exam_type, q.question_type, q.sub_type, "
        f"       q.stem, q.option_a, q.option_b, q.option_c, q.option_d, "
        f"       q.answer, q.analysis "
        f"FROM wrong_questions w "
        f"JOIN questions q ON q.id = w.question_id "
        f"WHERE {where} "
        f"{order_by} "
        f"LIMIT %s OFFSET %s",
        tuple(params) + (page_size, offset),
    )

    # 批量查最后错答，避免 N+1（原来 50 条记录 = 50 次 SQL，现在只需 1 次）
    qids = [r["question_id"] for r in rows]
    last_answers = _batch_get_last_wrong_answers(user["id"], qids)

    items = []
    for r in rows:
        last = last_answers.get(r["question_id"])
        items.append({
            "id":            r["id"],
            "question_id":   r["question_id"],
            "wrong_count":   int(r["wrong_count"] or 1),
            "is_mastered":   bool(r["is_mastered"]),
            "is_starred":    bool(r["is_starred"]),
            "note":          r["note"],
            "last_wrong_at": r["last_wrong_at"].isoformat() if r["last_wrong_at"] else None,
            # 题目信息
            "province":      r["province"],
            "year":          r["year"],
            "exam_type":     r["exam_type"],
            "question_type": r["question_type"],
            "sub_type":      r["sub_type"],
            "stem":          r["stem"],
            "options": {
                "A": r["option_a"], "B": r["option_b"],
                "C": r["option_c"], "D": r["option_d"],
            },
            "answer":        r["answer"],
            "analysis":      r["analysis"],
            # 用户答错的内容
            "my_answer":     last["user_answer"] if last else None,
        })

    return {
        "total":     int(total),
        "page":      page,
        "page_size": page_size,
        "items":     items,
    }


# ============================================================
# 按题型统计
# ============================================================
@router.get("/stats")
def stats_by_type(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: dict = Depends(current_user),
):
    """按题型统计错题数 + 总数"""
    conds = ["w.user_id = %s"]
    params: list = [user["id"]]
    if status_filter == "unmastered":
        conds.append("w.is_mastered = 0")
    elif status_filter == "mastered":
        conds.append("w.is_mastered = 1")
    where = " AND ".join(conds)

    rows = query_all(
        f"SELECT q.question_type AS qtype, COUNT(*) AS n "
        f"FROM wrong_questions w JOIN questions q ON q.id = w.question_id "
        f"WHERE {where} "
        f"GROUP BY q.question_type ORDER BY n DESC",
        tuple(params),
    )
    total = sum(int(r["n"]) for r in rows)

    return {
        "total":   total,
        "by_type": [{"question_type": r["qtype"] or "未分类", "count": int(r["n"])} for r in rows],
    }


# ============================================================
# /overview —— 全景图（柱状图 + AI 中总结）
# 速复习视图的"全局视角"页面用这个
# ============================================================
import hashlib

@router.get("/overview")
def overview(
    status_filter: Optional[str] = Query(None, alias="status",
        description="all/unmastered/mastered"),
    question_type: Optional[str] = Query(None),
    province:      Optional[str] = Query(None),
    year:          Optional[str] = Query(None, description="年份筛选"),
    refresh:       bool = Query(False, description="忽略缓存重新生成 AI 总结"),
    only_summary:  bool = Query(False, description="只返回 AI 总结，不返回柱状图（前端单独刷 AI 时省时）"),
    skip_ai:       bool = Query(False, description="跳过 AI 总结（柱状图秒出，AI 由前端再调一次拿）"),
    user: dict = Depends(current_user),
):
    """返回三组柱状图数据 + AI 中总结。
    AI 总结按"用户+筛选条件"hash 缓存 1 小时。

    两阶段加载策略：
      1) 前端先调 ?skip_ai=true → 柱状图瞬间出
      2) 前端再调 ?only_summary=true → 后台等 AI 5-15 秒返回总结
    这样 AI 失败也不影响柱状图。
    """
    conds = ["w.user_id = %s"]
    params: list = [user["id"]]
    if status_filter == "unmastered":
        conds.append("w.is_mastered = 0")
    elif status_filter == "mastered":
        conds.append("w.is_mastered = 1")
    if question_type:
        conds.append("q.question_type = %s")
        params.append(question_type)
    if province:
        conds.append("q.province = %s")
        params.append(province)
    if year:
        conds.append("q.year = %s")
        params.append(year)
    where = " AND ".join(conds)

    # ===== 1) 三组分布（only_summary 时跳过）=====
    by_type = []
    by_province = []
    by_year = []
    if not only_summary:
        by_type = query_all(
            f"SELECT q.question_type AS k, COUNT(*) AS n "
            f"FROM wrong_questions w JOIN questions q ON q.id = w.question_id "
            f"WHERE {where} GROUP BY q.question_type ORDER BY n DESC",
            tuple(params),
        )
        by_province = query_all(
            f"SELECT q.province AS k, COUNT(*) AS n "
            f"FROM wrong_questions w JOIN questions q ON q.id = w.question_id "
            f"WHERE {where} GROUP BY q.province ORDER BY n DESC LIMIT 10",
            tuple(params),
        )
        by_year = query_all(
            f"SELECT q.year AS k, COUNT(*) AS n "
            f"FROM wrong_questions w JOIN questions q ON q.id = w.question_id "
            f"WHERE {where} AND q.year IS NOT NULL "
            f"GROUP BY q.year ORDER BY q.year DESC LIMIT 8",
            tuple(params),
        )

    total = query_one(
        f"SELECT COUNT(*) AS n FROM wrong_questions w "
        f"JOIN questions q ON q.id = w.question_id WHERE {where}",
        tuple(params),
    )["n"] or 0

    # ===== 2) AI 中总结（缓存 1h），skip_ai=true 时跳过 =====
    ai_summary = None
    if total > 0 and not skip_ai:
        cache_key_raw = f"{status_filter or 'all'}|{question_type or ''}|{province or ''}|{year or ''}"
        cache_key = hashlib.md5(cache_key_raw.encode("utf-8")).hexdigest()[:32]

        cached = None if refresh else query_one(
            "SELECT analysis_text, generated_at FROM mistake_overview_cache "
            "WHERE user_id = %s AND cache_key = %s "
            "  AND generated_at > DATE_SUB(NOW(), INTERVAL 1 HOUR) "
            "LIMIT 1",
            (user["id"], cache_key),
        )
        if cached and cached.get("analysis_text"):
            ai_summary = {"text": cached["analysis_text"], "from_cache": True}
        else:
            # 拉前 12 道高优先级错题作为分析样本
            sample_rows = query_all(
                f"SELECT q.question_type, q.sub_type, q.province, q.year, "
                f"       q.stem, q.answer, "
                f"       (SELECT user_answer FROM answer_records "
                f"        WHERE user_id = w.user_id AND question_id = w.question_id "
                f"          AND is_correct = 0 ORDER BY created_at DESC LIMIT 1) AS my_answer "
                f"FROM wrong_questions w JOIN questions q ON q.id = w.question_id "
                f"WHERE {where} "
                f"ORDER BY w.wrong_count DESC, w.last_wrong_at DESC "
                f"LIMIT 12",
                tuple(params),
            )
            try:
                _consume_ai_quota(user)  # 真正调 LLM 前扣配额
                summary_text = _call_llm_for_overview(sample_rows, total, question_type, province)
                # UPSERT 到独立的 overview 缓存表
                try:
                    execute(
                        "INSERT INTO mistake_overview_cache "
                        "(user_id, cache_key, analysis_text, generated_at) "
                        "VALUES (%s, %s, %s, NOW()) "
                        "ON DUPLICATE KEY UPDATE "
                        "  analysis_text = VALUES(analysis_text), "
                        "  generated_at  = VALUES(generated_at)",
                        (user["id"], cache_key, summary_text),
                    )
                except Exception as e:
                    log.warning(f"[mistake] overview 写缓存失败：{e}")
                ai_summary = {"text": summary_text, "from_cache": False}
            except Exception as e:
                log.error(f"[mistake] AI 总结失败：{e}", exc_info=True)
                ai_summary = {"text": "", "from_cache": False, "error": str(e)}

    return {
        "total":       int(total),
        "by_type":     [{"k": r["k"] or "未分类", "n": int(r["n"])} for r in by_type],
        "by_province": [{"k": r["k"] or "未知",   "n": int(r["n"])} for r in by_province],
        "by_year":     [{"k": str(r["k"]),         "n": int(r["n"])} for r in by_year],
        "ai_summary":  ai_summary,
    }


def _call_llm_for_overview(samples: list, total: int,
                           question_type: Optional[str],
                           province: Optional[str]) -> str:
    """调 LLM 生成 200 字左右的中总结"""
    import asyncio

    sample_lines = []
    for i, s in enumerate(samples, 1):
        stem = (s.get("stem") or "")[:50]
        sample_lines.append(
            f"{i}. [{s.get('question_type') or '?'}] {stem}... "
            f"我答 {s.get('my_answer') or '?'}, 正解 {s.get('answer') or '?'}"
        )

    filter_desc = []
    if question_type: filter_desc.append(f"题型={question_type}")
    if province: filter_desc.append(f"省份={province}")
    filter_str = ("筛选条件：" + "、".join(filter_desc)) if filter_desc else "无筛选"

    prompt = f"""你是公考备考名师，下面是学员的错题样本，请用 150-200 字精炼分析他的薄弱点。

# 错题样本（共 {total} 道，节选最该复习的 {len(samples)} 道）
{filter_str}

{chr(10).join(sample_lines)}

# 输出要求
直接输出 markdown，不要 ```代码块，包括三块：

## 🎯 薄弱点
2-3 句话，指出最集中的错误模式（题型/小类/思维误区）。

## 📚 知识点
1-3 个 bullet（用 - 开头），列出最该复习的具体知识点。

## ✅ 行动建议
1 句话给出"先做什么"的具体建议（比如先看哪种小类的 5 道题）。

简练、具体、可执行。不要套话不要长篇。"""

    async def _go():
        llm = LLM()
        text_buf = ""
        messages = [
            {"role": "system",
             "content": "你是公考资深名师，精于诊断学员薄弱点，输出极其简练。"},
            {"role": "user", "content": prompt},
        ]
        async for chunk in llm.stream(messages, tools=None):
            if chunk.get("type") == "text":
                text_buf += chunk.get("delta", "")
            elif chunk.get("type") == "error":
                raise RuntimeError(chunk.get("message") or "LLM 出错")
            elif chunk.get("type") == "done":
                break
        return text_buf.strip()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _go())
                return future.result(timeout=90)
    except RuntimeError:
        pass
    return asyncio.run(_go())


# ============================================================
# 标已掌握 / 取消 / 切换星标 / 删除
# ============================================================
def _ensure_mistake_belongs_to(wrong_id: int, user_id: int) -> dict:
    row = query_one(
        "SELECT id, user_id, question_id, is_mastered, is_starred, note "
        "FROM wrong_questions WHERE id = %s",
        (wrong_id,),
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "错题不存在")
    if row["user_id"] != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权操作")
    return row


@router.post("/{wrong_id}/master")
def mark_mastered(wrong_id: int, user: dict = Depends(current_user)):
    _ensure_mistake_belongs_to(wrong_id, user["id"])
    execute(
        "UPDATE wrong_questions SET is_mastered = 1, updated_at = NOW() "
        "WHERE id = %s AND user_id = %s",
        (wrong_id, user["id"]),
    )
    return {"ok": True, "is_mastered": True}


@router.post("/{wrong_id}/unmaster")
def unmark_mastered(wrong_id: int, user: dict = Depends(current_user)):
    _ensure_mistake_belongs_to(wrong_id, user["id"])
    execute(
        "UPDATE wrong_questions SET is_mastered = 0, updated_at = NOW() "
        "WHERE id = %s AND user_id = %s",
        (wrong_id, user["id"]),
    )
    return {"ok": True, "is_mastered": False}


@router.post("/{wrong_id}/star")
def toggle_star(wrong_id: int, user: dict = Depends(current_user)):
    row = _ensure_mistake_belongs_to(wrong_id, user["id"])
    new_val = 0 if row["is_starred"] else 1
    execute(
        "UPDATE wrong_questions SET is_starred = %s, updated_at = NOW() "
        "WHERE id = %s AND user_id = %s",
        (new_val, wrong_id, user["id"]),
    )
    return {"ok": True, "is_starred": bool(new_val)}


@router.delete("/{wrong_id}")
def delete_mistake(wrong_id: int, user: dict = Depends(current_user)):
    _ensure_mistake_belongs_to(wrong_id, user["id"])
    execute(
        "DELETE FROM wrong_questions WHERE id = %s AND user_id = %s",
        (wrong_id, user["id"]),
    )
    return {"ok": True}


# ============================================================
# AI 解析（核心功能）
# ============================================================
class NoteUpdate(BaseModel):
    note: str = ""


@router.post("/{wrong_id}/note")
def update_note(wrong_id: int, payload: NoteUpdate, user: dict = Depends(current_user)):
    _ensure_mistake_belongs_to(wrong_id, user["id"])
    execute(
        "UPDATE wrong_questions SET note = %s, updated_at = NOW() "
        "WHERE id = %s AND user_id = %s",
        (payload.note, wrong_id, user["id"]),
    )
    return {"ok": True, "note": payload.note}


@router.post("/{wrong_id}/ai-explain")
def ai_explain(
    wrong_id: int,
    refresh: bool = Query(False, description="true 强制重新生成，忽略缓存"),
    user: dict = Depends(current_user),
):
    """
    针对单道错题生成 AI 深度解析。
    - 缓存优先：同一道题已生成过的，秒返
    - refresh=true 强制重新生成
    - 输出 markdown 格式（前端用 markdown-it / marked 渲染）
    """
    row = _ensure_mistake_belongs_to(wrong_id, user["id"])
    qid = row["question_id"]

    # 1. 缓存
    if not refresh:
        cached = query_one(
            "SELECT analysis_text, generated_at FROM wrong_question_ai_analysis "
            "WHERE question_id = %s AND user_id = %s",
            (qid, user["id"]),
        )
        if cached and cached.get("analysis_text"):
            return {
                "from_cache":   True,
                "analysis":     cached["analysis_text"],
                "generated_at": cached["generated_at"].isoformat() if cached["generated_at"] else None,
            }

    # 2. 拉题目 + 用户错答
    q = query_one(
        "SELECT id, province, year, exam_type, question_type, sub_type, "
        "       stem, option_a, option_b, option_c, option_d, "
        "       answer, analysis "
        "FROM questions WHERE id = %s AND is_valid = 1",
        (qid,),
    )
    if not q:
        raise HTTPException(404, "题目已下架或不存在")

    last = _get_last_wrong_answer(user["id"], qid)
    my_answer = (last or {}).get("user_answer") or "?"

    # 3. 调 LLM 生成 markdown 解析（缓存未命中才到这里，扣配额）
    _consume_ai_quota(user)
    prompt = _build_ai_explain_prompt(q, my_answer)
    try:
        analysis_md = _call_llm_for_explain(prompt)
    except Exception as e:
        log.error(f"[mistake] AI 解析失败 wrong_id={wrong_id} qid={qid} err={e}", exc_info=True)
        raise HTTPException(500, f"AI 解析失败：{e}")

    # 4. 写缓存（UPSERT）
    try:
        execute(
            "INSERT INTO wrong_question_ai_analysis "
            "(question_id, user_id, analysis_text, generated_at) "
            "VALUES (%s, %s, %s, NOW()) "
            "ON DUPLICATE KEY UPDATE "
            "  analysis_text = VALUES(analysis_text), "
            "  generated_at  = VALUES(generated_at)",
            (qid, user["id"], analysis_md),
        )
    except Exception as e:
        log.warning(f"[mistake] AI 解析写缓存失败：{e}")

    log.info(f"[mistake] ai-explain 生成 wrong_id={wrong_id} qid={qid} "
             f"len={len(analysis_md)} refresh={refresh}")

    return {
        "from_cache":   False,
        "analysis":     analysis_md,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 内部：构造 prompt + 调 LLM
# ============================================================
def _build_ai_explain_prompt(q: dict, my_answer: str) -> str:
    """构造给 LLM 的单题深度解析 prompt"""
    return f"""你是公考资深名师，请为下面这道**学员做错的题目**写一份深度解析（markdown 格式）。

# 题目信息
- **题型**：{q.get('question_type') or '未分类'}（{q.get('sub_type') or ''}）
- **来源**：{q.get('province') or ''} {q.get('year') or ''} {q.get('exam_type') or ''}

## 题干
{q.get('stem')}

## 选项
- A. {q.get('option_a')}
- B. {q.get('option_b')}
- C. {q.get('option_c')}
- D. {q.get('option_d')}

## 学员选了：**{my_answer}**（错）
## 正确答案：**{q.get('answer')}**

## 原解析
{q.get('analysis') or '(题库无解析)'}

# 你的任务

请按以下结构输出（直接 markdown，不要包 ```markdown 代码块）：

## 🎯 错因诊断
学员选 {my_answer} 反映出什么思维误区？2-3 句话讲清楚。

## 💡 解题思路
正确的思考路径是什么？分步骤讲清楚（编号 1. 2. 3.），让学员下次能复现这个思路。

## 📚 考点延伸
这道题考察的核心知识点是什么？同类题有什么共同特征？记住这一点能多对几道题？

## ⚠️ 易错陷阱
出题人是怎么设的陷阱？{my_answer} 选项为什么诱人但不对？

## 🔑 一句话记忆
用一句话总结这类题的解题口诀，方便快速回忆。

要求：
- 语言要像名师讲课，亲切但专业
- 每段 2-4 句话，不要长篇大论
- 用具体例子说明，不要空话套话
"""


def _call_llm_for_explain(prompt: str) -> str:
    """
    用 LLM 类发一次同步请求，拿完整文本。
    LLM.stream 是异步生成器，我们这里要同步调用 → 跑一个临时 event loop。
    """
    import asyncio

    async def _go():
        llm = LLM()
        text_buf = ""
        messages = [
            {"role": "system",
             "content": "你是公考备考名师，擅长用浅显的语言把抽象的解题思路讲透。"},
            {"role": "user", "content": prompt},
        ]
        async for chunk in llm.stream(messages, tools=None):
            ctype = chunk.get("type")
            if ctype == "text":
                text_buf += chunk.get("delta", "")
            elif ctype == "error":
                raise RuntimeError(chunk.get("message") or "LLM 出错")
            elif ctype == "done":
                break
        return text_buf.strip()

    # 在 fastapi 接口里同步等待异步函数
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # FastAPI 一般跑在 uvicorn 的事件循环里，同步函数里不能直接 run_until_complete
            # 简单做法：用 nest_asyncio，但那需要装包。这里用线程跑一个新 loop。
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _go())
                return future.result(timeout=120)
    except RuntimeError:
        pass
    return asyncio.run(_go())