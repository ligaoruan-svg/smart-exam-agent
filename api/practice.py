"""
api/practice.py - 练习相关 REST 接口

主要职责：
  POST /api/practice/quick-start            ★ 直接出题 + 立即开始（不依赖 AI 对话）
  POST /api/practice/start/{session_id}     pending → active，扣 daily_used，返回题目列表
  POST /api/practice/cancel/{session_id}    pending → cancelled
  POST /api/practice/answer                 提交单题答案
  POST /api/practice/finish/{session_id}    标记完成
  GET  /api/practice/session/{session_id}   获取 session 详情（断点续做用）
  GET  /api/practice/pending                获取当前用户的 pending session（如果有）
"""
import json
import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.config import get_logger
from api.auth import current_user
from api.db import query_one, query_all, execute

log = get_logger("api")

router = APIRouter(prefix="/api/practice", tags=["practice"])


# ============================================================
# Pydantic models
# ============================================================
class AnswerSubmit(BaseModel):
    session_id: str
    question_id: int
    user_answer: str = Field(..., pattern="^[ABCD]$")
    time_spent: int = Field(0, ge=0, le=3600)


class QuickStartPayload(BaseModel):
    """PracticePanel"开始出题"按钮直接出题用"""
    count:         int           = Field(20, ge=1, le=200)
    question_type: Optional[str] = Field(None, description="言语理解/判断推理/...，None=混合")
    province:      Optional[str] = Field(None, description="省份，None=全部省份")


# ============================================================
# 工具函数
# ============================================================
def _ensure_session_belongs_to(session_id: str, user_id: int) -> dict:
    """校验 session 存在且属于当前用户"""
    sess = query_one(
        "SELECT * FROM quiz_sessions WHERE id = %s",
        (session_id,),
    )
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"session {session_id} 不存在")
    if sess["user_id"] != user_id:
        log.warning(f"⚠️ user {user_id} 尝试访问别人的 session {session_id} (owner={sess['user_id']})")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问此 session")
    return sess


def _check_and_consume_daily_quota(user: dict, amount: int = 1) -> dict:
    """检查并扣减每日配额"""
    if user["plan"] in ("pro", "enterprise"):
        return {"ok": True, "remaining": 99999}

    used = user["daily_used"] or 0
    limit = user["daily_limit"] or 20
    remaining = limit - used

    if remaining < amount:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"今日免费额度已用完（{used}/{limit}），升级 pro 解锁不限次数",
        )

    execute(
        "UPDATE users SET daily_used = daily_used + %s WHERE id = %s",
        (amount, user["id"]),
    )
    return {"ok": True, "remaining": remaining - amount}


# ============================================================
# Routes
# ============================================================

@router.post("/quick-start")
def quick_start(payload: QuickStartPayload, user: dict = Depends(current_user)):
    """
    一步出题：从题库随机抽 count 道题（按题型/省份筛选），创建 active session 并直接返回。
    不依赖 AI 对话。前端 PracticePanel 的"开始出题"按钮直接调用。

    流程：
      1. 检查并扣减每日配额
      2. 按筛选条件随机抽题
      3. 把已存在的 pending session 标 cancelled（一用户一活跃 pending）
      4. 创建 active session（直接跳过 pending）
      5. 返回 session_id + 完整题目列表
    """
    count = max(1, min(int(payload.count or 20), 200))

    # 1. 抽题（随机出题不调 AI，不扣配额）
    conds = ["is_valid = 1"]
    params: list = []
    if payload.question_type and payload.question_type != "混合":
        conds.append("question_type = %s")
        params.append(payload.question_type)
    if payload.province and payload.province != "全部":
        conds.append("province = %s")
        params.append(payload.province)

    rows = query_all(
        f"SELECT id FROM questions WHERE {' AND '.join(conds)} "
        f"ORDER BY RAND() LIMIT %s",
        tuple(params) + (count,),
    )
    question_ids = [r["id"] for r in rows]
    if not question_ids:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"找不到符合条件的题目（{payload.question_type or '混合'}, "
            f"{payload.province or '全部省份'}），换个筛选试试",
        )

    # 3. 旧的 pending 一键取消
    execute(
        "UPDATE quiz_sessions SET status = 'cancelled' "
        "WHERE user_id = %s AND status = 'pending'",
        (user["id"],),
    )

    # 4. 创建 active session（跳过 pending，配额已扣）
    session_id = str(uuid.uuid4())
    execute(
        "INSERT INTO quiz_sessions "
        "(id, user_id, session_type, province, question_type, "
        " preset_question_ids, total_count, status, started_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', NOW())",
        (
            session_id, user["id"], "manual_form",
            payload.province, payload.question_type,
            json.dumps(question_ids), len(question_ids),
        ),
    )

    # 5. 拉完整题目数据
    placeholders = ",".join(["%s"] * len(question_ids))
    qrows = query_all(
        f"SELECT id, province, year, exam_type, question_type, sub_type, "
        f"       stem, option_a, option_b, option_c, option_d, "
        f"       answer, analysis, difficulty, source "
        f"FROM questions WHERE id IN ({placeholders}) AND is_valid = 1",
        tuple(question_ids),
    )
    by_id = {r["id"]: r for r in qrows}
    ordered = [by_id[qid] for qid in question_ids if qid in by_id]

    log.info(f"[practice] quick_start session={session_id} user={user['id']} "
             f"count={len(ordered)} type={payload.question_type} prov={payload.province}")

    return {
        "session_id": session_id,
        "status": "active",
        "total_count": len(ordered),
        "questions": [
            {
                "id":            q["id"],
                "province":      q["province"],
                "year":          q["year"],
                "exam_type":     q["exam_type"],
                "question_type": q["question_type"],
                "sub_type":      q["sub_type"],
                "stem":          q["stem"],
                "options": {
                    "A": q["option_a"], "B": q["option_b"],
                    "C": q["option_c"], "D": q["option_d"],
                },
                "answer":     q["answer"],
                "analysis":   q["analysis"],
                "difficulty": q["difficulty"],
                "source":     q["source"],
            }
            for q in ordered
        ],
    }


