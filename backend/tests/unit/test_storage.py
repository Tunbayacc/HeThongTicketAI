from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from app.core.errors import AppError
from app.services.file_rules import parse_allowed_extensions
from app.services.storage import resolve_upload, store_upload

ALLOWED = parse_allowed_extensions("pdf,png,jpg,jpeg,txt,docx")


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(BytesIO(content), filename=name)


async def test_store_upload_writes_file_and_returns_metadata(tmp_path):
    stored = await store_upload(_upload("bao-cao.pdf", b"%PDF-1.4 hello"), upload_dir=tmp_path, allowed=ALLOWED, max_bytes=100)
    assert stored.original_name == "bao-cao.pdf"
    assert stored.size_bytes == 14  # len(b"%PDF-1.4 hello") == 14
    assert stored.stored_name.endswith(".pdf")
    # server-generated name, never the user's filename
    assert stored.stored_name != "bao-cao.pdf"
    assert stored.storage_path.endswith(stored.stored_name)
    path = resolve_upload(stored.storage_path)
    assert path.read_bytes() == b"%PDF-1.4 hello"


async def test_store_upload_rejects_disallowed_type_and_writes_nothing(tmp_path):
    with pytest.raises(AppError) as exc:
        await store_upload(_upload("virus.exe", b"MZ"), upload_dir=tmp_path, allowed=ALLOWED, max_bytes=100)
    assert exc.value.status_code == 415
    assert exc.value.error_code == "FILE_TYPE_NOT_ALLOWED"
    assert list(tmp_path.iterdir()) == []


async def test_store_upload_rejects_oversized_and_removes_partial_file(tmp_path):
    with pytest.raises(AppError) as exc:
        await store_upload(_upload("big.txt", b"1234567890"), upload_dir=tmp_path, allowed=ALLOWED, max_bytes=4)
    assert exc.value.status_code == 413
    assert exc.value.error_code == "FILE_TOO_LARGE"
    assert list(tmp_path.iterdir()) == []
