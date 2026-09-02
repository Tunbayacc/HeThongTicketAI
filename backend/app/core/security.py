import base64
import os
import secrets

import bcrypt


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
