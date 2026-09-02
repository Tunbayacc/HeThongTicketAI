import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    # bcrypt only reads the first 72 bytes; raise early rather than silently truncate.
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("password longer than 72 bytes is not supported")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # base32, no 0/O/1/I


def generate_ticket_code() -> str:
    """Public, hard-to-guess ticket code: 'TK-' + 8 base32 chars (SRS BR-01)."""
    raw = secrets.token_bytes(8)
    n = int.from_bytes(raw, "big")
    chars: list[str] = []
    for _ in range(8):
        n, rem = divmod(n, 32)
        chars.append(_ALPHABET[rem])
    return "TK-" + "".join(chars)


def create_access_token(*, user_id: str, role: str) -> str:
    """Short-lived JWT (Settings.access_token_expire_minutes). Payload per SRS FR-AUTH-05.

    Each issuance carries a random `jti` (RFC 7519 4.1.7) so that every access
    token is unique even when minted within the same integer-second `iat` window.
    FR-AUTH-06 refresh therefore always returns a distinguishable fresh token,
    and the backend stays stateless (NFR-SCA-01) because jti is never validated
    against a store.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return pyjwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> str:
    """Random opaque refresh token (>=256 bits entropy); stored hashed (NFR-SEC-04)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