@router.get("/pending")
def get_pending_session(user: dict = Depends(current_user)):
    """
    返回当前用户的 pending session（如果有），用于：
      - ChatPanel 进入时检查"是否有 AI 已经准备好的练习等我开始"
      - PracticePanel 进入时如果有 pending 可以自动展示
    """
    sess = query_one(
        "SELECT * FROM quiz_sessions "
        "WHERE user_id = %s AND status = 'pending' "
        "ORDER BY started_at DESC LIMIT 1",
        (user["id"],),
    )
    if not sess:
        return {"has_pending": False}

    qids = sess.get("preset_question_ids") or []
    if isinstance(qids, str):
        qids = json.loads(qids)

    return {
        "has_pending": True,
        "session": {
            "id": sess["id"],
            "session_type": sess["session_type"],
            "question_type": sess["question_type"],
            "province": sess["province"],
            "total_count": sess["total_count"],
            "preset_question_count": len(qids) if qids else 0,
            "started_at": str(sess["started_at"]),
        },
    }


@router.get("/session/{session_id}")
def get_session(session_id: str, user: dict = Depends(current_user)):
    """获取 session 详情（断点续做用）"""
    sess = _ensure_session_belongs_to(session_id, user["id"])

    qids = sess.get("preset_question_ids") or []
    if isinstance(qids, str):
        qids = json.loads(qids)

    # 已答的题
    answered = query_all(
        "SELECT question_id, user_answer, is_correct, time_spent, created_at "
        "FROM answer_records WHERE session_id = %s ORDER BY created_at ASC",
        (session_id,),
    )

    return {
        "id": sess["id"],
        "status": sess["status"],
        "session_type": sess["session_type"],
        "question_type": sess["question_type"],
        "total_count": sess["total_count"],
        "answered_count": sess["answered_count"],
        "correct_count": sess["correct_count"],
        "preset_question_ids": qids,
        "answered": [
            {
                "question_id": a["question_id"],
                "user_answer": a["user_answer"],
                "is_correct": bool(a["is_correct"]),
                "time_spent": a["time_spent"],
            }
            for a in answered
        ],
        "started_at": str(sess["started_at"]),
        "completed_at": str(sess["completed_at"]) if sess["completed_at"] else None,
    }


