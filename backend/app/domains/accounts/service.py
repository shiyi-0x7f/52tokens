"""登录编排：各登录方式 → SCC 统一身份 → 本地用户 → 52tokens 会话。

- Google：52tokens 自己完成 OAuth（SCC 在国内连不到 Google），再经 SCC 联合登录建号。
- 微信网站应用扫码、邮箱验证码：直接用 SCC 已有接口。
会话令牌只以 SHA-256 摘要作为存储键，泄露存储也拿不到可用令牌。
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.core.errors import AppError
from app.core.kv import KeyValueStore
from app.core.turnstile import verify_turnstile
from app.domains.accounts.repository import UserRepository
from app.domains.accounts.schemas import AuthorizeOut, EmailSendOut, SessionOut, UserOut
from app.integrations import google_oauth
from app.integrations.scc import SccClient, SccUser

STATE_TTL_SECONDS = 600


def _state_key(state: str) -> str:
    return f"oauth:google:{state}"


def _session_key(token: str) -> str:
    return f"session:{hashlib.sha256(token.encode()).hexdigest()}"


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: KeyValueStore,
        http: httpx.AsyncClient,
        users: UserRepository,
        scc: SccClient,
    ) -> None:
        self.settings = settings
        self.store = store
        self.http = http
        self.users = users
        self.scc = scc

    # ---------- 公共：SCC 用户 → 本地用户 → 会话 ----------

    async def _open_session(
        self, scc_user: SccUser, *, verified_email: str | None, next_path: str = "/"
    ) -> SessionOut:
        """verified_email 只在邮箱已被验证（Google 确认 / 收到验证码）时传入，用于判定管理员。"""
        now = datetime.now(UTC)
        is_admin = verified_email is not None and (
            verified_email.lower() in self.settings.admin_email_set
        )
        user = await self.users.upsert_from_scc(
            scc_user_id=scc_user.user_id,
            nickname=scc_user.nickname,
            email=scc_user.email,
            avatar_url=scc_user.avatar_url,
            auth_provider=scc_user.auth_provider,
            is_admin=is_admin,
            now=now,
        )
        token = secrets.token_urlsafe(32)
        ttl = self.settings.session_ttl_days * 86400
        await self.store.set(_session_key(token), str(user.id), ttl)
        return SessionOut(
            session_token=token,
            expires_in=ttl,
            next=next_path,
            user=UserOut.model_validate(user),
        )

    # ---------- Google ----------

    def _require_google(self) -> None:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise AppError("SERVICE_UNAVAILABLE", "Google 登录未配置")

    async def start_google(self, next_path: str) -> AuthorizeOut:
        self._require_google()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(16)
        verifier, challenge = google_oauth.pkce_pair()
        await self.store.set(
            _state_key(state),
            json.dumps({"verifier": verifier, "nonce": nonce, "next": next_path}),
            STATE_TTL_SECONDS,
        )
        url = google_oauth.build_authorize_url(
            client_id=self.settings.google_client_id,
            redirect_uri=self.settings.google_redirect_uri,
            state=state,
            code_challenge=challenge,
            nonce=nonce,
        )
        return AuthorizeOut(authorize_url=url, state=state)

    async def finish_google(self, code: str, state: str) -> SessionOut:
        self._require_google()
        raw = await self.store.pop(_state_key(state))  # state 只能用一次
        if raw is None:
            raise AppError("AUTH_STATE_INVALID")
        saved = json.loads(raw)

        id_token = await google_oauth.exchange_code(
            self.http,
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret.get_secret_value(),
            redirect_uri=self.settings.google_redirect_uri,
            code=code,
            code_verifier=saved["verifier"],
        )
        identity = google_oauth.parse_id_token(
            id_token,
            client_id=self.settings.google_client_id,
            nonce=saved["nonce"],
            now=datetime.now(UTC),
        )
        scc_user = await self.scc.federated_login(identity)
        verified = identity.email if identity.email_verified else None
        return await self._open_session(scc_user, verified_email=verified, next_path=saved["next"])

    # ---------- 微信网站应用扫码（经 SCC） ----------

    async def start_wechat(self) -> AuthorizeOut:
        url, state = await self.scc.wechat_web_url()
        return AuthorizeOut(authorize_url=url, state=state)

    async def finish_wechat(self, code: str, state: str) -> SessionOut:
        scc_user = await self.scc.wechat_web_login(code, state)
        # 微信不提供已验证邮箱，不参与管理员判定
        return await self._open_session(scc_user, verified_email=None)

    # ---------- 邮箱验证码（经 SCC） ----------

    async def send_email_code(
        self, email: str, *, turnstile_token: str | None, remote_ip: str | None
    ) -> EmailSendOut:
        # 先过人机验证，防止被用来批量发邮件
        await verify_turnstile(
            self.http,
            secret=self.settings.turnstile_secret_key.get_secret_value(),
            token=turnstile_token,
            remote_ip=remote_ip,
        )
        return EmailSendOut(cooldown_seconds=await self.scc.email_send_code(email))

    async def finish_email(self, email: str, code: str) -> SessionOut:
        scc_user = await self.scc.email_login(email, code)
        # 能收到验证码即证明邮箱归属
        return await self._open_session(scc_user, verified_email=email)

    # ---------- 会话 ----------

    async def get_session_user(self, token: str) -> UserOut:
        user_id = await self.store.get(_session_key(token))
        if user_id is None:
            raise AppError("UNAUTHORIZED")
        user = await self.users.get(int(user_id))
        if user is None:
            await self.store.delete(_session_key(token))
            raise AppError("UNAUTHORIZED")
        return UserOut.model_validate(user)

    async def logout(self, token: str) -> None:
        await self.store.delete(_session_key(token))
