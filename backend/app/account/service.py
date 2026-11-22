"""账号业务：注册、登录、令牌签发与轮换、当前用户解析。

安全口径：密码哈希用标准库 PBKDF2，不引第三方；刷新令牌只存 SHA-256 哈希，
轮换用条件更新原子认领旧令牌，重放一律 1005；登录失败锁定是进程内计数
（docs/api.md 第 15 节：接口限流暂不引 Redis，重启即清零）。
"""

import hashlib
import hmac
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.account.models import Consent, Profile, RefreshToken, User
from app.account.schema import (
    AuthData,
    LoginRequest,
    PrivacyRecord,
    ProfileUpdate,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.account.schema import (
    Profile as ProfileOut,
)
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
    complete = await _profile_complete(session, user.id)
    return AuthData(user=_user_out(user), tokens=tokens, profile_complete=complete)


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
    complete = await _profile_complete(session, user.id)
    return AuthData(user=_user_out(user), tokens=tokens, profile_complete=complete)


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
    "get_profile",
    "hash_password",
    "login",
    "logout",
    "privacy_record",
    "refresh_tokens",
    "register",
    "update_profile",
    "verify_password",
]


# ---- 档案（docs/api.md 第 6 节） ----

_SEX_VALUES = ("male", "female", "undisclosed")
_EARLIEST_BIRTH = date(1900, 1, 1)


async def _profile_complete(session: AsyncSession, user_id: int) -> bool:
    """必填项只有 birth_date 与 sex（docs/api.md 2.3、16.4 的公共口径）。"""
    row = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    return row is not None and row.birth_date is not None and row.sex is not None


def _age_years(born: date) -> int:
    today = now_shanghai().date()
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


def _profile_out(row: Profile) -> ProfileOut:
    missing: list[str] = []
    if row.birth_date is None:
        missing.append("birth_date")
    if row.sex is None:
        missing.append("sex")
    return ProfileOut(
        name=row.name,
        birth_date=row.birth_date.isoformat() if row.birth_date is not None else None,
        age_years=_age_years(row.birth_date) if row.birth_date is not None else None,
        sex=row.sex,
        city_code=row.city_code,
        city_name=row.city_name,
        conditions=row.conditions,
        condition_note=row.condition_note,
        allergies=row.allergies,
        allergy_note=row.allergy_note,
        required_missing=missing,
        updated_at=format_shanghai(row.updated_at),
    )


def _parse_birth_date(raw: str) -> date:
    try:
        born = date.fromisoformat(raw)
    except ValueError:
        raise BizException(ErrorCode.INVALID_PARAM, "birth_date 须为 yyyy-MM-dd") from None
    if born < _EARLIEST_BIRTH or born > now_shanghai().date():
        raise BizException(ErrorCode.INVALID_PARAM, "birth_date 须在 1900-01-01 与今天之间")
    return born


def _check_terms(items: list[str] | None, field: str) -> list[str] | None:
    """conditions/allergies 的条目校验；None 与 [] 都原样落库（语义不同）。"""
    if items is None:
        return None
    if len(items) > 10:
        raise BizException(ErrorCode.INVALID_PARAM, f"{field} 最多 10 项")
    for item in items:
        if not item or len(item) > 20:
            raise BizException(ErrorCode.INVALID_PARAM, f"{field} 每项须为 1 到 20 字")
    return items


def _check_note(note: str | None, field: str) -> str | None:
    if note is None:
        return None
    note = note.strip()
    if len(note) > 200:
        raise BizException(ErrorCode.INVALID_PARAM, f"{field} 不能超过 200 字")
    return note or None


def _validate_update(payload: ProfileUpdate, fields: set[str]) -> dict[str, object]:
    """校验并归一 PUT 的字段。fields 是 model_fields_set，区分"未提交"与"提交空值"。"""
    values: dict[str, object] = {}
    if "name" in fields:
        name = payload.name
        if name is not None and len(name.strip()) == 0:
            name = None
        if name is not None and len(name) > 40:
            raise BizException(ErrorCode.INVALID_PARAM, "name 不能超过 40 字")
        values["name"] = name
    if "birth_date" in fields:
        values["birth_date"] = (
            _parse_birth_date(payload.birth_date) if payload.birth_date is not None else None
        )
    if "sex" in fields:
        if payload.sex is not None and payload.sex not in _SEX_VALUES:
            raise BizException(ErrorCode.INVALID_PARAM, "sex 取值须为 male/female/undisclosed")
        values["sex"] = payload.sex
    if {"city_code", "city_name"} & fields:
        # 城市成对提交或成对清空，只提交一边按参数错误处理
        if {"city_code", "city_name"} - fields:
            raise BizException(ErrorCode.INVALID_PARAM, "city_code 与 city_name 须同时提交")
        code, city = payload.city_code, payload.city_name
        if code is None and city is None:
            values["city_code"] = None
            values["city_name"] = None
        elif code is not None and city is not None:
            if len(code) != 6 or not code.isdigit():
                raise BizException(ErrorCode.INVALID_PARAM, "city_code 须为 6 位行政区划码")
            if not city or len(city) > 40:
                raise BizException(ErrorCode.INVALID_PARAM, "city_name 须为 1 到 40 字")
            values["city_code"] = code
            values["city_name"] = city
        else:
            raise BizException(ErrorCode.INVALID_PARAM, "city_code 与 city_name 须成对提交")
    if "conditions" in fields:
        values["conditions"] = _check_terms(payload.conditions, "conditions")
    if "condition_note" in fields:
        values["condition_note"] = _check_note(payload.condition_note, "condition_note")
    if "allergies" in fields:
        values["allergies"] = _check_terms(payload.allergies, "allergies")
    if "allergy_note" in fields:
        values["allergy_note"] = _check_note(payload.allergy_note, "allergy_note")
    return values


async def get_profile(session: AsyncSession, user_id: int) -> ProfileOut | None:
    row = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    return _profile_out(row) if row is not None else None


async def update_profile(session: AsyncSession, user: User, payload: ProfileUpdate) -> ProfileOut:
    values = _validate_update(payload, set(payload.model_fields_set))
    row = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    if row is None:
        row = Profile(user_id=user.id)
        session.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return _profile_out(row)


async def privacy_record(session: AsyncSession, user_id: int) -> PrivacyRecord:
    current = get_settings().privacy_version
    row = await session.scalar(
        select(Consent).where(Consent.user_id == user_id).order_by(Consent.created_at.desc())
    )
    consented = row.version if row is not None else None
    return PrivacyRecord(
        current_version=current,
        consented_version=consented,
        consented_at=format_shanghai(row.created_at) if row is not None else None,
        outdated=consented != current,
    )
