"""
mcp/mcp_server.py - 公考小智 v2 MCP Server

17 个工具，按职能分 6 类：
  字典查询      list_provinces, list_years, list_question_types
  题库查询      search_questions, get_random_questions, get_question_by_id,
              get_shenglun_questions, get_shenglun_by_id
  试卷查询      search_papers, get_paper_by_id
  用户学情      get_user_study_overview, get_recent_wrongs,
              get_recent_sessions, get_user_weakness
  写操作        prepare_practice_session, trigger_pack_province,
              generate_quiz_pdf, list_extras, download_extra

启动方式：
  stdio 模式（Claude Desktop 用）：
    python mcp_server.py

  SSE 模式（FastAPI BFF / RAGFlow 用）：
    MCP_MODE=sse MCP_PORT=8765 python mcp_server.py

环境变量：
  DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME    数据库连接
  MCP_MODE=stdio|sse                                     传输模式
  MCP_PORT=8765                                          SSE 端口
  ZIPS_DIR=...                                           ZIP 文件目录
  PDF_OUTPUT_DIR=...                                     生成 PDF 输出目录
  API_BASE=http://localhost:8900                         BFF 地址（构造下载 URL 用）
"""

import os
import sys
import json
import uuid
import random
from typing import Optional
from datetime import datetime
from pathlib import Path

# 让相对 import 在 Claude Desktop spawn 子进程时也能正常工作
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from db import (
    query_all, query_one, execute, execute_returning_id,
    get_db, load_dict_cache,
    get_provinces_cached, get_plans_cached,
)
from auth import require_user, require_admin, AuthError


# ============================================================
# 配置
# ============================================================
API_BASE       = os.environ.get("API_BASE", "http://localhost:8900")
ZIPS_DIR       = Path(os.environ.get("ZIPS_DIR", "./zips"))
PDF_OUTPUT_DIR = Path(os.environ.get("PDF_OUTPUT_DIR", "./pdf_output"))

# 行测里你还没清洗的题型，默认排除（清洗完后改这里就放开）
EXCLUDED_QUESTION_TYPES = ("图形推理", "资料分析", "申论")

# 单次最多抽多少题（防 LLM 让 SQL 抽 10000 道）
MAX_QUESTIONS_PER_CALL = 100

# 学情概览里"最近"的滑动窗口
RECENT_WINDOW_DAYS = 30


# ============================================================
# 启动初始化
# ============================================================
mcp = FastMCP("公考小智")

# 启动时把字典表加载进内存
load_dict_cache()


# ============================================================
# 工具内部 helper
# ============================================================
def _build_question_filter(
    province: Optional[str] = None,
    year: Optional[int] = None,
    exam_type: Optional[str] = None,
    question_type: Optional[str] = None,
    sub_type: Optional[str] = None,
    keyword: Optional[str] = None,
    exclude_dirty: bool = True,
) -> tuple[str, list]:
    """构造 questions 表的 WHERE 条件，返回 (where_sql, params)"""
    conds = ["is_valid = 1", "is_complete = 1"]
    params: list = []

    if exclude_dirty:
        # 排除还没清洗的题型
        placeholders = ",".join(["%s"] * len(EXCLUDED_QUESTION_TYPES))
        conds.append(f"question_type NOT IN ({placeholders})")
        params.extend(EXCLUDED_QUESTION_TYPES)

    if province:
        conds.append("province = %s")
        params.append(province)
    if year:
        conds.append("year = %s")
        params.append(int(year))
    if exam_type:
        conds.append("exam_type = %s")
        params.append(exam_type)
    if question_type:
        conds.append("question_type = %s")
        params.append(question_type)
    if sub_type:
        conds.append("sub_type = %s")
        params.append(sub_type)
    if keyword:
        conds.append("(stem LIKE %s OR analysis LIKE %s)")
        like = f"%{keyword}%"
        params.extend([like, like])

    return " AND ".join(conds), params


def _format_question_brief(q: dict) -> dict:
    """精简版题目，给搜索结果列表用（不含选项详情，省 token）"""
    stem = q.get("stem") or ""
    return {
        "id": q["id"],
        "province": q.get("province"),
        "year": q.get("year"),
        "question_type": q.get("question_type"),
        "sub_type": q.get("sub_type"),
        "stem_preview": stem[:80] + ("..." if len(stem) > 80 else ""),
        "difficulty": q.get("difficulty"),
    }


def _format_question_full(q: dict) -> dict:
    """完整版题目，给单题查询和实际练习用"""
    return {
        "id": q["id"],
        "province": q.get("province"),
        "year": q.get("year"),
        "exam_type": q.get("exam_type"),
        "question_type": q.get("question_type"),
        "sub_type": q.get("sub_type"),
        "stem": q.get("stem"),
        "options": {
            "A": q.get("option_a"),
            "B": q.get("option_b"),
            "C": q.get("option_c"),
            "D": q.get("option_d"),
        },
        "answer": q.get("answer"),
        "analysis": q.get("analysis"),
        "difficulty": q.get("difficulty"),
        "source": q.get("source"),
    }


def _safe_error(e: Exception, hint: str = "") -> dict:
    """统一错误返回，避免把 SQL 异常细节抛给 LLM"""
    if isinstance(e, AuthError):
        return {"error": "auth_failed", "message": str(e)}
    msg = f"{hint}: {type(e).__name__}" if hint else type(e).__name__
    print(f"[MCP ERROR] {msg}: {e}", file=sys.stderr)
    return {"error": "internal_error", "message": msg}


# ============================================================
# 一、字典查询（无鉴权）
# ============================================================

@mcp.tool()
def list_provinces(hot_only: bool = False) -> dict:
    """
    列出所有省份及其题量统计。

    触发：用户问"有哪些省份"、"热门省份是哪些"、"你们支持哪些地方的题"
    不要用于：查某省题目（用 search_questions / get_random_questions）

    参数：
      hot_only: True 只返回热门省份（国考、广东、江苏、山东 4 个）
    返回：省份列表，每项含 code/name/is_hot/total_papers
    """
    try:
        provinces = get_provinces_cached(hot_only=hot_only)
        return {
            "total": len(provinces),
            "provinces": [
                {
                    "code": p["code"],
                    "name": p["name"],
                    "is_hot": bool(p["is_hot"]),
                    "total_papers": p.get("total_papers", 0),
                }
                for p in provinces
            ],
        }
    except Exception as e:
        return _safe_error(e, "list_provinces")


