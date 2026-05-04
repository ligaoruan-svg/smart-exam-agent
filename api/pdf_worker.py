"""
api/pdf_worker.py - PDF 异步生成 worker

由 FastAPI lifespan 启动一个后台 task，定时（每 2 秒）扫 pdf_jobs 表里
status='pending' 的任务，调 skills/gk-quiz-html 渲染 PDF。

设计要点：
  - 单 worker、单实例（FastAPI 进程内一个就够）
  - playwright 是 sync API，所以渲染部分用 run_in_threadpool
  - 任务完成把 file_path 写回 pdf_jobs，供 /api/pdf/{id}/download 用
"""
import asyncio
import importlib
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi.concurrency import run_in_threadpool

from api.config import get_logger
from api.db import query_all, query_one, execute

log = get_logger("api")

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
PDF_OUT_DIR   = PROJECT_ROOT / "zips_temp"   # 跟你现有目录一致
PDF_OUT_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL_SEC = 2
JOB_TIMEOUT_SEC   = 180  # 单个任务超时（防卡死）


# ============================================================
# 动态 import skill（目录名带横线没法直接 import）
# ============================================================
_skill_module = None


def _load_skill():
    """import skills/gk-quiz-html (目录名有横线)"""
    global _skill_module
    if _skill_module is not None:
        return _skill_module

    skill_dir = PROJECT_ROOT / "skills" / "gk-quiz-html"
    if not skill_dir.exists():
        raise FileNotFoundError(f"skill 目录不存在: {skill_dir}")

    # 把 skill 目录加进 sys.path 直接 import 它的子模块
    if str(skill_dir) not in sys.path:
        sys.path.insert(0, str(skill_dir))

    render = importlib.import_module("render")
    to_pdf = importlib.import_module("to_pdf")

    import types
    _skill_module = types.SimpleNamespace(
        render_quiz_html=render.render_quiz_html,
        html_to_pdf=to_pdf.html_to_pdf,
    )
    log.info(f"✅ 加载 skill: {skill_dir}")
    return _skill_module


# ============================================================
# 题目格式转换：questions 表行 → skill 要的 JSON
# ============================================================
def _row_to_skill_question(row: dict, idx: int) -> dict:
    """
    skill 要的字段：
        id, type, source, stem, options{A,B,C,D}, answer, analysis
    """
    return {
        "id":     idx,
        "type":   row.get("question_type") or "未分类",
        "source": f"{row.get('year', '')}年 {row.get('province', '')} {row.get('exam_type', '')}",
        "province": row.get("province") or "",
        "stem":   (row.get("stem") or "").strip(),
        "options": {
            "A": (row.get("option_a") or "").strip(),
            "B": (row.get("option_b") or "").strip(),
            "C": (row.get("option_c") or "").strip(),
            "D": (row.get("option_d") or "").strip(),
        },
        "answer":   (row.get("answer") or "").strip().upper(),
        "analysis": (row.get("analysis") or "").strip(),
    }


def _fetch_questions(question_ids: list[int]) -> list[dict]:
    """按 ID 顺序拉题"""
    if not question_ids:
        return []
    placeholders = ",".join(["%s"] * len(question_ids))
    rows = query_all(
        f"SELECT id, province, year, exam_type, question_type, sub_type, "
        f"       stem, option_a, option_b, option_c, option_d, answer, analysis "
        f"FROM questions WHERE id IN ({placeholders})",
        tuple(question_ids),
    )
    # 保持原始顺序
    by_id = {r["id"]: r for r in rows}
    return [_row_to_skill_question(by_id[qid], i + 1)
            for i, qid in enumerate(question_ids) if qid in by_id]


# ============================================================
# 友好文件名
# ============================================================
def _make_friendly_filename(province: Optional[str], qtype: Optional[str],
                              count: int, task_id: str) -> str:
    """quiz_广东_言语理解_10题_xxx.pdf"""
    parts = ["quiz"]
    if province and province != "全部":
        parts.append(province)
    if qtype and qtype != "混合":
        parts.append(qtype)
    parts.append(f"{count}题")
    parts.append(task_id[:8])
    safe = "_".join(parts)
    # 防 OS 不喜欢的字符
    for bad in r'/\:*?"<>|':
        safe = safe.replace(bad, "")
    return f"{safe}.pdf"


