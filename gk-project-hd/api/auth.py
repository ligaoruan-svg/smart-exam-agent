"""
api/auth.py - JWT 鉴权

用法（FastAPI 路由）：
    from api.auth import current_user, current_admin

    @app.get("/api/me")
    def me(user: dict = Depends(current_user)):
        return user

    @app.get("/api/admin/stats")
    def admin_stats(admin: dict = Depends(current_admin)):
        return ...

注意：
  - 密码 hash 用 sha256("gk2026" + password) —— 跟旧版兼容
  - JWT secret 从 .env 读，不要写死
  - 老用户的 token 因为 secret 换了会失效，需要重新登录
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Header, HTTPException, status, Depends

from api.config import (
    JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRES_HOURS,
    get_logger,
)
from api.db import query_one, execute

log = get_logger("api")


# ============================================================
# 密码处理
# ============================================================
def hash_password(password: str) -> str:
    """跟旧版一致：sha256('gk2026' + password)"""
    return hashlib.sha256(f"gk2026{password}".encode()).hexdigest()


def verify_password(password: str, expected_hash: str) -> bool:
    return hash_password(password) == expected_hash


# ============================================================
# JWT 签发与校验
# ============================================================
def make_token(user_id: int, username: str, role: str = "user") -> str:
    payload = {
        "uid": user_id,
        "username": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码 token，失败抛 401"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 已过期")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"token 无效: {e}")


# ============================================================
# FastAPI Dependencies
# ============================================================
def _extract_token(authorization: Optional[str]) -> str:
    """从 Authorization header 提 Bearer token"""
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 Authorization 头")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Authorization 格式应为 'Bearer <token>'")
    return parts[1]


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    获取当前登录用户。注入到路由参数即可：
        @app.get("/foo")
        def foo(user: dict = Depends(current_user)):
            print(user["id"], user["username"])
    """
    token = _extract_token(authorization)
    payload = decode_token(token)
    uid = payload.get("uid")
    if not uid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 缺少 uid")

    user = query_one(
        "SELECT id, username, nickname, email, plan, daily_limit, daily_used, "
        "       total_answered, total_correct, role "
        "FROM users WHERE id = %s",
        (uid,),
    )
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def current_admin(user: dict = Depends(current_user)) -> dict:
    """要求 admin 角色"""
    if user.get("role") != "admin":
        log.warning(f"非 admin 用户 {user.get('id')} 访问了 admin 接口")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """可选鉴权：有 token 就解析，没 token 返回 None"""
    if not authorization:
        return None
    try:
        return current_user(authorization)
    except HTTPException:
        return None


# ============================================================
# 安全校验：MCP 工具调用时，强校验 LLM 传的 user_id
# ============================================================
def assert_uid_match(token_uid: int, llm_uid: Optional[int]) -> int:
    """
    LLM 调 MCP 工具时如果传了 user_id 参数，必须跟 token 里的 uid 一致，
    否则视为越权（防止 LLM 被 prompt injection 后查别人数据）。
    
    返回应该使用的 user_id（永远是 token_uid）
    """
    if llm_uid is None:
        return token_uid
    if int(llm_uid) != int(token_uid):
        log.warning(
            f"⚠️  user_id 不匹配 | token_uid={token_uid} llm_uid={llm_uid} "
            f"→ 强制使用 token_uid"
        )
    return token_uid