@mcp.tool()
def list_years(province: Optional[str] = None) -> dict:
    """
    列出题库里有哪些年份的题目。

    触发：用户问"广东有哪些年的题"、"国考最早到哪年"、"你们有几年的真题"
    不要用于：查题目内容（用 search_questions）

    参数：
      province: 可选，只看某省的年份范围
    返回：年份列表 + 每年题数
    """
    try:
        sql = (
            "SELECT year, COUNT(*) AS cnt FROM questions "
            "WHERE is_valid = 1 AND year IS NOT NULL"
        )
        params: list = []
        if province:
            sql += " AND province = %s"
            params.append(province)
        sql += " GROUP BY year ORDER BY year DESC"
        rows = query_all(sql, tuple(params))
        return {
            "province": province or "全部",
            "total": len(rows),
            "years": [{"year": r["year"], "count": r["cnt"]} for r in rows],
        }
    except Exception as e:
        return _safe_error(e, "list_years")


@mcp.tool()
def list_question_types() -> dict:
    """
    列出题库里有哪些题型/子题型，含每种的题数。

    触发：用户问"行测有哪些题型"、"判断推理下面有哪些子题型"、"都有什么类型的题"
    不要用于：出题或查题（用 prepare_practice_session / search_questions）
    """
    try:
        rows = query_all(
            "SELECT exam_type, question_type, sub_type, COUNT(*) AS cnt "
            "FROM questions WHERE is_valid = 1 "
            "GROUP BY exam_type, question_type, sub_type "
            "ORDER BY exam_type, question_type, cnt DESC"
        )
        # 按 exam_type → question_type 嵌套
        out: dict = {}
        for r in rows:
            et = r["exam_type"] or "未分类"
            qt = r["question_type"] or "未分类"
            out.setdefault(et, {}).setdefault(qt, []).append({
                "sub_type": r["sub_type"],
                "count": r["cnt"],
            })
        return {"types": out, "note": f"已排除暂未清洗的题型：{EXCLUDED_QUESTION_TYPES}"}
    except Exception as e:
        return _safe_error(e, "list_question_types")


# ============================================================
# 二、题库查询（无鉴权）
# ============================================================

