import pytest
from app.core.sanitizer import sanitize_text


def test_sanitize_text_none_or_empty():
    assert sanitize_text(None) is None
    assert sanitize_text("") == ""
    assert sanitize_text("   ") == "   "


def test_sanitize_text_preserves_plain_text_and_vietnamese():
    text = "Xin chào, tôi cần hỗ trợ về vé TK-ABC12345. Lỗi kết nối máy chủ!"
    assert sanitize_text(text) == text


def test_sanitize_text_strips_script_tags():
    malicious = "Hello <script>alert('XSS')</script> World!"
    cleaned = sanitize_text(malicious)
    assert "<script" not in cleaned.lower()
    assert "alert('xss')" not in cleaned.lower()
    assert "Hello" in cleaned
    assert "World!" in cleaned


def test_sanitize_text_removes_dangerous_tags():
    tags = [
        "<img src='x' onerror='alert(1)'>",
        "<svg/onload=alert(1)>",
        "<iframe src='javascript:alert(1)'></iframe>",
        "<style>body {display:none}</style>",
    ]
    for tag in tags:
        cleaned = sanitize_text(f"Text before {tag} text after")
        assert "<img" not in cleaned.lower()
        assert "<svg" not in cleaned.lower()
        assert "<iframe" not in cleaned.lower()
        assert "<style" not in cleaned.lower()
        assert "onerror" not in cleaned.lower()
        assert "onload" not in cleaned.lower()
        assert "Text before" in cleaned
        assert "text after" in cleaned


def test_sanitize_text_escapes_or_strips_angle_brackets():
    # Plain text containing stray brackets or comparisons
    text = "Giá trị a < b và c > d"
    cleaned = sanitize_text(text)
    assert "Giá trị a" in cleaned
    assert "và c" in cleaned
