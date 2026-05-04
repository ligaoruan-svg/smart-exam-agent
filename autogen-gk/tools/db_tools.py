"""
tools/db_tools.py - 复用公考小智数据库查询
直接连接 cs_v2，供各 Agent 调用
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "cs_v2"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


# ── 供 Agent 调用的工具函数 ──

def get_user_stats(user_id: int) -> dict:
    """获取用户基础答题统计"""
    row = query_one(
        "SELECT total_answered, total_correct, plan FROM users WHERE id = %s",
        (user_id,),
    )
    if not row:
        return {"error": "用户不存在"}
    total = row["total_answered"] or 0
    correct = row["total_correct"] or 0
    return {
        "total_answered": total,
        "total_correct": correct,
        "correct_rate": round(correct / total * 100, 1) if total else 0,
        "plan": row["plan"],
    }


def get_user_weakness(user_id: int) -> dict:
    """获取用户薄弱点"""
    row = query_one(
        "SELECT rate_yanyu, rate_panduan, rate_shuliang, rate_changshi "
        "FROM user_weaknesses WHERE user_id = %s",
        (user_id,),
    )
    if not row:
        return {"has_data": False, "message": "暂无薄弱点数据"}
    rates = {
        "言语理解": float(row.get("rate_yanyu") or 0),
        "判断推理": float(row.get("rate_panduan") or 0),
        "数量关系": float(row.get("rate_shuliang") or 0),
        "常识判断": float(row.get("rate_changshi") or 0),
    }
    sorted_rates = sorted(rates.items(), key=lambda x: -x[1])
    return {
        "has_data": True,
        "rates": dict(sorted_rates),
        "weakest": sorted_rates[0][0] if sorted_rates else None,
    }


def get_random_questions(question_type: str = None, count: int = 5) -> list[dict]:
    """随机抽题"""
    sql = "SELECT id, stem, option_a, option_b, option_c, option_d, answer, analysis, question_type FROM questions WHERE is_valid=1 AND is_complete=1"
    params: list = []
    if question_type:
        sql += " AND question_type = %s"
        params.append(question_type)
    sql += f" ORDER BY RAND() LIMIT {count}"
    return query_all(sql, tuple(params))


def get_recent_wrong_questions(user_id: int, limit: int = 5) -> list[dict]:
    """获取最近错题"""
    return query_all(
        "SELECT q.id, q.stem, q.question_type, q.answer, q.analysis, "
        "       w.wrong_count, w.last_wrong_at "
        "FROM wrong_questions w "
        "JOIN questions q ON q.id = w.question_id "
        "WHERE w.user_id = %s AND w.is_mastered = 0 "
        "ORDER BY w.last_wrong_at DESC LIMIT %s",
        (user_id, limit),
    )