# ============================================================
# 单任务处理
# ============================================================
async def _process_job(job: dict):
    task_id = job["id"]
    log.info(f"[pdf_worker] ▶ 开始任务 {task_id}")

    # 1. 标记 running
    execute(
        "UPDATE pdf_jobs SET status='running', started_at=NOW() "
        "WHERE id=%s AND status='pending'",
        (task_id,),
    )

    try:
        params = job["params"]
        if isinstance(params, str):
            params = json.loads(params)

        question_ids = params.get("question_ids") or []
        province     = params.get("province")
        qtype        = params.get("question_type")
        count        = params.get("count") or len(question_ids)

        if not question_ids:
            raise RuntimeError("任务缺少 question_ids")

        # 2. 拉题
        questions = await run_in_threadpool(_fetch_questions, question_ids)
        if len(questions) < 1:
            raise RuntimeError("没有抽到题目")

        # 3. 标题
        title_parts = []
        if province and province != "全部":
            title_parts.append(province)
        if qtype and qtype != "混合":
            title_parts.append(qtype)
        title_parts.append(f"{len(questions)}题模拟练习")
        title = job.get("title") or " ".join(title_parts)

        # 4. 渲染 + 写盘（全部塞进 thread，因为 playwright 是 sync）
        out_name = _make_friendly_filename(province, qtype, len(questions), task_id)
        out_path = PDF_OUT_DIR / out_name

        skill = _load_skill()

        def _render_and_save():
            html = skill.render_quiz_html(questions, title=title)
            skill.html_to_pdf(html, str(out_path))

        await run_in_threadpool(_render_and_save)

        if not out_path.exists():
            raise RuntimeError("PDF 文件未生成")

        size = out_path.stat().st_size
        rel  = f"zips_temp/{out_name}"

        # 5. 写回 completed
        execute(
            "UPDATE pdf_jobs SET status='completed', completed_at=NOW(), "
            "       title=%s, file_name=%s, file_path=%s, file_size=%s "
            "WHERE id=%s",
            (title, out_name, rel, size, task_id),
        )
        log.info(f"[pdf_worker] ✅ 完成 {task_id} | {out_name} | {size} bytes")

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        log.error(f"[pdf_worker] ❌ 任务 {task_id} 失败: {err}")
        log.error(traceback.format_exc())
        execute(
            "UPDATE pdf_jobs SET status='failed', completed_at=NOW(), error_msg=%s "
            "WHERE id=%s",
            (err[:1000], task_id),
        )


# ============================================================
# Worker 主循环
# ============================================================
_worker_task: Optional[asyncio.Task] = None
_should_stop = False


async def _worker_loop():
    log.info(f"[pdf_worker] 启动 | 输出目录={PDF_OUT_DIR}")
    while not _should_stop:
        try:
            # 把卡在 running 太久的任务标记为 failed（防止上次崩了的脏数据）
            execute(
                "UPDATE pdf_jobs SET status='failed', "
                "       error_msg=COALESCE(error_msg, '执行超时或进程崩溃'), "
                "       completed_at=NOW() "
                "WHERE status='running' "
                "  AND TIMESTAMPDIFF(SECOND, started_at, NOW()) > %s",
                (JOB_TIMEOUT_SEC,),
            )

            # 取一条 pending
            job = query_one(
                "SELECT id, user_id, status, params, title FROM pdf_jobs "
                "WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
            )
            if job:
                await _process_job(job)
            else:
                await asyncio.sleep(POLL_INTERVAL_SEC)
        except asyncio.CancelledError:
            log.info("[pdf_worker] 收到取消信号")
            break
        except Exception as e:
            log.error(f"[pdf_worker] 主循环异常: {e}", exc_info=True)
            await asyncio.sleep(POLL_INTERVAL_SEC)
    log.info("[pdf_worker] 退出")


def start_worker():
    """FastAPI lifespan 启动时调"""
    global _worker_task, _should_stop
    if _worker_task and not _worker_task.done():
        return
    _should_stop = False
    loop = asyncio.get_event_loop()
    _worker_task = loop.create_task(_worker_loop(), name="pdf_worker")
    log.info("[pdf_worker] 后台 task 已创建")


async def stop_worker():
    """FastAPI lifespan 关闭时调"""
    global _should_stop
    _should_stop = True
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
