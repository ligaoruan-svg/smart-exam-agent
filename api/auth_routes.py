"""
api/auth_routes.py - 用户认证 REST 路由
[redis 版] 限速数据存 Redis，进程重启不丢失
"""
import re
import json
import time
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.config import get_logger, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
from api.auth import (
    current_user, hash_password, verify_password, make_token,
)
from api.db import query_one, execute, execute_returning_id

log = get_logger("api")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ============================================================
# Redis 连接
# 依赖：pip install redis
# 启动：redis-server（Mac: brew install redis）
# ============================================================
import redis as _redis_lib

def _get_redis():
    """获取 Redis 连接，连接失败时抛出清晰错误"""
    try:
        r = _redis_lib.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        log.error(f"[auth] Redis 连接失败: {e}")
        raise RuntimeError("Redis 不可用，请先启动 redis-server")

_redis = _get_redis()


# ============================================================
# 登录限速：按「IP + 用户名」组合限速（Redis 版）
#
# 规则：
#   同一 IP 针对同一用户名，5 次错误锁定 5 分钟
#   同一 IP 累计错误总数超过 20 次，整个 IP 锁定 5 分钟
# ============================================================
_MAX_ATTEMPTS_PER_USER = 5
_MAX_ATTEMPTS_PER_IP   = 20
_LOCK_SECONDS          = 300   # 5 分钟


def _check_rate_limit(ip: str, username: str):
    user_key = f"login:{ip}:{username}"
    ip_key   = f"login_ip:{ip}"

    user_count = int(_redis.get(user_key) or 0)
    ip_count   = int(_redis.get(ip_key)   or 0)

    # 检查 IP 总量限制（防枚举）
    if ip_count >= _MAX_ATTEMPTS_PER_IP:
        ttl = max(_redis.ttl(ip_key), 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"请求过于频繁，请 {ttl} 秒后再试"
        )

    # 检查 IP + 用户名 限制
    if user_count >= _MAX_ATTEMPTS_PER_USER:
        ttl = max(_redis.ttl(user_key), 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"该账号登录尝试过多，请 {ttl} 秒后再试"
        )


def _record_failed_attempt(ip: str, username: str):
    user_key = f"login:{ip}:{username}"
    ip_key   = f"login_ip:{ip}"

    # incr 原子递增，expire 设置/刷新过期时间
    _redis.incr(user_key)
    _redis.expire(user_key, _LOCK_SECONDS)
    _redis.incr(ip_key)
    _redis.expire(ip_key, _LOCK_SECONDS)


def _clear_attempts(ip: str, username: str):
    user_key = f"login:{ip}:{username}"
    _redis.delete(user_key)
    # ip_key 不清除（成功登录不重置 IP 计数，防止攻击者穿插正确密码绕过）


def _get_attempts_left(ip: str, username: str) -> int:
    user_key = f"login:{ip}:{username}"
    count = int(_redis.get(user_key) or 0)
    return max(_MAX_ATTEMPTS_PER_USER - count, 0)


# ============================================================
# 邮箱验证码：Redis 存储（重启不丢失）
# key: vc:reg:{email}  / vc:reset:{email}
# value: JSON {code, used}，TTL = 300s
# ============================================================
_EMAIL_CODE_EXPIRE   = 300   # 5 分钟有效
_EMAIL_SEND_COOLDOWN = 60    # 同一邮箱 60 秒内只能发一次


def _vc_key(prefix: str, email: str) -> str:
    return f"vc:{prefix}:{email}"


def _vc_cooldown_key(prefix: str, email: str) -> str:
    return f"vc_cd:{prefix}:{email}"


def _vc_get(prefix: str, email: str) -> dict | None:
    raw = _redis.get(_vc_key(prefix, email))
    return json.loads(raw) if raw else None


def _vc_set(prefix: str, email: str, code: str):
    data = {"code": code, "used": False}
    _redis.setex(_vc_key(prefix, email), _EMAIL_CODE_EXPIRE, json.dumps(data))
    _redis.setex(_vc_cooldown_key(prefix, email), _EMAIL_SEND_COOLDOWN, "1")


