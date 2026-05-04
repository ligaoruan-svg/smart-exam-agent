"""
api/feedback_routes.py - 题目反馈接口
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from api.config import get_logger
from api.auth import current_user, current_admin
from api.db import query_one, query_all, execute

log = get_logger("api")
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    question_id:   int
    feedback_type: str = Field(..., description="answer_wrong/stem_incomplete/option_error/analysis_error/other")
    description:   str = Field("", max_length=1000)
    contact:       Optional[str] = Field(None, max_length=100)


@router.post("")
def submit_feedback(payload: FeedbackPayload, user: dict = Depends(current_user)):
    """用户提交题目反馈"""
    # 验证题目存在
    q = query_one("SELECT id FROM questions WHERE id = %s", (payload.question_id,))
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")

    # 同一用户同一题目同一类型 24小时内只能提交一次（防刷）
    existing = query_one(
        "SELECT id FROM question_feedbacks "
        "WHERE user_id = %s AND question_id = %s AND feedback_type = %s "
        "AND created_at > NOW() - INTERVAL 24 HOUR",
        (user["id"], payload.question_id, payload.feedback_type),
    )
    if existing:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "你已提交过相同反馈，请勿重复提交")

    execute(
        "INSERT INTO question_feedbacks "
        "(user_id, question_id, feedback_type, description, contact, status, priority) "
        "VALUES (%s, %s, %s, %s, %s, 'pending', 2)",
        (user["id"], payload.question_id, payload.feedback_type,
         payload.description or payload.feedback_type, payload.contact),
    )
    log.info(f"[feedback] user={user['id']} question={payload.question_id} type={payload.feedback_type}")
    return {"ok": True, "message": "反馈已提交，感谢！"}


# ============================================================
# 管理员接口
# ============================================================
@router.get("/admin/list")
def list_feedbacks(
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    admin: dict = Depends(current_admin),
):
    """管理员查看所有反馈"""
    conds = ["1=1"]
    params = []
    if status_filter:
        conds.append("f.status = %s")
        params.append(status_filter)

    where = " AND ".join(conds)
    total = query_one(
        f"SELECT COUNT(*) AS n FROM question_feedbacks f WHERE {where}",
        tuple(params)
    )["n"]

    rows = query_all(
        f"SELECT f.*, u.username, q.stem "
        f"FROM question_feedbacks f "
        f"LEFT JOIN users u ON f.user_id = u.id "
        f"LEFT JOIN questions q ON f.question_id = q.id "
        f"WHERE {where} "
        f"ORDER BY f.priority DESC, f.created_at DESC "
        f"LIMIT %s OFFSET %s",
        tuple(params) + (page_size, (page - 1) * page_size),
    )
    return {"total": total, "items": rows}


@router.patch("/admin/{feedback_id}")
def update_feedback(
    feedback_id: int,
    status_val: str,
    admin_reply: Optional[str] = None,
    admin: dict = Depends(current_admin),
):
    """管理员处理反馈（标记状态 + 回复）"""
    execute(
        "UPDATE question_feedbacks SET status=%s, admin_reply=%s, "
        "handler_id=%s, resolved_at=IF(%s='resolved', NOW(), NULL), updated_at=NOW() "
        "WHERE id=%s",
        (status_val, admin_reply, admin["id"], status_val, feedback_id),
    )
    return {"ok": True}
