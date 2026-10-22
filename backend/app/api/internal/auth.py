"""登录与会话（公开站服务端专用）。浏览器只和公开站交互，会话令牌放在 httpOnly Cookie 里。"""

from typing import Annotated

from fastapi import APIRouter, Header

from app.api.deps import AuthServiceDep
from app.core.errors import AppError
from app.core.response import ApiResponse, ok
from app.domains.accounts.schemas import (
    AuthorizeOut,
    EmailLoginIn,
    EmailSendIn,
    EmailSendOut,
    GoogleStartIn,
    OAuthCallbackIn,
    SessionOut,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["internal:auth"])

SessionHeader = Annotated[str | None, Header(alias="X-Session-Token", max_length=200)]


def _require(token: str | None) -> str:
    if not token:
        raise AppError("UNAUTHORIZED")
    return token


@router.post("/google/start")
async def google_start(body: GoogleStartIn, service: AuthServiceDep) -> ApiResponse[AuthorizeOut]:
    return ok(await service.start_google(body.next))


@router.post("/google/callback")
async def google_callback(
    body: OAuthCallbackIn, service: AuthServiceDep
) -> ApiResponse[SessionOut]:
    return ok(await service.finish_google(body.code, body.state))


@router.post("/wechat/start")
async def wechat_start(service: AuthServiceDep) -> ApiResponse[AuthorizeOut]:
    return ok(await service.start_wechat())


@router.post("/wechat/callback")
async def wechat_callback(
    body: OAuthCallbackIn, service: AuthServiceDep
) -> ApiResponse[SessionOut]:
    return ok(await service.finish_wechat(body.code, body.state))


@router.post("/email/send")
async def email_send(body: EmailSendIn, service: AuthServiceDep) -> ApiResponse[EmailSendOut]:
    return ok(
        await service.send_email_code(
            body.email, turnstile_token=body.turnstile_token, remote_ip=body.remote_ip
        )
    )


@router.post("/email/login")
async def email_login(body: EmailLoginIn, service: AuthServiceDep) -> ApiResponse[SessionOut]:
    return ok(await service.finish_email(body.email, body.code))


@router.get("/session")
async def get_session(service: AuthServiceDep, token: SessionHeader = None) -> ApiResponse[UserOut]:
    return ok(await service.get_session_user(_require(token)))


@router.delete("/session")
async def delete_session(service: AuthServiceDep, token: SessionHeader = None) -> ApiResponse[None]:
    await service.logout(_require(token))
    return ok(None)