@router.post("/start/{session_id}")
def start_session(session_id: str, user: dict = Depends(current_user)):
    """
    启动一个 pending session。
    pending → active，并扣减每日配额，返回完整题目列表。
    """
    sess = _ensure_session_belongs_to(session_id, user["id"])

    # 状态校验
    if sess["status"] == "active":
        log.info(f"session {session_id} 已经是 active 状态，幂等返回")
    elif sess["status"] != "pending":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"session 状态为 {sess['status']}，无法启动",
        )

    qids_raw = sess.get("preset_question_ids") or []
    if isinstance(qids_raw, str):
        qids_raw = json.loads(qids_raw)
    if not qids_raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "session 没有预设题目")

    # 扣配额（按题数扣）
    if sess["status"] == "pending":
        _check_and_consume_daily_quota(user, amount=len(qids_raw))

    # 拉题目（按 preset_question_ids 顺序）
    placeholders = ",".join(["%s"] * len(qids_raw))
    rows = query_all(
        f"SELECT id, province, year, exam_type, question_type, sub_type, "
        f"       stem, option_a, option_b, option_c, option_d, "
        f"       answer, analysis, difficulty, source "
        f"FROM questions WHERE id IN ({placeholders}) AND is_valid = 1",
        tuple(qids_raw),
    )
    # 按预设顺序排回去（IN 查询不保证顺序）
    by_id = {r["id"]: r for r in rows}
    ordered = [by_id[qid] for qid in qids_raw if qid in by_id]

    # 状态更新
    if sess["status"] == "pending":
        execute(
            "UPDATE quiz_sessions SET status = 'active', started_at = NOW() WHERE id = %s",
            (session_id,),
        )
        log.info(f"[practice] session {session_id} pending → active, "
                 f"user={user['id']}, count={len(ordered)}")

    return {
        "session_id": session_id,
        "status": "active",
        "total_count": len(ordered),
        "questions": [
            {
                "id": q["id"],
                "province": q["province"],
                "year": q["year"],
                "exam_type": q["exam_type"],
                "question_type": q["question_type"],
                "sub_type": q["sub_type"],
                "stem": q["stem"],
                "options": {
                    "A": q["option_a"], "B": q["option_b"],
                    "C": q["option_c"], "D": q["option_d"],
                },
                "answer": q["answer"],
                "analysis": q["analysis"],
                "difficulty": q["difficulty"],
                "source": q["source"],
            }
            for q in ordered
        ],
    }


@router.post("/cancel/{session_id}")
def cancel_session(session_id: str, user: dict = Depends(current_user)):
    """取消 pending/active session"""
    sess = _ensure_session_belongs_to(session_id, user["id"])

    if sess["status"] in ("completed", "cancelled"):
        return {"ok": True, "msg": f"session 已经是 {sess['status']} 状态"}

    execute(
        "UPDATE quiz_sessions SET status = 'cancelled', completed_at = NOW() WHERE id = %s",
        (session_id,),
    )
    log.info(f"[practice] session {session_id} cancelled by user {user['id']}")
    return {"ok": True}


# ============================================================
# 薄弱点更新（每次答题后异步计算，从 answer_records 实时统计）
# ============================================================

# 题型字段映射
_TYPE_FIELD_MAP = {
    "言语理解": "rate_yanyu",
    "判断推理": "rate_panduan",
    "数量关系": "rate_shuliang",
    "常识判断": "rate_changshi",
    "申论":     "rate_shenglun",
    "图形推理": "rate_tuli",
    "资料分析": "rate_ziliao",
}

def _update_weakness(user_id: int, question_type: str, province: str) -> None:
    """
    答题后重新计算该用户的薄弱点数据并写入 user_weaknesses 表。
    只更新本次答题涉及的题型和省份，其余字段保持不变。
    失败不影响主流程。
    """
    try:
        # 1. 计算所有题型的错误率（从 answer_records JOIN questions）
        rates = {}
        for qt, field in _TYPE_FIELD_MAP.items():
            row = query_one(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN ar.is_correct=0 THEN 1 ELSE 0 END) AS wrong "
                "FROM answer_records ar "
                "JOIN questions q ON ar.question_id = q.id "
                "WHERE ar.user_id = %s AND q.question_type = %s",
                (user_id, qt),
            )
            total = int(row["total"] or 0)
            wrong = int(row["wrong"] or 0)
            rates[field] = round(wrong / total, 3) if total > 0 else 0.0

        # 2. 计算各省错误率（只统计答题数 >= 5 的省份，避免样本太少失真）
        province_rows = query_all(
            "SELECT q.province, COUNT(*) AS total, "
            "       SUM(CASE WHEN ar.is_correct=0 THEN 1 ELSE 0 END) AS wrong "
            "FROM answer_records ar "
            "JOIN questions q ON ar.question_id = q.id "
            "WHERE ar.user_id = %s AND q.province IS NOT NULL "
            "GROUP BY q.province HAVING total >= 5",
            (user_id,),
        )
        province_rates = {
            r["province"]: round(int(r["wrong"] or 0) / int(r["total"]), 3)
            for r in province_rows
        }

        # 3. UPSERT 写入 user_weaknesses
        import json as _json
        execute(
            "INSERT INTO user_weaknesses "
            "(user_id, rate_yanyu, rate_panduan, rate_shuliang, rate_changshi, "
            " rate_shenglun, rate_tuli, rate_ziliao, weakness_provinces, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) "
            "ON DUPLICATE KEY UPDATE "
            "rate_yanyu=%s, rate_panduan=%s, rate_shuliang=%s, rate_changshi=%s, "
            "rate_shenglun=%s, rate_tuli=%s, rate_ziliao=%s, "
            "weakness_provinces=%s, updated_at=NOW()",
            (
                user_id,
                rates["rate_yanyu"], rates["rate_panduan"], rates["rate_shuliang"],
                rates["rate_changshi"], rates["rate_shenglun"], rates["rate_tuli"],
                rates["rate_ziliao"], _json.dumps(province_rates, ensure_ascii=False),
                # ON DUPLICATE KEY UPDATE values
                rates["rate_yanyu"], rates["rate_panduan"], rates["rate_shuliang"],
                rates["rate_changshi"], rates["rate_shenglun"], rates["rate_tuli"],
                rates["rate_ziliao"], _json.dumps(province_rates, ensure_ascii=False),
            ),
        )
    except Exception as e:
        log.warning(f"[practice] 更新薄弱点失败 user_id={user_id} err={e}")


