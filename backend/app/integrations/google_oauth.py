"""Google OAuth 2.0 / OpenID Connect（授权码 + PKCE）。"""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from loguru import logger

from app.core.errors import AppError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - 接口地址，不是密码
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    sub: str
    email: str | None
    email_verified: bool
    name: str | None
    picture: str | None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_pair() -> tuple[str, str]:
    """返回 (code_verifier, code_challenge)，S256。"""
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str, code_challenge: str, nonce: str
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(
    client: httpx.AsyncClient,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> str:
    """用授权码换 id_token。"""
    try:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Google token 接口不可达: {}", exc)
        raise AppError("UPSTREAM_ERROR") from exc
    if resp.status_code == 400:
        # 授权码过期 / 重复使用：让用户重新登录
        logger.info("Google 拒绝授权码: {}", resp.text[:200])
        raise AppError("AUTH_STATE_INVALID")
    if resp.status_code != 200:
        logger.warning("Google token 接口异常 status={}", resp.status_code)
        raise AppError("UPSTREAM_ERROR")
    id_token = resp.json().get("id_token")
    if not isinstance(id_token, str):
        raise AppError("UPSTREAM_ERROR", "Google 未返回 id_token")
    return id_token


def _decode_payload(id_token: str) -> dict[str, Any]:
    try:
        payload_b64 = id_token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError) as exc:
        raise AppError("UPSTREAM_ERROR", "id_token 格式错误") from exc
    if not isinstance(payload, dict):
        raise AppError("UPSTREAM_ERROR", "id_token 格式错误")
    return payload


def parse_id_token(id_token: str, *, client_id: str, nonce: str, now: datetime) -> GoogleIdentity:
    """校验 id_token 的声明并取出身份。

    id_token 是后端直接经 HTTPS 从 Google token 接口取得的，按 OpenID Connect Core
    3.1.3.7 第 6 条，可用 TLS 服务端校验代替签名校验；iss / aud / exp / nonce 仍逐项校验。
    """
    claims = _decode_payload(id_token)
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise AppError("UPSTREAM_ERROR", "id_token 签发方不符")
    if claims.get("aud") != client_id:
        raise AppError("UPSTREAM_ERROR", "id_token 受众不符")
    exp = claims.get("exp")
    if not isinstance(exp, int | float) or exp <= now.timestamp():
        raise AppError("AUTH_STATE_INVALID")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise AppError("AUTH_STATE_INVALID")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AppError("UPSTREAM_ERROR", "id_token 缺少 sub")
    email = claims.get("email")
    return GoogleIdentity(
        sub=sub,
        email=email if isinstance(email, str) else None,
        email_verified=claims.get("email_verified") is True,
        name=claims.get("name") if isinstance(claims.get("name"), str) else None,
        picture=claims.get("picture") if isinstance(claims.get("picture"), str) else None,
    )
