import time
import uuid

import jwt as pyjwt
import pytest

from app.core import security
from app.core.config import Settings


def _settings():
    return Settings(_env_file=None)  # never read backend/.env during tests


def test_create_and_decode_access_token(monkeypatch):
    monkeypatch.setattr(security, "get_settings", _settings)
    user_id = uuid.uuid4()
    token = security.create_access_token(user_id=str(user_id), role="MANAGER")
    payload = security.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "MANAGER"
    assert payload["exp"] > int(time.time())


def test_expired_token_raises_expired_error(monkeypatch):
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: Settings(_env_file=None, access_token_expire_minutes=0),
    )
    token = security.create_access_token(user_id=str(uuid.uuid4()), role="AGENT")
    with pytest.raises(pyjwt.ExpiredSignatureError):
        security.decode_access_token(token)


def test_tampered_token_rejected(monkeypatch):
    monkeypatch.setattr(security, "get_settings", _settings)
    token = security.create_access_token(user_id=str(uuid.uuid4()), role="AGENT")
    tampered = (token[:-2] + "AA") if token[-2:] != "AA" else (token[:-2] + "BB")
    with pytest.raises(pyjwt.InvalidTokenError):
        security.decode_access_token(tampered)


def test_refresh_token_generate_and_hash():
    rt = security.generate_refresh_token()
    assert len(rt) >= 43  # token_urlsafe(32) base64url, no padding
    assert security.hash_refresh_token(rt) == security.hash_refresh_token(rt)
    assert security.hash_refresh_token(rt) != rt