@router.post("/answer")
def submit_answer(payload: AnswerSubmit, user: dict = Depends(current_user)):
    """
    提交单题答案。
    会做几件事：
      1. 查正确答案，对比 → is_correct
      2. 写 answer_records
      3. 如果错了，写/更新 wrong_questions
      4. 更新 session 的 answered_count / correct_count
      5. 更新 user 的 total_answered / total_correct
      6. 更新 question 的 total_attempts / correct_count
    """
    sess = _ensure_session_belongs_to(payload.session_id, user["id"])

    if sess["status"] != "active":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"session 状态为 {sess['status']}，无法提交答案",
        )

    # 查题目
    q = query_one(
        "SELECT id, answer FROM questions WHERE id = %s",
        (payload.question_id,),
    )
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")

    is_correct = (payload.user_answer.upper() == q["answer"].upper())

    # 写 answer_records
    execute(
        "INSERT INTO answer_records "
        "(user_id, question_id, session_id, user_answer, is_correct, time_spent) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (user["id"], payload.question_id, payload.session_id,
         payload.user_answer.upper(), 1 if is_correct else 0, payload.time_spent),
    )

    # 错题处理
    if not is_correct:
        execute(
            "INSERT INTO wrong_questions (user_id, question_id, wrong_count, last_wrong_at) "
            "VALUES (%s, %s, 1, NOW()) "
            "ON DUPLICATE KEY UPDATE wrong_count = wrong_count + 1, last_wrong_at = NOW(), is_mastered = 0",
            (user["id"], payload.question_id),
        )
    else:
        # 答对了，如果之前是错题且已经做对几次，标记为掌握（简单策略：连续答对 1 次）
        execute(
            "UPDATE wrong_questions SET is_mastered = 1 "
            "WHERE user_id = %s AND question_id = %s",
            (user["id"], payload.question_id),
        )

    # 更新 session 计数
    execute(
        "UPDATE quiz_sessions SET answered_count = answered_count + 1, "
        "correct_count = correct_count + %s WHERE id = %s",
        (1 if is_correct else 0, payload.session_id),
    )

    # 更新用户总数
    execute(
        "UPDATE users SET total_answered = total_answered + 1, "
        "total_correct = total_correct + %s WHERE id = %s",
        (1 if is_correct else 0, user["id"]),
    )

    # 更新题目热度
    execute(
        "UPDATE questions SET total_attempts = total_attempts + 1, "
        "correct_count = correct_count + %s WHERE id = %s",
        (1 if is_correct else 0, payload.question_id),
    )

    # 更新薄弱点（拉题目的题型和省份用于统计）
    q_full = query_one(
        "SELECT question_type, province FROM questions WHERE id = %s",
        (payload.question_id,),
    )
    if q_full:
        _update_weakness(user["id"], q_full["question_type"], q_full["province"])

    return {
        "ok": True,
        "is_correct": is_correct,
        "correct_answer": q["answer"],
    }


@router.post("/finish/{session_id}")
def finish_session(session_id: str, user: dict = Depends(current_user)):
    """标记 session 完成"""
    sess = _ensure_session_belongs_to(session_id, user["id"])
    if sess["status"] == "completed":
        return {"ok": True, "msg": "已完成"}
    if sess["status"] != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"session 状态为 {sess['status']}，无法标记完成")

    # 计算总用时
    duration_sql = (
        "UPDATE quiz_sessions SET status = 'completed', completed_at = NOW(), "
        "duration_seconds = TIMESTAMPDIFF(SECOND, started_at, NOW()) "
        "WHERE id = %s"
    )
    execute(duration_sql, (session_id,))

    # 拉最终统计
    final = query_one(
        "SELECT total_count, answered_count, correct_count, duration_seconds "
        "FROM quiz_sessions WHERE id = %s",
        (session_id,),
    )
    log.info(f"[practice] session {session_id} completed | "
             f"{final['correct_count']}/{final['answered_count']}/{final['total_count']}")
    return {"ok": True, "stats": final}