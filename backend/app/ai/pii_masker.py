"""Deterministic, non-reversible PII masking for outbound model contexts.

Design spec 7.2 / SRS NFR-PRI-02/03: every field sent to a model — subject,
description, public-comment content — is masked first. Emails become [EMAIL-1],
[EMAIL-2], ... and phone numbers become [PHONE-1], [PHONE-2], ... in order of
appearance. Placeholders keep sentence structure for the model but are NOT
reversible (no mapping is retained). Pure string transform: offline, dependency-free.
"""

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Optional +84/84/0 prefix, then digits in groups — requires enough digits that
# short codes (TK-20260902, "năm 2024") are never matched.
_PHONE_RE = re.compile(r"(?:(?:\+?84|0)[\s.-]?)?\(?\d{3,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}")


def _mask(pattern: re.Pattern, text: str, token: str) -> str:
    seen: dict[str, int] = {}

    def _replace(match: re.Match) -> str:
        key = match.group(0)
        idx = seen.setdefault(key, len(seen) + 1)
        return f"[{token}-{idx}]"

    return pattern.sub(_replace, text)


def mask_text(raw: str) -> str:
    """Replace emails and phone numbers with numbered placeholders.

    Placeholders contain no '@' and no long digit groups, so masking is idempotent.
    """
    out = _mask(_EMAIL_RE, raw, "EMAIL")
    return _mask(_PHONE_RE, out, "PHONE")
