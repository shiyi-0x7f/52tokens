"""测试替身：内存键值存储、伪造的 Google id_token、Google / SCC 模拟服务。"""

import base64
import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx

GOOGLE_CLIENT_ID = "test-client.apps.googleusercontent.com"
SCC_BASE = "https://scc.test"


class MemoryStore:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def pop(self, key: str) -> str | None:
        return self.data.pop(key, None)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)


def make_id_token(**claims: Any) -> str:
    def enc(obj: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    payload = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_CLIENT_ID,
        "exp": int(time.time()) + 3600,
        "sub": "google-sub-123",
        "email": "alice@gmail.com",
        "email_verified": True,
        "name": "Alice",
        "picture": "https://lh3.googleusercontent.com/a/x",
    } | claims
    return f"{enc({'alg': 'RS256'})}.{enc(payload)}.signature"


class FakeUpstreams:
    """同时模拟 Google token 接口和 SCC；记录调用次数，可注入各种响应。"""

    def __init__(self) -> None:
        self.nonce = ""
        self.id_token_claims: dict[str, Any] = {}
        self.google_status = 200
        self.scc_login_responses: list[httpx.Response] = []
        # 微信 / 邮箱接口的注入响应：没有注入时返回成功
        self.responses: dict[str, list[httpx.Response]] = {}
        self.turnstile_success = True
        self.calls: dict[str, int] = {"google_token": 0, "scc_token": 0, "scc_login": 0}
        self.last_login_body: dict[str, Any] = {}
        self.last_bodies: dict[str, dict[str, Any]] = {}

    def _next(self, name: str, default: httpx.Response) -> httpx.Response:
        self.calls[name] = self.calls.get(name, 0) + 1
        queued = self.responses.get(name)
        return queued.pop(0) if queued else default

    def scc_user(self, user_id: int = 42, **kw: Any) -> httpx.Response:
        body = {
            "user_id": user_id,
            "nickname": "Alice",
            "email": "alice@gmail.com",
            "avatar_url": None,
            "auth_provider": "google",
            "token": "scc-client-token",
        } | kw
        return httpx.Response(200, json=body)

    def handler(self) -> Callable[[httpx.Request], httpx.Response]:
        def handle(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url == "https://oauth2.googleapis.com/token":
                self.calls["google_token"] += 1
                form = parse_qs(request.content.decode())
                assert form["code_verifier"], "必须携带 PKCE verifier"
                if self.google_status != 200:
                    return httpx.Response(self.google_status, json={"error": "invalid_grant"})
                token = make_id_token(nonce=self.nonce, **self.id_token_claims)
                return httpx.Response(200, json={"id_token": token})
            if url == f"{SCC_BASE}/api/v1/apps/token":
                self.calls["scc_token"] += 1
                return httpx.Response(
                    200,
                    json={
                        "access_token": f"app-token-{self.calls['scc_token']}",
                        "refresh_token": "r",
                        "token_type": "Bearer",
                        "expires_in": 900,
                    },
                )
            if url == f"{SCC_BASE}/api/v1/client/auth/federated/login":
                self.calls["scc_login"] += 1
                self.last_login_body = json.loads(request.content)
                if self.scc_login_responses:
                    return self.scc_login_responses.pop(0)
                return self.scc_user()
            path = request.url.path
            if path == "/api/v1/client/auth/wechat-web/url":
                assert request.url.params["app_id"] == "7"
                return self._next(
                    "wechat_url",
                    httpx.Response(
                        200,
                        json={
                            "authorize_url": "https://open.weixin.qq.com/connect/qrconnect?x=1",
                            "state": "wx-state-1",
                        },
                    ),
                )
            if path == "/api/v1/client/auth/wechat-web/login":
                self.last_bodies["wechat_login"] = json.loads(request.content)
                default = self.scc_user(user_id=77, email=None, auth_provider="wechat")
                return self._next("wechat_login", default)
            if path == "/api/v1/client/auth/email/send-code":
                self.last_bodies["email_send"] = json.loads(request.content)
                return self._next("email_send", httpx.Response(200, json={"cooldown_seconds": 60}))
            if path == "/api/v1/client/auth/email/login":
                self.last_bodies["email_login"] = json.loads(request.content)
                body = json.loads(request.content)
                default = self.scc_user(user_id=88, email=body["email"], auth_provider="local")
                return self._next("email_login", default)
            if url == "https://challenges.cloudflare.com/turnstile/v0/siteverify":
                self.calls["turnstile"] = self.calls.get("turnstile", 0) + 1
                return httpx.Response(200, json={"success": self.turnstile_success})
            raise AssertionError(f"未预期的请求 {url}")

        return handle

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler()))
