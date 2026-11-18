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


@lru_cache
def get_settings() -> Settings:
    return Settings()
