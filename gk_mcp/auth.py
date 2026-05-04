"""
mcp/auth.py - 鉴权与权限校验

MCP 工具调用时，所有需要 user_id 的工具都通过 require_user() 校验：
  - user_id 必须在 users 表存在
  - 必要时校验 plan / role / daily_limit

关于"FastAPI BFF 强校验"：
  FastAPI 在调用 MCP 工具前，会从 JWT token 解出 user_id，
  然后跟 LLM 传给 MCP 工具的 user_id 参数做对比，不一致就拒绝。
  这层校验在 FastAPI 那边做（下一轮交付）。
  MCP 这里只做"用户存在性"和"配额"层面的校验。
"""

from typing import Optional
from db import query_one, execute


class AuthError(Exception):
    """权限错误，工具内 raise，外层 wrapper 转成友好提示"""
    pass


def require_user(user_id: int) -> dict:
    """
    校验用户存在并返回完整用户信息。
    调用任何需要 user_id 的工具前，先调这个。
    """
    if not user_id or user_id <= 0:
        raise AuthError("缺少有效的 user_id 参数")

    user = query_one(
        "SELECT id, username, nickname, plan, plan_expires_at, "
        "       daily_limit, daily_used, daily_reset_at, "
        "       total_answered, total_correct, role "
        "FROM users WHERE id = %s",
        (user_id,)
    )
    if not user:
        raise AuthError(f"用户 {user_id} 不存在")
    return user


def require_admin(user_id: int) -> dict:
    """管理员工具用，校验 role = 'admin'"""
    user = require_user(user_id)
    if user["role"] != "admin":
        raise AuthError(f"用户 {user_id} 无管理员权限")
    return user


def check_and_consume_daily_quota(user_id: int, amount: int = 1) -> dict:
    """
    检查每日配额并扣减。
    pro 会员或 admin 不扣（daily_limit 设很大也兜得住）。
    返回：{remaining: int, allowed: bool, message: str}

    使用时机：
      - prepare_practice_session 调用时不扣（只准备）
      - start_practice_session 时才扣（真正开始才算）
      - 这个函数被 FastAPI BFF 在 /api/practice/start 时调用，不在 MCP 工具里调
      - MCP 工具里也提供这个 API 备用
    """
    user = require_user(user_id)

    # pro / enterprise 不限次数
    if user["plan"] in ("pro", "enterprise"):
        return {"remaining": 99999, "allowed": True, "message": "会员不限次数"}

    # 检查是否需要重置每日额度（跨天）
    from datetime import datetime, date
    now = datetime.now()
    today = now.date()

    daily_reset_at = user.get("daily_reset_at")
    need_reset = False
    if daily_reset_at is None:
        need_reset = True
    elif isinstance(daily_reset_at, datetime) and daily_reset_at.date() < today:
        need_reset = True

    if need_reset:
        execute(
            "UPDATE users SET daily_used = 0, daily_reset_at = %s WHERE id = %s",
            (now, user_id)
        )
        user["daily_used"] = 0

    used = user["daily_used"] or 0
    limit = user["daily_limit"] or 20
    remaining = limit - used

    if remaining < amount:
        return {
            "remaining": remaining,
            "allowed": False,
            "message": f"今日免费额度已用完（{used}/{limit}），升级 pro 解锁不限次数",
        }

    # 扣减
    execute(
        "UPDATE users SET daily_used = daily_used + %s WHERE id = %s",
        (amount, user_id)
    )
    return {
        "remaining": remaining - amount,
        "allowed": True,
        "message": f"剩余 {remaining - amount} 次",
    }
