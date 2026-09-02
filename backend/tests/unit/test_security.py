import bcrypt

from app.core.security import generate_ticket_code, hash_password, verify_password


def test_hash_and_verify_roundtrip():
    hashed = hash_password("S3cret!pw")
    assert hashed.startswith("$2b$")
    assert verify_password("S3cret!pw", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_generate_ticket_code_shape():
    code = generate_ticket_code()
    assert code.startswith("TK-")
    assert len(code) == 11  # "TK-" + 8 chars
    assert code[3:].isalnum()
    assert code == code.upper()
