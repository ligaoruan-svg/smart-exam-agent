"""
mcp/db.py - 数据库连接 + 字典缓存

DB_CONFIG 通过环境变量读取，缺省值适用于本地开发。
启动时一次性加载 provinces / plans 等字典表到内存。
"""

import os
import pymysql
from contextlib import contextmanager
from typing import Optional

# ============================================================
# 配置（环境变量覆盖）
# ============================================================
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", "3306")),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "ruanligao"),
    "database": os.environ.get("DB_NAME", "cs_v2"),
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,   # 简单场景下开 autocommit，避免每次手动 commit
}


# ============================================================
# 连接获取（带自动重连）
# ============================================================
@contextmanager
def get_db():
    """
    用法：
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
    """
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """快捷封装：一行 SELECT 返回所有结果"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """快捷封装：一行 SELECT 返回一条"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """快捷封装：INSERT/UPDATE/DELETE，返回受影响行数"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def execute_returning_id(sql: str, params: tuple = ()) -> int:
    """INSERT 后返回 lastrowid"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid


# ============================================================
# 字典缓存（启动时加载一次）
# ============================================================
_provinces_cache: list[dict] = []
_plans_cache: list[dict] = []
_cache_loaded = False


def load_dict_cache():
    """
    启动时调用一次，把字典表全部加载到内存。
    provinces / plans 这种几乎不变的表，没必要每次查询都打 DB。
    """
    global _provinces_cache, _plans_cache, _cache_loaded
    if _cache_loaded:
        return
    try:
        _provinces_cache = query_all(
            "SELECT code, name, is_hot, sort_order, total_papers, total_downloads "
            "FROM provinces ORDER BY sort_order"
        )
        _plans_cache = query_all(
            "SELECT plan_key, name, price, period, description, features, "
            "       is_recommended, sort_order, is_active "
            "FROM plans WHERE is_active = 1 ORDER BY sort_order"
        )
        _cache_loaded = True
        print(f"✅ 字典缓存加载完成：{len(_provinces_cache)} 省份，{len(_plans_cache)} 套餐")
    except Exception as e:
        print(f"⚠️  字典缓存加载失败：{e}")
        # 不抛异常，让后续工具调用时按需查 DB 兜底


def get_provinces_cached(hot_only: bool = False) -> list[dict]:
    if not _cache_loaded:
        load_dict_cache()
    if hot_only:
        return [p for p in _provinces_cache if p["is_hot"]]
    return _provinces_cache


def get_plans_cached() -> list[dict]:
    if not _cache_loaded:
        load_dict_cache()
    return _plans_cache
