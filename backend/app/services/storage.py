"""Server-side storage for ticket attachments (SRS file rules; design spec 8).

Only validated bytes reach disk. A file is streamed in chunks, counted against
max_bytes, stored under a server-generated UUID name (never the user's filename),
and returned as a StoredFile carrying the metadata the Attachment row needs. The
router/service owns the DB row; this module owns the bytes.
"""

import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.errors import AppError
from app.services.file_rules import extension_allowed, within_size

_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    stored_name: str
    storage_path: str  # forward-slash path (portable host <-> container bind mount)
    original_name: str
    mime_type: str
    size_bytes: int


def _mime_for(filename: str, declared: str | None) -> str:
    if declared and "/" in declared:
        return declared
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


async def store_upload(
    upload: UploadFile, *, upload_dir: Path, allowed: set[str], max_bytes: int
) -> StoredFile:
    """Validate + stream one upload to disk under a fresh UUID name.

    Raises 415 FILE_TYPE_NOT_ALLOWED or 413 FILE_TOO_LARGE (SRS 10.2 codes).
    """
    original = upload.filename or "file"
    if not extension_allowed(original, allowed):
        raise AppError(415, "FILE_TYPE_NOT_ALLOWED", "Loại tệp không được phép tải lên.")
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = PurePosixPath(original).suffix.lower()
    stored_name = uuid.uuid4().hex + ext
    # Forward-slash storage_path so a row written in the host venv resolves the
    # same under the Linux container's bind mount of ./backend.
    storage_path = (PurePosixPath(upload_dir.as_posix()) / stored_name).as_posix()
    target = Path(storage_path)
    size = 0
    try:
        with target.open("wb") as fh:
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                if not within_size(size, max_bytes):
                    raise AppError(413, "FILE_TOO_LARGE", "Tệp vượt quá kích thước tối đa cho phép.")
                fh.write(chunk)
    except AppError:
        target.unlink(missing_ok=True)
        raise
    return StoredFile(
        stored_name=stored_name,
        storage_path=storage_path,
        original_name=original,
        mime_type=_mime_for(original, upload.content_type),
        size_bytes=size,
    )


def resolve_upload(storage_path: str) -> Path:
    p = Path(storage_path)
    return p if p.is_absolute() else Path.cwd() / p


def remove_stored(storage_path: str) -> None:
    resolve_upload(storage_path).unlink(missing_ok=True)


async def store_many(
    uploads, *, upload_dir: Path, allowed: set[str], max_bytes: int, max_files: int
) -> list[StoredFile]:
    """Validate the whole batch up front, then store each file.

    The count limit is checked BEFORE anything is written (SRS file rule '<= 5 tệp
    mỗi yêu cầu' -> 422 VALIDATION_ERROR). If any single file is rejected mid-way,
    the files already written are removed so a failed request never leaks bytes.
    """
    if uploads is None:
        return []
    if len(uploads) > max_files:
        raise AppError(422, "VALIDATION_ERROR", f"Mỗi yêu cầu tối đa {max_files} tệp đính kèm.")
    stored: list[StoredFile] = []
    try:
        for up in uploads:
            stored.append(await store_upload(up, upload_dir=upload_dir, allowed=allowed, max_bytes=max_bytes))
    except Exception:
        for sf in stored:
            remove_stored(sf.storage_path)
        raise
    return stored
