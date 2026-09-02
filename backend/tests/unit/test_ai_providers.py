"""Provider protocol, MockProvider determinism/failure knobs, Gemini payload/parse
helpers. No network is exercised (Gemini helpers are pure; httpx MockTransport
stands in for the Gemini REST endpoint)."""

import asyncio
import json

import httpx
import pytest

import app.ai.providers as ai_providers
from app.ai.providers import (
    GeminiProvider,
    MockProvider,
    ProviderError,
    build_generate_payload,
    parse_content_text,
)
from app.ai.schemas import OUTPUT_SCHEMAS

_REAL_ASYNC_CLIENT = httpx.AsyncClient


class _MockedAsyncClient:
    """Callable stand-in for httpx.AsyncClient that routes requests through a
    MockTransport. GeminiProvider builds its own AsyncClient internally, so tests
    monkeypatch the class onto the httpx module to inject a transport."""

    def __init__(self, handler):
        self._handler = handler

    def __call__(self, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(self._handler), **kwargs)


def _patch_client(monkeypatch, handler) -> None:
    monkeypatch.setattr(ai_providers.httpx, "AsyncClient", _MockedAsyncClient(handler))


def _make_gemini(monkeypatch, handler, *, model: str = "gemini-2.0-flash") -> GeminiProvider:
    _patch_client(monkeypatch, handler)
    return GeminiProvider(api_key="test-key", model=model, timeout_seconds=5)


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


def test_gemini_probe_hits_plain_models_url_not_colon_suffix(monkeypatch):
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={})

    p = _make_gemini(monkeypatch, handler)
    assert asyncio.run(p.probe()) is True
    url = captured["url"]
    # probe() must GET the plain model-metadata resource — no ':model' colon method.
    assert url.split("?")[0] == \
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash"
    assert ":model" not in url


def test_gemini_generate_200_empty_candidates_raises_invalid_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    p = _make_gemini(monkeypatch, handler)
    with pytest.raises(ProviderError) as exc:
        asyncio.run(p.generate(result_type="CLASSIFICATION", system_prompt="s", user_prompt="u"))
    assert exc.value.code == "AI_INVALID_RESPONSE"


def test_gemini_generate_200_malformed_text_raises_invalid_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="không phải json")

    p = _make_gemini(monkeypatch, handler)
    with pytest.raises(ProviderError) as exc:
        asyncio.run(p.generate(result_type="CLASSIFICATION", system_prompt="s", user_prompt="u"))
    assert exc.value.code == "AI_INVALID_RESPONSE"
