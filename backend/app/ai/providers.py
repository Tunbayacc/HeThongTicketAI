"""AI providers behind one interface (design spec 7.1, SRS NFR-SCA-05).

GeminiProvider speaks the Google Gemini REST generateContent API over httpx (an
existing runtime dependency); MockProvider returns deterministic JSON so the whole
S4 flow runs offline in tests and the demo. A provider returns RAW TEXT — the AI
service JSON-parses and schema-validates it, so 'structurally invalid' handling
lives in exactly one place.

Failures surface as ProviderError with a sanitized error_code; the AI service maps
code -> HTTP status and persists a FAILED ai_results row.
"""

import asyncio
import json
import os

import httpx

from app.core.config import get_settings


class ProviderError(Exception):
    """Transport/provider-level failure carrying a sanitized error_code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AIProvider:
    """Base class / structural interface. Providers only return raw text."""

    model_name: str = "ai"

    async def generate(self, *, result_type: str, system_prompt: str, user_prompt: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    async def probe(self) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError


# ---- Mock ---------------------------------------------------------------------


def _mock_classification(user_prompt: str) -> dict:
    text = user_prompt.lower()
    if any(k in text for k in ("mật khẩu", "đăng nhập", "khóa", "tài khoản", "otp", "account")):
        return {"category": "ACCOUNT", "priority": "HIGH", "confidence": 0.87,
                "reason": "Vé liên quan tới tài khoản / đăng nhập."}
    if any(k in text for k in ("thanh toán", "hóa đơn", "tiền", "phí", "hoàn tiền", "billing")):
        return {"category": "BILLING", "priority": "HIGH", "confidence": 0.85,
                "reason": "Vé liên quan tới thanh toán / hóa đơn."}
    if any(k in text for k in ("lỗi", "cài đặt", "không chạy", "báo lỗi", "máy", "phần mềm")):
        return {"category": "TECHNICAL", "priority": "MEDIUM", "confidence": 0.8,
                "reason": "Vé liên quan tới sự cố kỹ thuật."}
    return {"category": "GENERAL", "priority": "MEDIUM", "confidence": 0.72,
            "reason": "Không nhận diện được nhóm rõ ràng; mặc định chung."}


def _mock_summary() -> dict:
    return {
        "problem": "Khách gặp sự cố khi sử dụng dịch vụ.",
        "key_points": ["Đã liên hệ qua cổng hỗ trợ", "Nhân viên đang xử lý"],
        "actions_taken": ["Đã tiếp nhận vé", "Đã trao đổi với khách"],
        "current_status": "Đang chờ xác minh thêm thông tin từ khách.",
        "next_steps": ["Xác minh thông tin", "Phản hồi khách kết quả"],
        "warnings": ["Đây là bản tóm tắt tự động của AI."],
    }


def _mock_draft() -> dict:
    return {
        "draft": ("Cảm ơn bạn đã liên hệ. Chúng tôi đã nhận được yêu cầu và đang "
                  "kiểm tra. Bạn vui lòng chờ phản hồi tiếp theo trong thời gian sớm nhất."),
        "tone": "thân thiện",
        "assumptions": ["Khách cần hỗ trợ thêm về yêu cầu đã gửi"],
        "warnings": ["Đây là bản nháp do AI tạo — vui lòng kiểm tra trước khi gửi."],
    }


class MockProvider(AIProvider):
    """Deterministic offline provider (default). fail_mode, from AI_MOCK_FAIL env
    ('' normal | 'timeout' | 'invalid'), forces a failure for integration tests."""

    model_name = "mock"

    def __init__(self, fail_mode: str = "") -> None:
        self._fail = fail_mode

    async def generate(self, *, result_type: str, system_prompt: str, user_prompt: str) -> str:
        if self._fail == "timeout":
            raise ProviderError("AI_TIMEOUT", "Dịch vụ AI đã quá thời gian phản hồi.")
        if self._fail == "invalid":
            return "đây không phải JSON như yêu cầu"
        if result_type == "CLASSIFICATION":
            payload = _mock_classification(user_prompt)
        elif result_type == "SUMMARY":
            payload = _mock_summary()
        else:
            payload = _mock_draft()
        return json.dumps(payload, ensure_ascii=False)

    async def probe(self) -> bool:
        return True


# ---- Gemini -------------------------------------------------------------------


def build_generate_payload(*, system_prompt: str, user_prompt: str) -> dict:
    return {
        "contents": [{"role": "user", "parts": [
            {"text": system_prompt}, {"text": user_prompt},
        ]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }


def parse_content_text(raw: str) -> str:
    """Concatenate candidate text from a generateContent JSON response (REST)."""
    body = json.loads(raw)
    parts = body["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


class GeminiProvider(AIProvider):
    """Real provider: Google Gemini generateContent over httpx.

    Timeout = settings.ai_timeout_seconds (SRS NFR-PER-05). Retries at most once on
    transient failures only (HTTP 429/5xx or network error); never retries anything
    else (SRS 8.5). probe() is a cheap, token-free reachability check (model lookup).
    """

    def __init__(self, api_key: str, model: str, timeout_seconds: int) -> None:
        self._key = api_key
        self.model_name = model
        self._timeout = timeout_seconds

    def _url(self, task: str) -> str:
        return (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model_name}:{task}?key={self._key}")

    def _model_url(self) -> str:
        # Model metadata is the plain /models/{model} resource — colon-suffix URLs
        # (:generateContent, :countTokens, ...) are reserved for prediction ops, so
        # a ':model' method does not exist and would 404. probe() must use this path.
        return (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model_name}?key={self._key}")

    async def generate(self, *, result_type: str, system_prompt: str, user_prompt: str) -> str:
        payload = build_generate_payload(system_prompt=system_prompt, user_prompt=user_prompt)
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(self._url("generateContent"), json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise ProviderError("AI_TIMEOUT",
                                    "Dịch vụ AI đã quá thời gian phản hồi.") from exc
            transient = resp.status_code == 429 or resp.status_code >= 500
            if resp.status_code == 200:
                try:
                    return parse_content_text(resp.text)
                except (ValueError, KeyError, IndexError) as exc:
                    # Malformed body, or 200 with no candidates (e.g. a
                    # safety-blocked prompt). Surface as a sanitized ProviderError so
                    # the service persists a FAILED row instead of an unhandled 500.
                    raise ProviderError("AI_INVALID_RESPONSE",
                                        "Phản hồi AI không hợp lệ.") from exc
            if transient and attempt < 2:
                await asyncio.sleep(0.2)
                continue
            if resp.status_code == 429:
                raise ProviderError("AI_RATE_LIMITED", "Dịch vụ AI đang quá tải, hãy thử lại sau.")
            raise ProviderError("AI_UNAVAILABLE", "Dịch vụ AI tạm thời không khả dụng.")

    async def probe(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self._model_url())
            return resp.status_code == 200
        except (httpx.HTTPError, ValueError):
            return False


def build_provider() -> AIProvider:
    """Factory read at call time so integration tests can flip AI_MOCK_FAIL per
    request without clearing the cached Settings."""
    settings = get_settings()
    if settings.ai_provider == "gemini":
        if not settings.gemini_api_key:
            raise ProviderError("AI_UNAVAILABLE", "Chưa cấu hình khóa Gemini (GEMINI_API_KEY).")
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model,
                              settings.ai_timeout_seconds)
    return MockProvider(fail_mode=os.environ.get("AI_MOCK_FAIL", ""))
