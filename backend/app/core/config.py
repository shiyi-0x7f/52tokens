"""应用配置：从仓库根目录的 .env.{APP_ENV} 读取，容器内由 env_file 注入。"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
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

    # 统一身份 SCC：用 app 凭据换 app token 后调用联合登录
    scc_base_url: str = "http://127.0.0.1:8001"
    scc_app_id: int | None = None
    scc_app_secret: SecretStr = SecretStr("")

    # Google OAuth（Web 应用客户端）；回调地址必须与 Google Console 中登记的一致
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://127.0.0.1:4321/auth/google/callback"

    # Cloudflare Turnstile 服务端密钥（默认值是官方测试 key，始终通过）
    turnstile_secret_key: SecretStr = SecretStr("1x0000000000000000000000000000000AA")

    session_ttl_days: int = 30
    # 公开站写入的会话 Cookie 名；后台 SPA 与公开站同域，后台接口直接读它
    session_cookie_name: str = "t52_session"
    # 这些邮箱登录后自动成为后台管理员（逗号分隔）
    admin_emails: str = ""

    @field_validator("scc_app_id", mode="before")
    @classmethod
    def _blank_as_none(cls, value: object) -> object:
        # .env 里留空的键读进来是空字符串，视为未配置
        return None if value == "" else value

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