@mcp.tool()
def search_questions(
    province: Optional[str] = None,
    year: Optional[int] = None,
    exam_type: Optional[str] = None,
    question_type: Optional[str] = None,
    sub_type: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """
    搜索题库（行测题），返回精简列表（不含完整选项）。

    触发：用户找题（不出题），如"找几道2023广东的言语理解"、"搜索关于行政法的题"
    不要用于：
      - 用户要做题 → 用 prepare_practice_session
      - 用户要看完整题目 → 用 get_question_by_id
      - 用户要打印 → 用 generate_quiz_pdf

    参数：
      province / year / exam_type / question_type / sub_type: 可选筛选
      keyword: 在题干和解析里全文模糊匹配
      limit: 默认10，最大50
      offset: 分页起点，默认0

    返回：{total, results: [...精简题目（不含选项）]}
    """
    try:
        limit = min(int(limit), 50)
        offset = max(int(offset), 0)
        where, params = _build_question_filter(
            province=province, year=year, exam_type=exam_type,
            question_type=question_type, sub_type=sub_type, keyword=keyword,
        )

        # 总数
        total_row = query_one(
            f"SELECT COUNT(*) AS cnt FROM questions WHERE {where}",
            tuple(params),
        )
        total = total_row["cnt"] if total_row else 0

        # 详情
        rows = query_all(
            f"SELECT id, province, year, question_type, sub_type, stem, difficulty "
            f"FROM questions WHERE {where} "
            f"ORDER BY id DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [_format_question_brief(r) for r in rows],
        }
    except Exception as e:
        return _safe_error(e, "search_questions")


@mcp.tool()
def get_random_questions(
    count: int = 10,
    province: Optional[str] = None,
    exam_type: Optional[str] = None,
    question_type: Optional[str] = None,
    sub_type: Optional[str] = None,
    user_id: Optional[int] = None,
    exclude_answered: bool = False,
) -> dict:
    """
    随机抽题，返回完整题目（含选项+答案+解析）。

    触发：用户说"给我看几道题示例"、"展示一道数量关系"、"AI演示几道题"
    不要用于：
      - 用户要在线做题 → 用 prepare_practice_session（会创建session）
      - 用户要打印PDF → 用 generate_quiz_pdf

    参数：
      count: 抽多少道，默认10，最大100
      province / exam_type / question_type / sub_type: 筛选条件
      user_id: 可选，传了才能排除已答过的题
      exclude_answered: 是否排除已答过的题（需传user_id）

    返回：{count: 实际数, questions: [...完整题目含答案解析]}
    """
    try:
        count = min(int(count), MAX_QUESTIONS_PER_CALL)
        where, params = _build_question_filter(
            province=province, exam_type=exam_type,
            question_type=question_type, sub_type=sub_type,
        )

        # 排除已答过的题（如果有 user_id）
        if exclude_answered and user_id:
            where += (
                " AND id NOT IN ("
                "  SELECT DISTINCT question_id FROM answer_records WHERE user_id = %s"
                ")"
            )
            params.append(user_id)

        # MySQL 8 ORDER BY RAND() 在几万行级别还能接受
        # 真要扛大流量再换"先 COUNT 再随机 OFFSET"的方案
        rows = query_all(
            f"SELECT * FROM questions WHERE {where} "
            f"ORDER BY RAND() LIMIT %s",
            tuple(params) + (count,),
        )
        return {
            "count": len(rows),
            "requested": count,
            "questions": [_format_question_full(r) for r in rows],
        }
    except Exception as e:
        return _safe_error(e, "get_random_questions")


@mcp.tool()
def get_question_by_id(question_id: int) -> dict:
    """
    按 ID 获取单题完整内容（题干、选项、答案、解析）。

    触发：用户说"第8291题怎么做"、"看看这道题的解析"、AI引用某道具体题
    不要用于：随机抽题（用 get_random_questions）、批量查题（用 search_questions）
    """
    try:
        q = query_one("SELECT * FROM questions WHERE id = %s", (int(question_id),))
        if not q:
            return {"error": "not_found", "message": f"题目 {question_id} 不存在"}
        return _format_question_full(q)
    except Exception as e:
        return _safe_error(e, "get_question_by_id")


@mcp.tool()
def get_shenglun_questions(
    province: Optional[str] = None,
    year: Optional[int] = None,
    question_type: Optional[str] = None,
    exam_level: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """
    搜索申论题列表（只返回摘要，不含材料原文）。

    触发：用户问"有哪些广东申论"、"2024年国考申论有什么题"、"找申论概括归纳题"
    不要用于：
      - 获取申论完整材料 → 用 get_shenglun_by_id
      - 下载申论PDF → 用 trigger_pack_province（下载原版真题PDF，质量更好）
      - 生成申论练习卷 → 申论不支持在线判分，推荐下载原版PDF

    参数：
      province / year / question_type / exam_level: 筛选
      question_type 取值: 概括归纳/综合分析/对策建议/贯彻执行/申论文章
      exam_level 取值: 副省级/地市级/行政执法/A卷/B卷
      limit: 默认5，最大20

    注意：申论是主观题，系统无法自动判分，用户练申论最好下载原版PDF对照作答
    """
    try:
        limit = min(int(limit), 20)
        conds = ["is_valid = 1"]
        params: list = []
        if province:
            conds.append("province = %s"); params.append(province)
        if year:
            conds.append("year = %s"); params.append(int(year))
        if question_type:
            conds.append("question_type = %s"); params.append(question_type)
        if exam_level:
            conds.append("exam_level = %s"); params.append(exam_level)

        where = " AND ".join(conds)
        rows = query_all(
            f"SELECT id, province, year, exam_level, question_type, "
            f"       question_no, stem, word_limit, score "
            f"FROM shenglun_questions WHERE {where} "
            f"ORDER BY year DESC, id DESC LIMIT %s",
            tuple(params) + (limit,),
        )
        return {
            "count": len(rows),
            "results": [
                {
                    "id": r["id"],
                    "province": r["province"],
                    "year": r["year"],
                    "exam_level": r["exam_level"],
                    "question_type": r["question_type"],
                    "question_no": r["question_no"],
                    "stem_preview": (r["stem"] or "")[:120],
                    "word_limit": r["word_limit"],
                    "score": r["score"],
                }
                for r in rows
            ],
        }
    except Exception as e:
        return _safe_error(e, "get_shenglun_questions")


@mcp.tool()
def get_shenglun_by_id(question_id: int) -> dict:
    """
    按 ID 获取申论题完整内容（含给定材料全文和参考答案）。

    触发：用户选定了某道申论题，要查看完整材料和参考答案
    不要用于：
      - 搜索申论列表 → 用 get_shenglun_questions
      - 下载整套申论真题 → 用 trigger_pack_province
    """
    try:
        q = query_one(
            "SELECT * FROM shenglun_questions WHERE id = %s",
            (int(question_id),),
        )
        if not q:
            return {"error": "not_found", "message": f"申论题 {question_id} 不存在"}
        # key_points 是 JSON 字段，pymysql 已自动反序列化
        return {
            "id": q["id"],
            "province": q["province"],
            "year": q["year"],
            "exam_level": q["exam_level"],
            "question_type": q["question_type"],
            "question_no": q["question_no"],
            "stem": q["stem"],
            "material": q["material"],
            "word_limit": q["word_limit"],
            "score": q["score"],
            "key_points": q["key_points"],
            "reference_answer": q["reference_answer"],
        }
    except Exception as e:
        return _safe_error(e, "get_shenglun_by_id")


# ============================================================
# 三、试卷查询（无鉴权）
# ============================================================

@mcp.tool()
def search_papers(
    province: Optional[str] = None,
    year: Optional[int] = None,
    exam_type: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """
    搜索试卷文件（PDF），返回试卷列表和下载链接。

    触发：用户找具体某套试卷，如"2023广东行测真题在哪"、"找一下国考申论PDF"
    不要用于：
      - 打包下载多份 → 用 trigger_pack_province（支持批量打包）
      - 在线刷题 → 用 prepare_practice_session
      - 题库查题 → 用 search_questions

    注意：试卷是完整PDF原版文件，和题库（按题存储）是两个独立体系
    """
    try:
        limit = min(int(limit), 50)
        conds = ["status = 'published'"]
        params: list = []
        if province:
            conds.append("province = %s"); params.append(province)
        if year:
            conds.append("year = %s"); params.append(int(year))
        if exam_type:
            conds.append("exam_type = %s"); params.append(exam_type)

        where = " AND ".join(conds)
        rows = query_all(
            f"SELECT id, name, province, year, exam_type, exam_level, "
            f"       doc_type, sub_exam, zip_path, "
            f"       file_size, download_count, total_questions "
            f"FROM papers WHERE {where} "
            f"ORDER BY year DESC, download_count DESC LIMIT %s",
            tuple(params) + (limit,),
        )
        return {
            "count": len(rows),
            "papers": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "province": r["province"],
                    "year": r["year"],
                    "exam_type": r["exam_type"],
                    "doc_type": r.get("doc_type"),       # 题目 / 答案
                    "sub_exam": r.get("sub_exam"),       # A 卷 / B 卷
                    "exam_level": r["exam_level"],
                    "size_mb": round((r["file_size"] or 0) / 1024 / 1024, 1),
                    "download_count": r["download_count"],
                    # 单文件下载（与 paper_routes.py 对齐）
                    "download_url": f"{API_BASE}/api/paper/file/{r['id']}",
                    # 该省份整包 ZIP（如果有）
                    "zip_url": (
                        f"{API_BASE}/api/paper/zip/{r['province']}"
                        if r.get("zip_path") else None
                    ),
                }
                for r in rows
            ],
        }
    except Exception as e:
        return _safe_error(e, "search_papers")


@mcp.tool()
def get_paper_by_id(paper_id: int) -> dict:
    """
    按 ID 获取单份试卷详细元数据和下载链接。

    触发：已知试卷ID，要获取下载地址
    通常由 search_papers 的结果触发，不单独使用
    不要用于：搜索试卷（用 search_papers）、批量下载（用 trigger_pack_province）
    """
    try:
        p = query_one("SELECT * FROM papers WHERE id = %s", (int(paper_id),))
        if not p:
            return {"error": "not_found", "message": f"试卷 {paper_id} 不存在"}
        return {
            "id": p["id"],
            "name": p["name"],
            "province": p["province"],
            "year": p["year"],
            "exam_type": p["exam_type"],
            "exam_level": p["exam_level"],
            "size_mb": round((p["file_size"] or 0) / 1024 / 1024, 1),
            "download_count": p["download_count"],
            "total_questions": p["total_questions"],
            "download_url": f"{API_BASE}/api/papers/{p['id']}/download",
            "status": p["status"],
        }
    except Exception as e:
        return _safe_error(e, "get_paper_by_id")


# ============================================================
# 四、用户学情（需鉴权）
# ============================================================

@mcp.tool()
def get_user_study_overview(user_id: int) -> dict:
    """
    一次获取用户完整学情诊断包（总答题数、正确率、薄弱点、近期错题、近期练习）。

    触发：用户说"分析我的学习情况"、"我练得怎么样"、"给我看看我的数据"、"我哪里弱"
    这是最常用的学情工具，一次调用包含所有学情信息，调完无需再调其他学情工具。
    不要用于：
      - 只看薄弱点 → 用 get_user_weakness（更聚焦，token更省）
      - 只看错题 → 用 get_recent_wrongs

    参数：
      user_id: 必填，FastAPI BFF 会校验它和 token 一致

    返回：
      summary       总答题数、正确率、近30天数据、来源分布
      weakness      最弱模块、最弱省份、各题型错误率
      recent_wrongs 最近5条错题预览
      recent_sessions 最近3次练习
    """
    try:
        user = require_user(user_id)

        # 1. 基础统计
        summary = {
            "username": user["nickname"] or user["username"],
            "total_answered": user["total_answered"] or 0,
            "total_correct": user["total_correct"] or 0,
            "correct_rate": (
                round(user["total_correct"] / user["total_answered"], 3)
                if user["total_answered"] else 0.0
            ),
            "plan": user["plan"],
        }

        # 2. 近 30 天答题情况
        recent = query_one(
            "SELECT COUNT(*) AS total, SUM(is_correct) AS correct "
            "FROM answer_records WHERE user_id = %s "
            "AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
            (user_id, RECENT_WINDOW_DAYS),
        )
        summary["recent_30d_answered"] = recent["total"] or 0
        summary["recent_30d_correct"] = int(recent["correct"] or 0)

        # 3. 薄弱点
        weakness_row = query_one(
            "SELECT * FROM user_weaknesses WHERE user_id = %s",
            (user_id,),
        )
        weakness: dict = {}
        if weakness_row:
            rates = {
                "言语理解": float(weakness_row.get("rate_yanyu") or 0),
                "判断推理": float(weakness_row.get("rate_panduan") or 0),
                "数量关系": float(weakness_row.get("rate_shuliang") or 0),
                "常识判断": float(weakness_row.get("rate_changshi") or 0),
                "图形推理": float(weakness_row.get("rate_tuli") or 0),
                "资料分析": float(weakness_row.get("rate_ziliao") or 0),

            }
            # 按错误率降序排
            sorted_modules = sorted(
                [(k, v) for k, v in rates.items() if v > 0],
                key=lambda x: -x[1],
            )
            weakness["module_error_rates"] = dict(sorted_modules)
            if sorted_modules:
                weakness["weakest_module"] = sorted_modules[0][0]
                weakness["weakest_rate"] = sorted_modules[0][1]
            weakness["province_error_rates"] = weakness_row.get("weakness_provinces") or {}

        # 4. 近期错题（精简，只要预览）
        recent_wrongs = query_all(
            "SELECT w.question_id, w.wrong_count, w.last_wrong_at, "
            "       q.question_type, q.stem, q.province, q.year "
            "FROM wrong_questions w "
            "JOIN questions q ON q.id = w.question_id "
            "WHERE w.user_id = %s AND w.is_mastered = 0 "
            "ORDER BY w.last_wrong_at DESC LIMIT 5",
            (user_id,),
        )

        # 5. 近期练习
        recent_sessions = query_all(
            "SELECT id, session_type, question_type, total_count, "
            "       answered_count, correct_count, status, started_at "
            "FROM quiz_sessions "
            "WHERE user_id = %s AND status IN ('completed', 'active') "
            "ORDER BY started_at DESC LIMIT 3",
            (user_id,),
        )

        # 6. 按来源分类统计（AI出题 vs 随机练习）
        source_rows = query_all(
            "SELECT qs.session_type, COUNT(ar.id) AS total, SUM(ar.is_correct) AS correct "
            "FROM answer_records ar "
            "JOIN quiz_sessions qs ON ar.session_id = qs.id "
            "WHERE ar.user_id = %s "
            "GROUP BY qs.session_type",
            (user_id,),
        )
        source_label = {"ai_prepared": "AI智能出题", "manual_form": "随机练习"}
        source_stats = {}
        for r in source_rows:
            stype = r["session_type"]
            total = int(r["total"] or 0)
            correct = int(r["correct"] or 0)
            source_stats[source_label.get(stype, stype)] = {
                "total": total,
                "correct": correct,
                "correct_rate": round(correct / total, 3) if total else 0.0,
                "note": "专攻弱项，正确率偏低属正常" if stype == "ai_prepared" else "综合练习",
            }
        summary["source_breakdown"] = source_stats

        return {
            "summary": summary,
            "weakness": weakness,
            "recent_wrongs": [
                {
                    "id": w["question_id"],
                    "type": w["question_type"],
                    "stem_preview": (w["stem"] or "")[:60],
                    "province": w["province"],
                    "year": w["year"],
                    "wrong_count": w["wrong_count"],
                    "last_wrong_at": str(w["last_wrong_at"]) if w["last_wrong_at"] else None,
                }
                for w in recent_wrongs
            ],
            "recent_sessions": [
                {
                    "id": s["id"],
                    "type": s["session_type"],
                    "question_type": s["question_type"],
                    "score": (
                        f"{s['correct_count']}/{s['answered_count']}"
                        if s["answered_count"] else None
                    ),
                    "status": s["status"],
                    "date": str(s["started_at"])[:10] if s["started_at"] else None,
                }
                for s in recent_sessions
            ],
        }
    except Exception as e:
        return _safe_error(e, "get_user_study_overview")


@mcp.tool()
def get_recent_wrongs(
    user_id: int,
    limit: int = 10,
    question_type: Optional[str] = None,
    only_unmastered: bool = True,
) -> dict:
    """
    获取用户最近的错题列表（含完整题目内容）。

    触发：用户说"看看我最近错了哪些题"、"我的错题本"、"复习错题"
    不要用于：
      - 全面学情分析 → 用 get_user_study_overview（包含错题预览）
      - 基于错题出题 → 用 prepare_practice_session（based_on_wrongs=True）

    参数：
      user_id: 必填
      limit: 默认10，最大50
      question_type: 可按题型过滤，如"判断推理"
      only_unmastered: True只看未掌握的（默认），False看全部
    """
    try:
        require_user(user_id)
        limit = min(int(limit), 50)
        conds = ["w.user_id = %s"]
        params: list = [user_id]

        if only_unmastered:
            conds.append("w.is_mastered = 0")
        if question_type:
            conds.append("q.question_type = %s")
            params.append(question_type)

        where = " AND ".join(conds)
        rows = query_all(
            f"SELECT w.id AS w_id, w.question_id, w.wrong_count, w.is_mastered, "
            f"       w.is_starred, w.last_wrong_at, w.note, "
            f"       q.stem, q.option_a, q.option_b, q.option_c, q.option_d, "
            f"       q.answer, q.analysis, q.question_type, q.province, q.year "
            f"FROM wrong_questions w "
            f"JOIN questions q ON q.id = w.question_id "
            f"WHERE {where} "
            f"ORDER BY w.last_wrong_at DESC LIMIT %s",
            tuple(params) + (limit,),
        )
        return {
            "count": len(rows),
            "wrongs": [
                {
                    "id": r["question_id"],
                    "wrong_count": r["wrong_count"],
                    "is_mastered": bool(r["is_mastered"]),
                    "is_starred": bool(r["is_starred"]),
                    "last_wrong_at": str(r["last_wrong_at"]) if r["last_wrong_at"] else None,
                    "note": r["note"],
                    "question": _format_question_full(r),
                }
                for r in rows
            ],
        }
    except Exception as e:
        return _safe_error(e, "get_recent_wrongs")


@mcp.tool()
def get_recent_sessions(user_id: int, limit: int = 5) -> dict:
    """
    获取用户最近的练习记录（session列表）。

    触发：用户问"我最近做了什么练习"、"上次练了多少题"、"我的练习历史"
    不要用于：全面学情分析（用 get_user_study_overview，它包含近期练习）

    参数：
      user_id: 必填
      limit: 返回条数，默认5，最大20
    """
    try:
        require_user(user_id)
        limit = min(int(limit), 20)
        rows = query_all(
            "SELECT id, session_type, province, question_type, "
            "       total_count, answered_count, correct_count, "
            "       duration_seconds, status, started_at, completed_at "
            "FROM quiz_sessions WHERE user_id = %s "
            "ORDER BY started_at DESC LIMIT %s",
            (user_id, limit),
        )
        return {
            "count": len(rows),
            "sessions": [
                {
                    "id": r["id"],
                    "type": r["session_type"],
                    "province": r["province"],
                    "question_type": r["question_type"],
                    "total": r["total_count"],
                    "answered": r["answered_count"],
                    "correct": r["correct_count"],
                    "duration_seconds": r["duration_seconds"],
                    "status": r["status"],
                    "started_at": str(r["started_at"]) if r["started_at"] else None,
                    "completed_at": str(r["completed_at"]) if r["completed_at"] else None,
                }
                for r in rows
            ],
        }
    except Exception as e:
        return _safe_error(e, "get_recent_sessions")


@mcp.tool()
def get_user_weakness(user_id: int) -> dict:
    """
    获取用户薄弱点分析（各题型错误率排序 + 省份维度弱点）。

    触发：用户问"我哪个模块最弱"、"我的薄弱点是什么"、"我数量关系怎么样"
    不要用于：
      - 需要完整学情的场景 → 用 get_user_study_overview（包含薄弱点在内的全部数据）
      - 基于薄弱点出题 → 用 prepare_practice_session（不传 question_type，会自动按弱点配比）

    返回：各题型错误率排序 + 最弱模块 + 省份维度弱点
    """
    try:
        require_user(user_id)
        row = query_one(
            "SELECT * FROM user_weaknesses WHERE user_id = %s",
            (user_id,),
        )
        if not row:
            return {
                "user_id": user_id,
                "has_data": False,
                "message": "暂无薄弱点数据，多答几道题就有了",
            }

        rates = {
            "言语理解": float(row.get("rate_yanyu") or 0),
            "判断推理": float(row.get("rate_panduan") or 0),
            "数量关系": float(row.get("rate_shuliang") or 0),
            "常识判断": float(row.get("rate_changshi") or 0),
            "图形推理": float(row.get("rate_tuli") or 0),
            "资料分析": float(row.get("rate_ziliao") or 0),

        }
        sorted_modules = sorted(rates.items(), key=lambda x: -x[1])
        return {
            "user_id": user_id,
            "has_data": True,
            "module_error_rates": dict(sorted_modules),
            "weakest_modules": [m for m, r in sorted_modules[:3] if r > 0],
            "province_error_rates": row.get("weakness_provinces") or {},
            "updated_at": str(row.get("updated_at")) if row.get("updated_at") else None,
        }
    except Exception as e:
        return _safe_error(e, "get_user_weakness")


# ============================================================
# 五、写操作（需用户确认，会创建 ui_card）
# ============================================================

@mcp.tool()
def prepare_practice_session(
    user_id: int,
    count: int = 10,
    province: Optional[str] = None,
    question_type: Optional[str] = None,
    sub_type: Optional[str] = None,
    based_on_wrongs: bool = False,
) -> dict:
    """
    为用户准备一套在线练习题（创建pending session，用户点开始后在网页做题、自动判分）。

    触发：用户说"出5道题练练"、"做几道判断推理"、"摸底测试"、"刷题"、"再来10道"
    不要用于：
      - 用户要打印试卷 → 用 generate_quiz_pdf
      - 用户只想看题目示例不做题 → 用 get_random_questions

    ⚠️ 重要规则：
      - count 严格按用户当前消息说的数字，绝对不要拷贝历史消息的数字
      - 用户说"再来10道"要重新调用传 count=10，不能复用上一次的session
      - based_on_wrongs=True 适合用户说"用我的错题练"、"专攻弱点"
      - 不传 question_type 时，系统会自动按用户薄弱点加权配比出题

    返回：session_id + ui_card（type='practice_ready'，前端渲染开始/取消按钮）
    """
    try:
        require_user(user_id)
        count = min(int(count), MAX_QUESTIONS_PER_CALL)

        # 1. 把该用户旧 pending 标 cancelled（一用户一活跃 pending）
        execute(
            "UPDATE quiz_sessions SET status = 'cancelled' "
            "WHERE user_id = %s AND status = 'pending'",
            (user_id,),
        )

        # 2. 选题
        question_ids: list[int] = []
        source_desc = ""

        if based_on_wrongs:
            wrong_rows = query_all(
                "SELECT w.question_id FROM wrong_questions w "
                "JOIN questions q ON q.id = w.question_id "
                "WHERE w.user_id = %s AND w.is_mastered = 0 "
                + ("AND q.question_type = %s " if question_type else "")
                + "ORDER BY w.last_wrong_at DESC LIMIT %s",
                ((user_id, question_type, count) if question_type else (user_id, count)),
            )
            question_ids = [r["question_id"] for r in wrong_rows]
            source_desc = f"基于你最近的错题"

            # 不够就从全库补
            if len(question_ids) < count:
                need = count - len(question_ids)
                where, params = _build_question_filter(
                    province=province, question_type=question_type, sub_type=sub_type,
                )
                if question_ids:
                    where += f" AND id NOT IN ({','.join(['%s']*len(question_ids))})"
                    params.extend(question_ids)
                extra = query_all(
                    f"SELECT id FROM questions WHERE {where} "
                    f"ORDER BY RAND() LIMIT %s",
                    tuple(params) + (need,),
                )
                question_ids.extend([r["id"] for r in extra])
                if extra:
                    source_desc += f"，并从题库补充 {len(extra)} 道"
        else:
            # 如果没有指定题型，读取薄弱点按错误率加权配比出题
            if not question_type:
                weakness_row = query_one(
                    "SELECT rate_yanyu, rate_panduan, rate_shuliang, rate_changshi, "
                    "       rate_tuli, rate_ziliao "
                    "FROM user_weaknesses WHERE user_id = %s",
                    (user_id,),
                )
                if weakness_row:
                    # 题型 → 错误率映射
                    type_rates = {
                        "言语理解": float(weakness_row.get("rate_yanyu") or 0),
                        "判断推理": float(weakness_row.get("rate_panduan") or 0),
                        "数量关系": float(weakness_row.get("rate_shuliang") or 0),
                        "常识判断": float(weakness_row.get("rate_changshi") or 0),

                    }
                    # 过滤掉排除的题型
                    type_rates = {k: v for k, v in type_rates.items()
                                  if k not in EXCLUDED_QUESTION_TYPES}

                    total_rate = sum(type_rates.values())
                    question_ids = []
                    source_parts = []

                    if total_rate > 0:
                        # 按错误率加权分配题数（弱的多出，强的少出）
                        # 最低保底每个题型至少1题（如果count够）
                        alloc = {}
                        for qt, rate in type_rates.items():
                            alloc[qt] = max(1, round(count * rate / total_rate))

                        # 调整总数到 count
                        diff = sum(alloc.values()) - count
                        if diff > 0:
                            # 超了，从错误率最低的题型减
                            for qt in sorted(alloc, key=lambda x: type_rates[x]):
                                if diff <= 0: break
                                if alloc[qt] > 1:
                                    alloc[qt] -= 1
                                    diff -= 1
                        elif diff < 0:
                            # 少了，给错误率最高的题型加
                            diff = abs(diff)
                            for qt in sorted(alloc, key=lambda x: -type_rates[x]):
                                if diff <= 0: break
                                alloc[qt] += 1
                                diff -= 1

                        # 按分配数量抽题
                        for qt, n in alloc.items():
                            if n <= 0: continue
                            where, params = _build_question_filter(
                                province=province, question_type=qt, sub_type=sub_type,
                            )
                            rows = query_all(
                                f"SELECT id FROM questions WHERE {where} "
                                f"ORDER BY RAND() LIMIT %s",
                                tuple(params) + (n,),
                            )
                            question_ids.extend([r["id"] for r in rows])
                            if rows:
                                source_parts.append(f"{qt}×{len(rows)}")

                        # 配比后补齐：round()导致总数可能差1-2道，从全库补足
                        if len(question_ids) < count:
                            need = count - len(question_ids)
                            where_fill, params_fill = _build_question_filter(province=province)
                            if question_ids:
                                where_fill += f" AND id NOT IN ({','.join(['%s']*len(question_ids))})"
                                params_fill.extend(question_ids)
                            extra_rows = query_all(
                                f"SELECT id FROM questions WHERE {where_fill} "
                                f"ORDER BY RAND() LIMIT %s",
                                tuple(params_fill) + (need,),
                            )
                            question_ids.extend([r["id"] for r in extra_rows])

                        random.shuffle(question_ids)  # 打乱题型顺序
                        weakest = max(type_rates, key=type_rates.get)
                        source_desc = f"根据薄弱点智能配比（{weakest}较弱），共 {len(question_ids)} 道"
                        if source_parts:
                            source_desc += f"：{'、'.join(source_parts)}"

            # 没有薄弱点数据或指定了题型，走原来随机逻辑
            if not question_ids:
                where, params = _build_question_filter(
                    province=province, question_type=question_type, sub_type=sub_type,
                )
                rows = query_all(
                    f"SELECT id FROM questions WHERE {where} "
                    f"ORDER BY RAND() LIMIT %s",
                    tuple(params) + (count,),
                )
                question_ids = [r["id"] for r in rows]
                parts = []
                if province: parts.append(province)
                if question_type: parts.append(question_type)
                if sub_type: parts.append(sub_type)
                source_desc = "、".join(parts) if parts else "全题库随机"

        if not question_ids:
            return {
                "error": "no_questions",
                "message": f"找不到符合条件的题（{source_desc}），换个筛选试试",
            }

        # 兜底补齐：配比计算可能少1-2道，从全库随机补足
        if len(question_ids) < count:
            need = count - len(question_ids)
            where_fill, params_fill = _build_question_filter(
                province=province, question_type=question_type, sub_type=sub_type,
            )
            if question_ids:
                where_fill += f" AND id NOT IN ({','.join(['%s'] * len(question_ids))})"
                params_fill.extend(question_ids)
            extra_rows = query_all(
                f"SELECT id FROM questions WHERE {where_fill} "
                f"ORDER BY RAND() LIMIT %s",
                tuple(params_fill) + (need,),
            )
            question_ids.extend([r["id"] for r in extra_rows])
            if extra_rows:
                source_desc += f"（补充{len(extra_rows)}道凑足{count}题）"

        # 3. 写入 pending session
        session_id = str(uuid.uuid4())
        execute(
            "INSERT INTO quiz_sessions "
            "(id, user_id, session_type, province, question_type, "
            " preset_question_ids, total_count, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')",
            (
                session_id, user_id, "ai_prepared",
                province, question_type,
                json.dumps(question_ids), len(question_ids),
            ),
        )

        # 4. 估算时间（一道行测 1 分钟左右）
        estimated_minutes = max(1, len(question_ids))

        return {
            "session_id": session_id,
            "summary": f"已准备 {len(question_ids)} 道{question_type or '题'}",
            "ui_card": {
                "type": "practice_ready",
                "session_id": session_id,
                "data": {
                    "count": len(question_ids),
                    "question_type": question_type or "混合",
                    "source": source_desc,
                    "estimated_minutes": estimated_minutes,
                    "based_on_wrongs": based_on_wrongs,
                },
                "actions": [
                    {"key": "start",  "label": "开始练习", "primary": True,
                     "route": f"/practice?session={session_id}"},
                    {"key": "cancel", "label": "取消"},
                ],
            },
        }
    except Exception as e:
        return _safe_error(e, "prepare_practice_session")


@mcp.tool()
def trigger_pack_province(
    province: str,
    exam_type: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    exam_types: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> dict:
    """
    打包某省份真题为ZIP并返回下载卡片（即时或实时打包）。

    触发：用户说"下载广东真题"、"打包北京行测"、"要2023年国考"、"给我广东全套"
    不要用于：
      - 在线做题 → 用 prepare_practice_session
      - 生成新练习卷PDF → 用 generate_quiz_pdf
      - 专题学习资料（技巧类）→ 用 list_extras + download_extra

    ⚠️ 用法对照表：
      "广东全部"              → province="广东"（不加任何筛选，返回预压缩整包）
      "广东2023行测"          → province="广东", year=2023, exam_type="行测"
      "广东2021+2022行测"     → province="广东", years="2021,2022", exam_type="行测"
      "国考行测+申论"          → province="国考", exam_types="行测,申论"

    参数（year/exam_type单值，years/exam_types逗号分隔字符串）：
      province:   必填
      year:       单年份（整数）
      years:      多年份，如"2021,2022,2023"（优先级高于year）
      exam_type:  单科目，"行测"/"申论"
      exam_types: 多科目，"行测,申论"（优先级高于exam_type）
      doc_type:   "题目"/"答案"，留空=全部

    返回：ui_card（type='pack_ready'，status='ready'可直接下载）
    """
    try:
        # ----- 1. 归一化筛选参数 -----
        year_list: list = []
        if years:
            for y in str(years).split(","):
                y = y.strip()
                if y.isdigit():
                    year_list.append(int(y))
        elif year is not None:
            year_list = [int(year)]

        exam_type_list: list = []
        if exam_types:
            exam_type_list = [x.strip() for x in str(exam_types).split(",") if x.strip()]
        elif exam_type:
            exam_type_list = [exam_type]

        doc_type_list: list = []
        if doc_type:
            doc_type_list = [doc_type]

        has_filter = bool(year_list or exam_type_list or doc_type_list)

        # ----- 2. 查 DB 看到底有几份命中 -----
        conds = ["province = %s", "status = 'published'"]
        params: list = [province]
        if year_list:
            ph = ",".join(["%s"] * len(year_list))
            conds.append(f"year IN ({ph})"); params.extend(year_list)
        if exam_type_list:
            ph = ",".join(["%s"] * len(exam_type_list))
            conds.append(f"exam_type IN ({ph})"); params.extend(exam_type_list)
        if doc_type_list:
            ph = ",".join(["%s"] * len(doc_type_list))
            conds.append(f"doc_type IN ({ph})"); params.extend(doc_type_list)

        count_row = query_one(
            f"SELECT COUNT(*) AS cnt, SUM(file_size) AS total "
            f"FROM papers WHERE {' AND '.join(conds)}",
            tuple(params),
        )
        total = count_row["cnt"] if count_row else 0
        size_bytes = (count_row.get("total") if count_row else 0) or 0

        if total == 0:
            return {
                "error": "no_papers",
                "message": f"{province} 暂无符合条件的试卷",
            }

        size_mb = round(size_bytes / 1024 / 1024, 1)
        task_id = f"pack-{province}-{uuid.uuid4().hex[:8]}"

        # ----- 3. 构造下载 URL + 友好名 -----
        if has_filter:
            # 实时子集打包
            qs_parts = [f"province={province}"]
            if year_list:
                qs_parts.append("years=" + ",".join(str(y) for y in year_list))
            if exam_type_list:
                qs_parts.append("exam_type=" + ",".join(exam_type_list))
            if doc_type_list:
                qs_parts.append("doc_type=" + ",".join(doc_type_list))
            download_url = f"{API_BASE}/api/paper/zip-subset?" + "&".join(qs_parts)

            # 友好文件名（用于卡片标题，不含 .zip 后缀）
            name_parts = [province]
            if year_list:
                name_parts.append("+".join(str(y) for y in sorted(set(year_list))))
            if exam_type_list:
                name_parts.append("+".join(exam_type_list))
            if doc_type_list:
                name_parts.append("+".join(doc_type_list))
            file_label = "_".join(name_parts)
        else:
            # 整省 ZIP（预压缩）
            candidates = [
                ZIPS_DIR / f"{province}公考真题.zip",
                Path(__file__).resolve().parent.parent / "zips" / f"{province}公考真题.zip",
            ]
            zip_full = next((p for p in candidates if p.exists()), None)
            if zip_full:
                download_url = f"{API_BASE}/api/paper/zip/{province}"
                size_mb = round(zip_full.stat().st_size / 1024 / 1024, 1)
                file_label = f"{province}公考真题"
            else:
                # 整包不存在就退回到子集模式（取所有该省的）
                download_url = f"{API_BASE}/api/paper/zip-subset?province={province}"
                file_label = f"{province}_全部真题"

        # ----- 4. 写审计 -----
        try:
            execute(
                "INSERT INTO activity_logs "
                "(action_type, target_type, target_id, content, metadata) "
                "VALUES ('pack_download', 'province', %s, %s, %s)",
                (
                    province,
                    f"获取 {file_label} 下载链接（{total} 份）",
                    json.dumps({
                        "task_id": task_id, "province": province,
                        "years": year_list, "exam_types": exam_type_list,
                        "doc_types": doc_type_list,
                        "count": total, "size_mb": size_mb,
                    }, ensure_ascii=False),
                ),
            )
        except Exception:
            pass

        # ----- 5. 友好摘要 -----
        filter_desc_parts: list = []
        if year_list:
            filter_desc_parts.append("、".join(str(y) for y in year_list) + "年")
        if exam_type_list:
            filter_desc_parts.append("+".join(exam_type_list))
        if doc_type_list:
            filter_desc_parts.append("+".join(doc_type_list))
        filter_desc = " ".join(filter_desc_parts) if filter_desc_parts else "全部"

        return {
            "task_id": task_id,
            "summary": f"{province} {filter_desc}：共 {total} 份真题，约 {size_mb} MB，可直接下载",
            "ui_card": {
                "type": "pack_ready",
                "task_id": task_id,
                "data": {
                    "province":     province,
                    "file_label":   file_label,         # ★ 友好文件名（不含 .zip）
                    "filter_desc":  filter_desc,        # ★ 文字描述（"2021、2022年 行测"）
                    "exam_type":    "+".join(exam_type_list) if exam_type_list else "全部科目",
                    "years":        year_list,
                    "paper_count":  total,
                    "size_mb":      size_mb,
                    "status":       "ready",
                    "download_url": download_url,
                },
            },
        }
    except Exception as e:
        return _safe_error(e, "trigger_pack_province")


@mcp.tool()
def list_extras() -> dict:
    """
    列出所有专题学习资料（非省份真题的ZIP，如考试技巧、申论写作指导）。

    触发：用户说"有什么学习资料"、"考试技巧在哪"、"申论技巧资料"、"有没有备考材料"
    不要用于：下载省份真题（用 trigger_pack_province）

    通常配合 download_extra 使用：
      先调 list_extras 看有什么 → 展示给用户选 → 用户确认后调 download_extra 下载
    如果用户已明确说要某个资料名字，可直接调 download_extra 跳过这步

    返回：extras列表，每项含 name / size_mb / download_url
    """
    try:
        # 扫 zips/ 目录里所有不属于"{省}公考真题.zip"格式的文件 = 专题
        if not ZIPS_DIR.exists():
            return {"extras": [], "count": 0}

        # 已知省份名（前缀过滤）
        province_rows = query_all(
            "SELECT DISTINCT province FROM papers WHERE status='published'"
        )
        known_provinces = {r["province"] for r in province_rows}

        out = []
        for zf in sorted(ZIPS_DIR.glob("*.zip")):
            # 看是不是某个省的整包
            is_province_pack = False
            for prov in known_provinces:
                if zf.name == f"{prov}公考真题.zip":
                    is_province_pack = True
                    break
            if is_province_pack:
                continue

            label = zf.stem  # 申论行测技巧
            out.append({
                "name":         label,
                "filename":     zf.name,
                "size_mb":      round(zf.stat().st_size / 1024 / 1024, 1),
                "download_url": f"{API_BASE}/api/paper/zip-extra/{label}",
            })

        return {"extras": out, "count": len(out)}
    except Exception as e:
        return _safe_error(e, "list_extras")


@mcp.tool()
def download_extra(name: str) -> dict:
    """
    给用户生成专题学习资料的下载卡片（即时返回，不需要等待）。

    触发：用户明确要下载某个专题资料，如"下载申论行测技巧"、"给我考试技巧"
    不要用于：省份真题下载（用 trigger_pack_province）

    参数：
      name: 专题名，从 list_extras 返回值里取，如"申论行测技巧"

    注意：如果用户没有指定具体名字，先调 list_extras 展示可选项让用户选择

    返回：包含 ui_card 的下载卡片（pack_ready类型，前端可直接渲染）
    """
    try:
        # 校验文件存在
        full = ZIPS_DIR / f"{name}.zip"
        if not full.exists():
            # 模糊匹配一下：可能用户说的不是完整名字
            candidates = list(ZIPS_DIR.glob("*.zip"))
            matched = [c for c in candidates if name in c.stem or c.stem in name]
            if not matched:
                return {
                    "error": "extra_not_found",
                    "message": f"没找到名为 {name} 的专题资料，可以先用 list_extras 看可选项",
                }
            full = matched[0]
            name = full.stem

        size_mb = round(full.stat().st_size / 1024 / 1024, 1)
        task_id = f"extra-{uuid.uuid4().hex[:8]}"

        return {
            "task_id": task_id,
            "summary": f"{name} 已就绪，约 {size_mb} MB，可直接下载",
            "ui_card": {
                "type": "pack_ready",
                "task_id": task_id,
                "data": {
                    "province":     "专题资料",          # 复用 pack_ready 卡片
                    "file_label":   name,
                    "filter_desc":  "学习资料",
                    "exam_type":    "专题",
                    "paper_count":  1,
                    "size_mb":      size_mb,
                    "status":       "ready",
                    "download_url": f"{API_BASE}/api/paper/zip-extra/{name}",
                },
            },
        }
    except Exception as e:
        return _safe_error(e, "download_extra")


@mcp.tool()
def generate_quiz_pdf(
    user_id: int,
    count: int = 20,
    province: Optional[str] = None,
    question_type: Optional[str] = None,
    sub_type: Optional[str] = None,
) -> dict:
    """
    生成一份PDF行测练习试卷（异步任务，30-60秒完成）。

    触发：用户说"生成PDF"、"出一份打印版试卷"、"打印10道判断推理"、"做成PDF"
    不要用于：
      - 在线做题 → 用 prepare_practice_session（立即可用，无需等待）
      - 下载真题原版PDF → 用 trigger_pack_province（质量更好）

    ⚠️ 重要规则：
      - count 严格按用户当前消息的数字，绝对不要拷贝历史消息的数字
      - 用户说"再给我20道" → 重新调用传 count=20
      - 调用后无需说"稍等""马上好"，ui_card会自动显示进度条
      - 只适用于行测选择题，不适用于申论（申论用 trigger_pack_province 下载原版）

    参数：
      user_id: 必填
      count: 题数，默认20，最大100
      province / question_type / sub_type: 筛选条件（可不填）

    返回：ui_card（type='pdf_generating'，前端轮询 /api/pdf/{task_id}/status）
    """
    try:
        require_user(user_id)
        count = min(int(count), MAX_QUESTIONS_PER_CALL)

        # 先抽题，确认有足够数量
        where, params = _build_question_filter(
            province=province, question_type=question_type, sub_type=sub_type,
        )
        rows = query_all(
            f"SELECT id FROM questions WHERE {where} "
            f"ORDER BY RAND() LIMIT %s",
            tuple(params) + (count,),
        )
        if len(rows) < count:
            return {
                "error": "not_enough_questions",
                "message": f"只能找到 {len(rows)} 道符合条件的题，少于请求的 {count} 道",
                "available_count": len(rows),
            }

        question_ids = [r["id"] for r in rows]
        task_id = str(uuid.uuid4())   # 完整 UUID（pdf_jobs.id 是 VARCHAR(36)）

        # 写 pdf_jobs
        params_blob = json.dumps({
            "task_id": task_id,
            "user_id": user_id,
            "count": count,
            "province": province,
            "question_type": question_type,
            "sub_type": sub_type,
            "question_ids": question_ids,
        }, ensure_ascii=False)

        title_parts = []
        if province:
            title_parts.append(province)
        if question_type:
            title_parts.append(question_type)
        title_parts.append(f"{count}题模拟练习")
        title = " ".join(title_parts)

        execute(
            "INSERT INTO pdf_jobs "
            "  (id, user_id, status, params, "
            "   question_count, question_type, province, title) "
            "VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s)",
            (task_id, user_id, params_blob,
             count, question_type, province, title),
        )

        # 同时写 activity_logs（保持原有审计能力）
        try:
            execute(
                "INSERT INTO activity_logs "
                "(actor_id, action_type, target_type, target_id, content, metadata) "
                "VALUES (%s, 'pdf_generate_request', 'pdf_task', %s, %s, %s)",
                (
                    user_id, task_id,
                    f"请求生成 {count} 道题 PDF",
                    json.dumps({
                        "task_id": task_id, "count": count,
                        "filters": {
                            "province": province,
                            "question_type": question_type,
                            "sub_type": sub_type,
                        },
                    }, ensure_ascii=False),
                ),
            )
        except Exception:
            pass  # activity_logs 失败不影响主流程

        return {
            "task_id": task_id,
            "summary": f"已开始生成 {count} 道题的 PDF 试卷，约 30-60 秒",
            "ui_card": {
                "type": "pdf_generating",
                "task_id": task_id,
                "data": {
                    "count": count,
                    "question_type": question_type or "混合",
                    "province": province or "全部",
                    "title": title,
                    "estimated_seconds": 30 + count // 2,
                    "status": "pending",
                    "status_url": f"{API_BASE}/api/pdf/{task_id}/status",
                    "download_url": f"{API_BASE}/api/pdf/{task_id}/download",
                },
                "actions": [
                    {"key": "check", "label": "查看进度",
                     "route": f"{API_BASE}/api/pdf/{task_id}/status"},
                ],
            },
        }
    except Exception as e:
        return _safe_error(e, "generate_quiz_pdf")




# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    mode = os.environ.get("MCP_MODE", "stdio").lower()
    port = int(os.environ.get("MCP_PORT", "8765"))

    if mode == "sse":
        print(f"🚀 MCP Server (SSE) 启动: http://0.0.0.0:{port}/sse")
        print(f"   数据库: {os.environ.get('DB_HOST', 'localhost')}:"
              f"{os.environ.get('DB_PORT', '3306')}/"
              f"{os.environ.get('DB_NAME', 'cs_v2')}")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        # stdio 模式给 Claude Desktop 用，stdout 不能有日志，全走 stderr
        print("🚀 MCP Server (stdio) 启动", file=sys.stderr)
        mcp.run(transport="stdio")
