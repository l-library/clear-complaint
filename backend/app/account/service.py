"""账号业务：注册、登录、令牌签发与轮换、当前用户解析。

安全口径：密码哈希用标准库 PBKDF2，不引第三方；刷新令牌只存 SHA-256 哈希，
轮换用条件更新原子认领旧令牌，重放一律 1005；登录失败锁定是进程内计数
（docs/api.md 第 15 节：接口限流暂不引 Redis，重启即清零）。
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import Consent, RefreshToken, User
from app.account.schema import AuthData, LoginRequest, RegisterRequest, TokenPair, UserOut
from app.common.clock import format_shanghai, now_shanghai
from app.common.codes import ErrorCode
from app.common.errors import BizException
from app.core.config import get_settings
from app.db.session import get_session

_PHONE = re.compile(r"\d{11}")
_PBKDF2_ITERATIONS = 260_000

# 登录失败锁定：10 分钟窗口内 5 次失败（docs/api.md 4.2）
_LOCK_WINDOW = timedelta(minutes=10)
_LOCK_THRESHOLD = 5
_login_failures: dict[str, list[datetime]] = {}


def _format_error(phone: str, password: str) -> str | None:
    if _PHONE.fullmatch(phone) is None:
        return "手机号必须是 11 位数字"
    has_letter = re.search(r"[A-Za-z]", password) is not None
    has_digit = re.search(r"\d", password) is not None
    if not 8 <= len(password) <= 32 or not has_letter or not has_digit:
        return "密码须为 8 到 32 位且同时含字母与数字"
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_access_token(user_id: int) -> tuple[str, datetime]:
    settings = get_settings()
    now = now_shanghai()
    expires_at = now + timedelta(seconds=settings.access_token_seconds)
    token = jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": now, "exp": expires_at},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token, expires_at


async def _token_pair(session: AsyncSession, user: User) -> TokenPair:
    settings = get_settings()
    access, access_expires = _issue_access_token(user.id)
    refresh = secrets.token_urlsafe(32)
    refresh_expires = now_shanghai() + timedelta(days=settings.refresh_token_days)
    session.add(
        RefreshToken(user_id=user.id, token_hash=_hash(refresh), expires_at=refresh_expires)
    )
    # 刷新令牌先落库再返回，避免客户端拿到一条用不了的令牌
    await session.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        access_expires_at=format_shanghai(access_expires),
        refresh_expires_at=format_shanghai(refresh_expires),
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        phone=user.phone,
        is_demo=user.is_demo,
        created_at=format_shanghai(user.created_at),
    )


async def register(session: AsyncSession, payload: RegisterRequest) -> AuthData:
    settings = get_settings()
    rule_error = _format_error(payload.phone, payload.password)
    if rule_error is not None:
        raise BizException(ErrorCode.PHONE_OR_PASSWORD_INVALID, rule_error)
    if not payload.accept_privacy or not payload.accept_sensitive:
        raise BizException(ErrorCode.PRIVACY_CONSENT_REQUIRED)
    if payload.consent_version != settings.privacy_version:
        raise BizException(ErrorCode.PRIVACY_CONSENT_REQUIRED, "隐私政策版本不是当前版本")

    existing = await session.scalar(select(User.id).where(User.phone == payload.phone))
    if existing is not None:
        raise BizException(ErrorCode.PHONE_ALREADY_REGISTERED)

    user = User(phone=payload.phone, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        # 并发注册同一手机号，唯一约束兜底
        await session.rollback()
        raise BizException(ErrorCode.PHONE_ALREADY_REGISTERED) from None
    session.add(
        Consent(
            user_id=user.id,
            version=payload.consent_version,
            sensitive_accepted=payload.accept_sensitive,
        )
    )
    tokens = await _token_pair(session, user)
    await session.refresh(user)
    return AuthData(user=_user_out(user), tokens=tokens, profile_complete=False)


def _check_lockout(phone: str) -> None:
    failures = [t for t in _login_failures.get(phone, []) if t > now_shanghai() - _LOCK_WINDOW]
    if failures:
        _login_failures[phone] = failures
    if len(failures) >= _LOCK_THRESHOLD:
        raise BizException(ErrorCode.LOGIN_TOO_MANY_ATTEMPTS)


def _record_failure(phone: str) -> None:
    _login_failures.setdefault(phone, []).append(now_shanghai())


async def login(session: AsyncSession, payload: LoginRequest) -> AuthData:
    _check_lockout(payload.phone)
    user = await session.scalar(select(User).where(User.phone == payload.phone))
    if user is None or not verify_password(payload.password, user.password_hash):
        _record_failure(payload.phone)
        raise BizException(ErrorCode.LOGIN_CREDENTIALS_WRONG)
    _login_failures.pop(payload.phone, None)
    tokens = await _token_pair(session, user)
    return AuthData(user=_user_out(user), tokens=tokens, profile_complete=False)


async def refresh_tokens(session: AsyncSession, token: str) -> TokenPair:
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    if row is None or row.used_at is not None or row.expires_at < now_shanghai():
        raise BizException(ErrorCode.REFRESH_TOKEN_INVALID)
    # 条件更新原子认领旧令牌，防并发双花；没抢到的那个请求判重放
    claimed = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.used_at.is_(None))
        .values(used_at=now_shanghai())
        .returning(RefreshToken.id)
    )
    if claimed.scalar_one_or_none() is None:
        raise BizException(ErrorCode.REFRESH_TOKEN_INVALID)
    user = await session.get(User, row.user_id)
    if user is None:
        raise BizException(ErrorCode.REFRESH_TOKEN_INVALID)
    return await _token_pair(session, user)


async def logout(session: AsyncSession, user: User, token: str) -> None:
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == _hash(token),
            RefreshToken.user_id == user.id,
            RefreshToken.used_at.is_(None),
        )
        .values(used_at=now_shanghai())
    )
    await session.commit()
    # 不存在的令牌也按成功处理，幂等，不区分存在性


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """需要鉴权的路由统一 Depends 这个函数；跨域包只 import service，不碰 router。"""
    if authorization is None or not authorization.startswith("Bearer "):
        raise BizException(ErrorCode.UNAUTHORIZED)
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload: dict[str, Any] = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise BizException(ErrorCode.ACCESS_TOKEN_EXPIRED) from None
    except jwt.InvalidTokenError:
        raise BizException(ErrorCode.UNAUTHORIZED) from None
    if payload.get("type") != "access":
        raise BizException(ErrorCode.UNAUTHORIZED)
    try:
        user_id = int(str(payload["sub"]))
    except KeyError:
        raise BizException(ErrorCode.UNAUTHORIZED) from None
    user = await session.get(User, user_id)
    if user is None:
        raise BizException(ErrorCode.UNAUTHORIZED)
    return user


__all__ = [
    "get_current_user",
    "hash_password",
    "login",
    "logout",
    "refresh_tokens",
    "register",
    "verify_password",
]