def _vc_mark_used(prefix: str, email: str):
    raw = _redis.get(_vc_key(prefix, email))
    if raw:
        data = json.loads(raw)
        data["used"] = True
        ttl = _redis.ttl(_vc_key(prefix, email))
        _redis.setex(_vc_key(prefix, email), max(ttl, 1), json.dumps(data))


def _vc_check_cooldown(prefix: str, email: str) -> int:
    """返回剩余冷却秒数，0 表示可以发送"""
    ttl = _redis.ttl(_vc_cooldown_key(prefix, email))
    return max(ttl, 0)


# ============================================================
# 邮件发送
# ============================================================
def _send_email(to_email: str, subject: str, html: str) -> None:
    if not SMTP_USER or not SMTP_PASS:
        raise RuntimeError("SMTP 未配置，请检查 .env 文件")
    msg = MIMEText(html, "html", "utf-8")
    from email.header import Header
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"]    = SMTP_USER
    msg["To"]      = to_email
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [to_email], msg.as_string())


def _code_html(code: str, title: str, subtitle: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#f9fafb;border-radius:12px;">
      <div style="text-align:center;margin-bottom:24px;">
        <div style="background:linear-gradient(135deg,#10b981,#059669);display:inline-block;padding:10px 20px;border-radius:8px;">
          <span style="color:#fff;font-size:18px;font-weight:700;">公考小智</span>
        </div>
      </div>
      <h2 style="color:#111827;text-align:center;margin-bottom:8px;">{title}</h2>
      <p style="color:#6b7280;text-align:center;margin-bottom:28px;">{subtitle}</p>
      <div style="background:#fff;border-radius:10px;padding:24px;text-align:center;border:1px solid #e5e7eb;">
        <span style="font-size:36px;font-weight:800;letter-spacing:8px;color:#10b981;">{code}</span>
      </div>
      <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:24px;">如非本人操作，请忽略此邮件</p>
    </div>
    """


def _log_login(user_id: int, username: str, ip: str, user_agent: str, login_status: str):
    """记录登录日志，失败不影响主流程"""
    try:
        execute(
            "INSERT INTO login_logs (user_id, username, ip, user_agent, status) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, username, ip, user_agent[:500] if user_agent else '', login_status),
        )
    except Exception as e:
        log.warning(f"[auth] 写登录日志失败: {e}")


# ============================================================
# 请求体
# ============================================================
class LoginPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6, max_length=50)
    email: str
    code: str = Field(..., min_length=6, max_length=6)
    nickname: str | None = None


class SendCodePayload(BaseModel):
    email: str


class ResetPasswordPayload(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6, max_length=50)


# ============================================================
# 路由：登录
# ============================================================
@router.post("/login")
def login(payload: LoginPayload, request: Request):
    ip = request.client.host or "unknown"
    ua = request.headers.get("User-Agent", "")

    _check_rate_limit(ip, payload.username)

    user = query_one(
        "SELECT id, username, password_hash, role FROM users WHERE username = %s OR email = %s",
        (payload.username, payload.username),
    )
    if not user:
        log.warning(f"[auth] 账号不存在 ip={ip} username={payload.username}")
        _log_login(0, payload.username, ip, ua, "fail_not_found")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")

    if not verify_password(payload.password, user["password_hash"]):
        _record_failed_attempt(ip, payload.username)
        attempts_left = _get_attempts_left(ip, payload.username)
        log.warning(f"[auth] 密码错误 ip={ip} username={payload.username} 剩余尝试={attempts_left}")
        _log_login(user["id"], user["username"], ip, ua, "fail_password")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")

    _clear_attempts(ip, payload.username)
    execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
    _log_login(user["id"], user["username"], ip, ua, "success")
    token = make_token(user["id"], user["username"], user["role"])
    log.info(f"[auth] 登录成功 user_id={user['id']} username={user['username']}")
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    }


# ============================================================
# 路由：发送注册验证码
# ============================================================
@router.post("/send-code")
def send_code(payload: SendCodePayload):
    email = payload.email.strip().lower()

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱格式不正确")

    cooldown = _vc_check_cooldown("reg", email)
    if cooldown > 0:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"发送太频繁，请 {cooldown} 秒后再试")

    if query_one("SELECT id FROM users WHERE email = %s", (email,)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已被注册")

    code = str(random.randint(100000, 999999))
    _vc_set("reg", email, code)

    try:
        _send_email(
            email,
            f"【公考小智】注册验证码：{code}",
            _code_html(code, "邮箱验证码", "请使用以下验证码完成注册，验证码 5 分钟内有效"),
        )
        log.info(f"[auth] 注册验证码已发送 email={email}")
    except Exception as e:
        log.error(f"[auth] 发送验证码失败 email={email} err={e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "邮件发送失败，请检查邮箱地址是否正确")

    return {"ok": True, "message": "验证码已发送，请查收邮件"}


# ============================================================
# 路由：注册
# ============================================================
@router.post("/register")
def register(payload: RegisterPayload):
    email = payload.email.strip().lower()

    record = _vc_get("reg", email)
    if not record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先获取验证码")
    if record.get("used"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码已使用，请重新获取")
    if record.get("code") != payload.code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误")

    _vc_mark_used("reg", email)

    if not re.match(r"^[a-zA-Z0-9_]+$", payload.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名只能包含字母、数字、下划线")

    if query_one("SELECT id FROM users WHERE username = %s", (payload.username,)):
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已被占用")
    if query_one("SELECT id FROM users WHERE email = %s", (email,)):
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱已被占用")

    try:
        DEFAULT_DAILY_LIMIT = 20
        new_id = execute_returning_id(
            "INSERT INTO users (username, nickname, email, password_hash, role, daily_limit) "
            "VALUES (%s, %s, %s, %s, 'user', %s)",
            (payload.username, payload.nickname or payload.username,
             email, hash_password(payload.password), DEFAULT_DAILY_LIMIT),
        )
    except Exception as e:
        if "Duplicate entry" in str(e) or "1062" in str(e):
            raise HTTPException(status.HTTP_409_CONFLICT, "用户名已被占用")
        log.error(f"[auth] 注册写库失败 username={payload.username} err={e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "注册失败，请稍后重试")

    token = make_token(new_id, payload.username, "user")
    log.info(f"[auth] 注册成功 user_id={new_id} username={payload.username}")
    return {
        "token": token,
        "user": {
            "id": new_id,
            "username": payload.username,
            "role": "user",
        },
    }


# ============================================================
# 路由：查询当前用户
# ============================================================
@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user.get("nickname") or user["username"],
        "email": user.get("email"),
        "plan": user["plan"],
        "daily_limit": user["daily_limit"],
        "daily_used": user["daily_used"],
        "total_answered": user["total_answered"],
        "total_correct": user["total_correct"],
        "role": user["role"],
    }


# ============================================================
# 路由：发送重置密码验证码
# ============================================================
@router.post("/send-reset-code")
def send_reset_code(payload: SendCodePayload):
    email = payload.email.strip().lower()

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱格式不正确")

    user = query_one("SELECT id FROM users WHERE email = %s", (email,))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该邮箱未注册")

    cooldown = _vc_check_cooldown("reset", email)
    if cooldown > 0:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"发送太频繁，请 {cooldown} 秒后再试")

    code = str(random.randint(100000, 999999))
    _vc_set("reset", email, code)

    try:
        _send_email(
            email,
            f"【公考小智】重置密码验证码：{code}",
            _code_html(code, "重置密码验证码", "你正在重置密码，验证码 5 分钟内有效"),
        )
        log.info(f"[auth] 重置密码验证码已发送 email={email}")
    except Exception as e:
        log.error(f"[auth] 重置密码验证码发送失败 email={email} err={e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "邮件发送失败，请稍后重试")

    return {"ok": True, "message": "验证码已发送，请查收邮件"}


# ============================================================
# 路由：重置密码
# ============================================================
@router.post("/reset-password")
def reset_password(payload: ResetPasswordPayload):
    email = payload.email.strip().lower()

    record = _vc_get("reset", email)
    if not record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先获取验证码")
    if record.get("used"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码已使用，请重新获取")
    if record.get("code") != payload.code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误")

    _vc_mark_used("reset", email)

    user = query_one("SELECT id, username FROM users WHERE email = %s", (email,))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")

    execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hash_password(payload.new_password), user["id"]),
    )
    log.info(f"[auth] 密码重置成功 user_id={user['id']} username={user['username']}")
    return {"ok": True, "message": "密码重置成功，请重新登录"}
