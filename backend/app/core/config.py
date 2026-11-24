from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。所有字段都能被同名大写环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "清诉 ClearComplaint API"
    # 本地默认指向 docker-compose 里的 Postgres；生产由环境变量注入
    database_url: str = (
        "postgresql+asyncpg://clear_complaint:clear_complaint@localhost:5432/clear_complaint"
    )

    # 认证。jwt_secret 生产必须注入，本地与 CI 用开发默认值跑测试
    jwt_secret: str = "dev-only-jwt-secret-0123456789abcdef"
    access_token_seconds: int = 2 * 60 * 60
    refresh_token_days: int = 30

    # AgentArts 三条工作流（docs/api-agentarts.md 16.1）。Key 只经环境变量注入，永不入库
    agentarts_profile_intake_url: str = ""
    agentarts_followup_supplement_url: str = ""
    agentarts_triage_url: str = ""
    agentarts_profile_intake_api_key: str = ""
    agentarts_followup_supplement_api_key: str = ""
    agentarts_triage_api_key: str = ""
    agentarts_invoke_mode: str = "published"

    # 进程内定时任务（用药提醒生成、超时、过期、未保存清理）。
    # 默认关闭：测试与 CI 不受后台写库影响；生产与本地演示经 .env 打开
    scheduler_enabled: bool = False

    # 导出包落盘目录。CI/测试不设；生产由环境变量注入
    export_dir: str = ""

    # 隐私政策版本与链接：GET /api/meta/privacy 返回，注册时校验 consent_version
    privacy_version: str = "2026-11-01"
    privacy_policy_url: str = "/#/pages/privacy/index?section=privacy"
    sensitive_policy_url: str = "/#/pages/privacy/index?section=sensitive"


@lru_cache
def get_settings() -> Settings:
    return Settings()
