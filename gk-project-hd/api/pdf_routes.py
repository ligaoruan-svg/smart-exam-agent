"""
api/pdf_routes.py - PDF 异步生成任务的状态查询 + 下载

接口：
    GET  /api/pdf/{task_id}/status    查询任务状态（前端轮询）
    GET  /api/pdf/{task_id}/download  完成后下载

任务由 generate_quiz_pdf MCP 工具创建（写入 pdf_jobs 表），
由 api/pdf_worker.py 后台扫描并执行。
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.auth import current_user, optional_user
from api.config import get_logger
from api.db import query_one, execute

log = get_logger("api")

router = APIRouter(prefix="/api/pdf", tags=["pdf"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@router.get("/{task_id}/status")
def task_status(task_id: str, user: dict = Depends(current_user)):
    """
    任务状态。鉴权：登录即可查看自己的任务。
    返回字段：
        task_id       任务 ID
        status        pending / running / completed / failed
        progress      0-100（粗略估算用）
        title         友好标题
        file_name     生成的文件名（completed 时有）
        download_url  下载 URL（completed 时有）
        error_msg     失败原因（failed 时有）
        elapsed_sec   已耗时
    """
    job = query_one(
        "SELECT id, user_id, status, params, question_count, "
        "       title, file_name, file_size, error_msg, "
        "       started_at, completed_at, created_at "
        "FROM pdf_jobs WHERE id = %s",
        (task_id,),
    )
    if not job:
        raise HTTPException(404, "任务不存在")

    # 越权检查
    if int(job["user_id"]) != int(user["id"]) and user.get("role") != "admin":
        raise HTTPException(403, "无权查看他人任务")

    status = job["status"]

    # 粗略 progress：pending=10、running=50、completed=100、failed 保留最后值
    progress_map = {"pending": 5, "running": 50, "completed": 100, "failed": 100}
    progress = progress_map.get(status, 0)

    # elapsed
    if job["completed_at"] and job["started_at"]:
        elapsed = (job["completed_at"] - job["started_at"]).total_seconds()
    elif job["started_at"]:
        from datetime import datetime
        elapsed = (datetime.now() - job["started_at"]).total_seconds()
    else:
        elapsed = 0.0

    resp = {
        "task_id":     job["id"],
        "status":      status,
        "progress":    progress,
        "title":       job["title"] or "",
        "elapsed_sec": int(elapsed),
        "file_name":   job["file_name"],
        "file_size":   job["file_size"],
        "download_url": f"/api/pdf/{task_id}/download" if status == "completed" else None,
        "error_msg":   job["error_msg"] if status == "failed" else None,
    }
    return resp


@router.get("/{task_id}/download")
def download_pdf(task_id: str, user: dict = Depends(current_user)):
    """下载已生成的 PDF"""
    job = query_one(
        "SELECT user_id, status, file_path, file_name FROM pdf_jobs WHERE id = %s",
        (task_id,),
    )
    if not job:
        raise HTTPException(404, "任务不存在")
    if int(job["user_id"]) != int(user["id"]) and user.get("role") != "admin":
        raise HTTPException(403, "无权下载他人 PDF")
    if job["status"] != "completed":
        raise HTTPException(400, f"任务尚未完成（status={job['status']}）")
    if not job["file_path"]:
        raise HTTPException(500, "任务标记为完成但缺少文件路径")

    full = PROJECT_ROOT / job["file_path"]
    if not full.exists():
        raise HTTPException(404, "文件已被清理")

    return FileResponse(
        path=full,
        filename=job["file_name"] or full.name,
        media_type="application/pdf",
    )
