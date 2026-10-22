"""应用配置：从仓库根目录的 .env.{APP_ENV} 读取，容器内由 env_file 注入。"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ENV = os.getenv("APP_ENV", "dev")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / f".env.{APP_ENV}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8100

    database_url: str = "postgresql+asyncpg://tokens52:change-me@127.0.0.1:5432/tokens52"
    redis_url: str = "redis://127.0.0.1:6379/6"
    redis_key_prefix: str = "52tokens:"

    internal_api_token: SecretStr = SecretStr("")

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
