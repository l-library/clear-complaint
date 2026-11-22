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
