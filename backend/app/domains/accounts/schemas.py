from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None
    is_admin: bool


class GoogleStartIn(BaseModel):
    # 登录后回到的站内路径
    next: str = Field(default="/", max_length=500)

    @field_validator("next")
    @classmethod
    def _site_relative(cls, value: str) -> str:
        """只接受站内相对路径，防止开放重定向（//host、/\\host、绝对 URL 都拒绝）。"""
        if not value.startswith("/") or value.startswith("//") or "\\" in value:
            raise ValueError("next 必须是站内相对路径")
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("next 含控制字符")
        return value


class AuthorizeOut(BaseModel):
    """第三方授权跳转信息。state 由公开站写入浏览器 Cookie，回调时比对，防止登录 CSRF。"""

    authorize_url: str
    state: str


class OAuthCallbackIn(BaseModel):
    code: str = Field(max_length=2000)
    state: str = Field(max_length=512)


class EmailSendIn(BaseModel):
    email: str = Field(max_length=200)
    turnstile_token: str | None = Field(default=None, max_length=4096)
    remote_ip: str | None = Field(default=None, max_length=64)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, sep, domain = value.partition("@")
        if not sep or not local or "." not in domain or any(c.isspace() for c in value):
            raise ValueError("邮箱格式不正确")
        return value


class EmailSendOut(BaseModel):
    cooldown_seconds: int


class EmailLoginIn(BaseModel):
    email: str = Field(max_length=200)
    code: str = Field(min_length=4, max_length=8)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class SessionOut(BaseModel):
    session_token: str
    expires_in: int
    next: str = "/"
    user: UserOut
