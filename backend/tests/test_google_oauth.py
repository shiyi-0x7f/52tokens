"""Google OAuth 工具函数：PKCE、授权链接、id_token 声明校验。"""

import base64
import hashlib
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.errors import AppError
from app.integrations import google_oauth
from tests.fakes import GOOGLE_CLIENT_ID, make_id_token

NOW = datetime.now(UTC)


def test_pkce_challenge_is_s256_of_verifier() -> None:
    verifier, challenge = google_oauth.pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert challenge == expected.decode()
    assert 43 <= len(verifier) <= 128


def test_authorize_url_carries_state_nonce_and_pkce() -> None:
    url = google_oauth.build_authorize_url(
        client_id="cid", redirect_uri="https://x/cb", state="s", code_challenge="c", nonce="n"
    )
    query = parse_qs(urlparse(url).query)
    assert query["state"] == ["s"]
    assert query["nonce"] == ["n"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid email profile"]


def test_parse_valid_token() -> None:
    identity = google_oauth.parse_id_token(
        make_id_token(nonce="n1"), client_id=GOOGLE_CLIENT_ID, nonce="n1", now=NOW
    )
    assert identity.sub == "google-sub-123"
    assert identity.email_verified is True


@pytest.mark.parametrize(
    ("claims", "error"),
    [
        ({"aud": "someone-else"}, "UPSTREAM_ERROR"),
        ({"iss": "https://evil.example.com"}, "UPSTREAM_ERROR"),
        ({"exp": 1}, "AUTH_STATE_INVALID"),
        ({"nonce": "other"}, "AUTH_STATE_INVALID"),
        ({"sub": ""}, "UPSTREAM_ERROR"),
    ],
)
def test_parse_rejects_bad_claims(claims: dict[str, object], error: str) -> None:
    token = make_id_token(**({"nonce": "n1"} | claims))
    with pytest.raises(AppError) as exc:
        google_oauth.parse_id_token(token, client_id=GOOGLE_CLIENT_ID, nonce="n1", now=NOW)
    assert exc.value.error.name == error


def test_unverified_email_is_reported_as_unverified() -> None:
    identity = google_oauth.parse_id_token(
        make_id_token(nonce="n", email_verified=False),
        client_id=GOOGLE_CLIENT_ID,
        nonce="n",
        now=NOW,
    )
    assert identity.email_verified is False
