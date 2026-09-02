"""Upload allowlist + size rules (SRS TBD-05/FR-PUB, SRS 10.1; design spec 8)."""

from pathlib import PurePosixPath


def parse_allowed_extensions(allowed_csv: str) -> set[str]:
    """'pdf,png,jpg,jpeg,txt,docx' -> {'pdf','png',...} (lowercased, trimmed)."""
    return {ext.strip().lower() for ext in allowed_csv.split(",") if ext.strip()}


def extension_allowed(filename: str, allowed: set[str]) -> bool:
    ext = PurePosixPath(filename).suffix.lower().lstrip(".")
    return ext in allowed and ext != ""


def within_size(size_bytes: int, max_bytes: int) -> bool:
    return size_bytes <= max_bytes
