"""账号域的请求与响应模型，字段与命名照 docs/api.md 第 2、4 节。"""

from pydantic import BaseModel


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    access_expires_at: str
    refresh_expires_at: str


class UserOut(BaseModel):
    id: int
    phone: str
    is_demo: bool
    created_at: str


class AuthData(BaseModel):
    user: UserOut
    tokens: TokenPair
    # 档案表 M2 落地后按必填项（birth_date、sex）计算，此前恒为 False
    profile_complete: bool


class RefreshData(BaseModel):
    tokens: TokenPair


class RegisterRequest(BaseModel):
    phone: str
    password: str
    consent_version: str
    accept_privacy: bool
    accept_sensitive: bool


class LoginRequest(BaseModel):
    phone: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PrivacyMeta(BaseModel):
    current_version: str
    policy_url: str
    sensitive_policy_url: str


class Profile(BaseModel):
    name: str | None
    birth_date: str | None
    age_years: int | None
    sex: str | None
    city_code: str | None
    city_name: str | None
    # null 未告知，[] 明确确认没有；两者语义不同，不能合并
    conditions: list[str] | None
    condition_note: str | None
    allergies: list[str] | None
    allergy_note: str | None
    required_missing: list[str]
    updated_at: str


class ProfileData(BaseModel):
    profile: Profile | None


class ProfileUpdate(BaseModel):
    """部分更新：未出现的字段保持不变，出现且为 null/""/[] 的字段清空。

    city_code 与 city_name 必须同时出现（成对提交或成对清空）。
    """

    name: str | None = None
    birth_date: str | None = None
    sex: str | None = None
    city_code: str | None = None
    city_name: str | None = None
    conditions: list[str] | None = None
    condition_note: str | None = None
    allergies: list[str] | None = None
    allergy_note: str | None = None


class PrivacyRecord(BaseModel):
    current_version: str
    consented_version: str | None
    consented_at: str | None
    outdated: bool


class ExportData(BaseModel):
    url: str
    expires_at: str
    size_bytes: int


class DeleteConfirm(BaseModel):
    confirm: str


class ClearData(BaseModel):
    cleared: dict[str, int]
