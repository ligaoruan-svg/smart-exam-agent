"""
api/db.py - FastAPI 用的数据库连接

跟 gk_mcp/db.py 几乎一样，但配置从 api.config 读（不是环境变量直接读）。
两套连接是独立的：MCP server 一套（独立进程），FastAPI 一套。
"""
import pymysql
from contextlib import contextmanager
from typing import Optional

from api.config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    get_logger,
)

log = get_logger("api")

DB_CONFIG = {
    "host": DB_HOST, "port": DB_PORT,
    "user": DB_USER, "password": DB_PASSWORD,
    "database": DB_NAME,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


@contextmanager
def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def execute_returning_id(sql: str, params: tuple = ()) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid


def test_connection() -> bool:
    """启动时调用，验证 DB 可连"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
        log.info(f"✅ 数据库连接成功 | {DB_HOST}:{DB_PORT}/{DB_NAME}")
        return True
    except Exception as e:
        log.error(f"❌ 数据库连接失败 | {DB_HOST}:{DB_PORT}/{DB_NAME} | {e}")
        return False
