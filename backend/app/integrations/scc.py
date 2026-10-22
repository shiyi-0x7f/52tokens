"""SCC 统一身份客户端：Google 联合登录、微信网站应用扫码、邮箱验证码。

契约见 dev_docs/refs/software_control_center.md。SCC 的错误响应是 FastAPI 默认的
{"detail": "..."}，这里统一映射成 52tokens 的业务码。
"""

from dataclasses import dataclass
from typing import Any, NoReturn

import httpx
from loguru import logger

from app.core.errors import AppError
from app.core.kv import KeyValueStore
from app.integrations.google_oauth import GoogleIdentity

APP_TOKEN_KEY = "scc:app_token"  # noqa: S105 - 缓存键名，不是密码


@dataclass(frozen=True, slots=True)
class SccUser:
    user_id: int
    nickname: str
    email: str | None
    avatar_url: str | None
    auth_provider: str


def _user(body: dict[str, Any]) -> SccUser:
    return SccUser(
        user_id=int(body["user_id"]),
        nickname=str(body["nickname"]),
        email=body.get("email"),
        avatar_url=body.get("avatar_url"),
        auth_provider=str(body.get("auth_provider", "local")),
    )


def _detail(resp: httpx.Response) -> str | None:
    if not resp.headers.get("content-type", "").startswith("application/json"):
        return None
    detail = resp.json().get("detail")
    return detail if isinstance(detail, str) else None


class SccClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        store: KeyValueStore,
        *,
        base_url: str,
        app_id: int | None,
        app_secret: str,
    ) -> None:
        self.http = http
        self.store = store
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret

    def _require_app_id(self) -> int:
        if self.app_id is None:
            logger.error("SCC_APP_ID 未配置")
            raise AppError("SERVICE_UNAVAILABLE", "登录服务未配置")
        return self.app_id

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        params: dict[str, str | int] | None = None,
        token: str | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            return await self.http.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                params=params,
                headers=headers,
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("SCC 不可达 {}: {}", path, exc)
            raise AppError("UPSTREAM_ERROR", "登录服务暂不可用") from exc

    def _raise_common(self, resp: httpx.Response, path: str) -> NoReturn:
        """各接口共有的错误：限流、SCC 上游故障、未配置。"""
        detail = _detail(resp)
        logger.warning("SCC 调用失败 {} status={} detail={}", path, resp.status_code, detail)
        if resp.status_code == 429:
            raise AppError("RATE_LIMITED", detail)
        if resp.status_code == 503:
            raise AppError("SERVICE_UNAVAILABLE", "登录服务暂不可用")
        raise AppError("UPSTREAM_ERROR", "登录服务暂不可用")

    # ---------- app token（Google 联合登录用） ----------

    async def _app_token(self, *, refresh: bool = False) -> str:
        if not refresh and (cached := await self.store.get(APP_TOKEN_KEY)):
            return cached
        app_id = self._require_app_id()
        if not self.app_secret:
            logger.error("SCC_APP_SECRET 未配置")
            raise AppError("SERVICE_UNAVAILABLE", "登录服务未配置")
        resp = await self._request(
            "POST", "/api/v1/apps/token", json={"app_id": app_id, "secret": self.app_secret}
        )
        if resp.status_code != 200:
            logger.error("SCC 换取 app token 失败 status={}", resp.status_code)
            raise AppError("UPSTREAM_ERROR", "登录服务暂不可用")
        body = resp.json()
        token: str = body["access_token"]
        # 提前 60 秒过期，避免临界时刻用到失效 token
        await self.store.set(APP_TOKEN_KEY, token, max(int(body["expires_in"]) - 60, 1))
        return token

    # ---------- Google 联合登录 ----------

    async def federated_login(self, identity: GoogleIdentity) -> SccUser:
        payload: dict[str, object] = {
            "provider": "google",
            "subject": identity.sub,
            "email": identity.email,
            "email_verified": identity.email_verified,
            "nickname": identity.name,
            "avatar_url": identity.picture,
        }
        path = "/api/v1/client/auth/federated/login"
        resp = await self._request("POST", path, json=payload, token=await self._app_token())
        if resp.status_code == 401:
            # 缓存的 app token 可能已被吊销 / 过期：刷新一次再试
            token = await self._app_token(refresh=True)
            resp = await self._request("POST", path, json=payload, token=token)
        if resp.status_code == 200:
            return _user(resp.json())
        if resp.status_code == 403:
            raise AppError("FORBIDDEN", "账号已被禁用")
        if resp.status_code == 409:
            raise AppError("CONFLICT", "该邮箱已关联其他 Google 账号")
        self._raise_common(resp, path)

    # ---------- 微信网站应用扫码 ----------

    async def wechat_web_url(self) -> tuple[str, str]:
        """返回 (authorize_url, state)。state 由 SCC 生成并绑定 app_id。"""
        path = "/api/v1/client/auth/wechat-web/url"
        resp = await self._request("GET", path, params={"app_id": self._require_app_id()})
        if resp.status_code == 200:
            body = resp.json()
            return str(body["authorize_url"]), str(body["state"])
        self._raise_common(resp, path)

    async def wechat_web_login(self, code: str, state: str) -> SccUser:
        path = "/api/v1/client/auth/wechat-web/login"
        body = {"app_id": self._require_app_id(), "code": code, "state": state}
        resp = await self._request("POST", path, json=body)
        if resp.status_code == 200:
            return _user(resp.json())
        if resp.status_code == 400:
            # state 过期 / 不符、授权码失效：让用户重新扫码
            logger.info("SCC 微信登录 400: {}", _detail(resp))
            raise AppError("AUTH_STATE_INVALID")
        self._raise_common(resp, path)

    # ---------- 邮箱验证码 ----------

    async def email_send_code(self, email: str) -> int:
        """发送登录验证码，返回冷却秒数。冷却 / 每日上限由 SCC 控制（超限 429）。"""
        path = "/api/v1/client/auth/email/send-code"
        body = {"app_id": self._require_app_id(), "email": email, "purpose": "login"}
        resp = await self._request("POST", path, json=body)
        if resp.status_code == 200:
            return int(resp.json().get("cooldown_seconds", 60))
        if resp.status_code in (400, 422):
            raise AppError("BAD_REQUEST", "邮箱地址无效")
        if resp.status_code == 502 and _detail(resp) is not None:
            # SCC 自己的业务错误（SMTP 未配置 / 发信失败），区别于网关层的 502
            logger.error("SCC 发送验证码邮件失败: {}", _detail(resp))
            raise AppError("EMAIL_SEND_FAILED")
        self._raise_common(resp, path)

    async def email_login(self, email: str, code: str) -> SccUser:
        path = "/api/v1/client/auth/email/login"
        body = {"app_id": self._require_app_id(), "email": email, "code": code}
        resp = await self._request("POST", path, json=body)
        if resp.status_code == 200:
            return _user(resp.json())
        if resp.status_code in (400, 422):
            raise AppError("AUTH_CODE_INVALID", _detail(resp))
        self._raise_common(resp, path)
