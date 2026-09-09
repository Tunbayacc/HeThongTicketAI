"""Input text sanitizer for defense-in-depth against XSS and HTML injection (NFR-SEC-08, AC-SEC-03).

Frontend already renders all text safely through React JSX text nodes (which escapes by default).
This utility provides backend defense-in-depth before persistence in database.
"""

import re

# Block tags with their internal content (e.g. <script>alert(1)</script> -> remove completely)
_DANGEROUS_BLOCKS = re.compile(
    r"<\s*(script|style|iframe|object|embed|applet)[\s\S]*?<\s*/\s*\1\s*>",
    re.IGNORECASE,
)

# Unclosed dangerous tags up to the next closing bracket
_DANGEROUS_SINGLE = re.compile(
    r"<\s*(?:script|style|iframe|object|embed|applet|svg|img|link|meta)[^>]*>",
    re.IGNORECASE,
)

# Any remaining html tags starting with <tag or </tag
_HTML_TAGS = re.compile(r"</?[a-zA-Z][a-zA-Z0-9:-]*(?:\s+[^>]*)?/?>", re.IGNORECASE)

# Dangerous inline event handlers like onerror=, onload=, onclick=
_EVENT_HANDLERS = re.compile(r"\bon[a-zA-Z]+\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s>]+)", re.IGNORECASE)

# javascript: protocol
_JS_PROTOCOL = re.compile(r"javascript\s*:[^\s'\"]*", re.IGNORECASE)


def sanitize_text(text: str | None) -> str | None:
    """Sanitizes user input text by stripping dangerous executable tags,

    event handlers, and HTML tags, returning clean text.
    Preserves legitimate text, unicode/Vietnamese accents, and comparisons like 'a < b'.
    """
    if text is None:
        return None
    if not text:
        return text

    # 1. Remove dangerous blocks completely (content inside <script>...</script> etc.)
    cleaned = _DANGEROUS_BLOCKS.sub("", text)

    # 2. Remove dangerous single/unclosed tags (svg, img, etc.)
    cleaned = _DANGEROUS_SINGLE.sub("", cleaned)

    # 3. Strip any remaining HTML tags
    cleaned = _HTML_TAGS.sub("", cleaned)

    # 4. Strip any stray event handlers and javascript: schemes
    cleaned = _EVENT_HANDLERS.sub("", cleaned)
    cleaned = _JS_PROTOCOL.sub("", cleaned)

    return cleaned
