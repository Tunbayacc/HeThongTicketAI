"""Provider protocol, MockProvider determinism/failure knobs, Gemini payload/parse
helpers. No network is exercised (Gemini helpers are pure)."""

import asyncio
import json

import pytest

from app.ai.providers import (
    MockProvider,
    ProviderError,
    build_generate_payload,
    parse_content_text,
)
from app.ai.schemas import OUTPUT_SCHEMAS


def test_mock_classification_parses_to_valid_schema():
    p = MockProvider()
    text = asyncio.run(p.generate(result_type="CLASSIFICATION",
                                  system_prompt="s", user_prompt="lỗi đăng nhập mật khẩu"))
    OUTPUT_SCHEMAS["CLASSIFICATION"].model_validate(json.loads(text))


def test_mock_summary_and_draft_are_valid_shapes():
    p = MockProvider()
    for rt in ("SUMMARY", "DRAFT_REPLY"):
        text = asyncio.run(p.generate(result_type=rt, system_prompt="s", user_prompt="bối cảnh vé"))
        OUTPUT_SCHEMAS[rt].model_validate(json.loads(text))


def test_mock_invalid_mode_returns_non_json():
    p = MockProvider(fail_mode="invalid")
    out = asyncio.run(p.generate(result_type="CLASSIFICATION", system_prompt="s", user_prompt="x"))
    assert "không phải JSON" in out


def test_mock_timeout_mode_raises_provider_error():
    p = MockProvider(fail_mode="timeout")
    with pytest.raises(ProviderError) as exc:
        asyncio.run(p.generate(result_type="CLASSIFICATION", system_prompt="s", user_prompt="x"))
    assert exc.value.code == "AI_TIMEOUT"


def test_mock_probe_is_ok():
    assert asyncio.run(MockProvider().probe()) is True


def test_build_generate_payload_is_json_mode():
    payload = build_generate_payload(system_prompt="s", user_prompt="u")
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["contents"][0]["parts"][1]["text"] == "u"


def test_parse_content_text_extracts_candidate_text():
    raw = json.dumps({"candidates": [{"content": {"parts": [
        {"text": '{"category": "ACCOUNT"}, '}, {"text": '"ignored"'},
    ]}}]})
    assert parse_content_text(raw).startswith('{"category"')


def test_parse_content_text_raises_on_malformed():
    with pytest.raises((ValueError, KeyError, IndexError)):
        parse_content_text("không phải json")
