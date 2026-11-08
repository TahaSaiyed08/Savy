"""The Gemini extractor, with Google's API replaced by a function we control (no network, no key)."""
import base64
import json

import httpx
import pytest
from fastapi import HTTPException

from apps.api import extractors
from apps.api.extractors import ExtractionServiceError, GeminiExtractor, get_extractor

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 20
ITEMS = {"items": [{"brand": "Dairyland", "item": "milk", "variant": "2%", "size_qty": 4, "size_unit": "l",
                    "price": None, "confidence": 0.98}], "store": None, "bought_at": None, "total": None}


def _reply(payload: dict | str, status: int = 200) -> httpx.Response:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]} if status == 200 else {"error": {"message": "x"}}
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://example.test"))


@pytest.fixture
def gemini(monkeypatch):
    """A GeminiExtractor whose calls are recorded and answered from `answers` (one per call, in order)."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    sent, answers = [], []

    def post(url, headers=None, json=None, timeout=None):
        sent.append({"url": url, "headers": headers, "body": json, "timeout": timeout})
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, Exception):
            raise answer  # a stall: the call times out instead of answering
        return answer

    monkeypatch.setattr(extractors.httpx, "post", post)
    monkeypatch.setattr(extractors.time, "sleep", lambda s: None)
    ext = GeminiExtractor()
    ext.sent, ext.answers = sent, answers
    return ext


def test_typed_text_is_sent_with_the_prompt_and_the_schema_and_read_back(gemini):
    gemini.answers.append(_reply(ITEMS))
    x = gemini.extract("manual", text="a 4 L jug of 2% Dairyland milk")
    assert [(i.brand, i.item, i.variant, i.size_qty, i.size_unit) for i in x.items] == [
        ("Dairyland", "milk", "2%", 4, "l")]
    (call,) = gemini.sent
    assert call["url"].endswith("/models/gemini-3.5-flash:generateContent")
    assert call["headers"] == {"x-goog-api-key": "test-key"}  # the key travels in a header, never in the URL
    body = call["body"]
    assert body["contents"][0]["parts"] == [{"text": "a 4 L jug of 2% Dairyland milk"}]
    assert body["system_instruction"]["parts"][0]["text"]  # the shared extraction prompt
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "items" in body["generationConfig"]["responseJsonSchema"]["properties"]


def test_a_photo_is_sent_inline_with_its_real_type_not_the_claimed_one(gemini):
    gemini.answers.append(_reply(ITEMS))
    gemini.extract("product", image=JPEG, media_type="image/png")  # mislabelled upload
    first = gemini.sent[0]["body"]["contents"][0]["parts"][0]["inline_data"]
    assert first["mime_type"] == "image/jpeg" and base64.b64decode(first["data"]) == JPEG


def test_an_unsupported_image_is_a_415_before_any_call_is_made(gemini):
    with pytest.raises(HTTPException) as e:
        gemini.extract("product", image=b"not an image")
    assert e.value.status_code == 415 and gemini.sent == []


def _model(call):
    return call["url"].split("/models/")[1].split(":")[0]


def test_a_busy_gemini_is_retried_on_the_lighter_model_then_answers(gemini):
    gemini.answers += [_reply("", 429), _reply(ITEMS)]
    assert gemini.extract("manual", text="milk").items[0].item == "milk"
    assert [_model(c) for c in gemini.sent] == ["gemini-3.5-flash", "gemini-3.1-flash-lite"]


def test_a_stalled_main_model_is_given_up_on_quickly_and_the_fallback_answers(gemini):
    gemini.answers += [httpx.ReadTimeout("stalled"), _reply(ITEMS)]
    assert gemini.extract("manual", text="milk").items[0].item == "milk"
    first, second = gemini.sent
    assert (_model(first), first["timeout"]) == ("gemini-3.5-flash", GeminiExtractor.TIMEOUT)
    assert (_model(second), second["timeout"]) == ("gemini-3.1-flash-lite", GeminiExtractor.FALLBACK_TIMEOUT)


def test_it_gives_up_after_three_attempts_and_reports_the_last_status(gemini):
    gemini.answers.append(_reply("", 429))
    with pytest.raises(ExtractionServiceError, match="429"):
        gemini.extract("manual", text="milk")
    assert len(gemini.sent) == GeminiExtractor.ATTEMPTS == 3


def test_with_no_fallback_the_main_model_is_simply_tried_again(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")
    ext = GeminiExtractor()
    gemini.answers += [_reply("", 503), _reply(ITEMS)]
    ext.extract("manual", text="milk")
    assert [_model(c) for c in gemini.sent] == ["gemini-3.5-flash", "gemini-3.5-flash"]


def test_a_bad_request_or_key_is_not_retried(gemini):
    gemini.answers.append(_reply("", 400))
    with pytest.raises(ExtractionServiceError, match="400"):
        gemini.extract("manual", text="milk")
    assert len(gemini.sent) == 1


def test_an_http_error_is_a_service_error_that_never_leaks_the_key(gemini):
    gemini.answers.append(_reply("", 403))
    with pytest.raises(ExtractionServiceError) as e:
        gemini.extract("manual", text="milk")
    assert "403" in str(e.value) and "test-key" not in str(e.value)


def test_a_network_failure_is_a_service_error(gemini, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(extractors.httpx, "post", boom)
    with pytest.raises(ExtractionServiceError, match="ConnectTimeout"):
        gemini.extract("manual", text="milk")


@pytest.mark.parametrize("reply", [
    {"promptFeedback": {"blockReason": "SAFETY"}},  # blocked: no candidates at all
    {"candidates": []},
])
def test_a_blocked_or_empty_answer_is_a_422_not_a_crash(gemini, reply):
    gemini.answers.append(httpx.Response(200, json=reply, request=httpx.Request("POST", "https://example.test")))
    with pytest.raises(RuntimeError, match="no usable extraction"):
        gemini.extract("manual", text="milk")


def test_an_answer_that_is_not_in_the_schema_is_rejected(gemini):
    gemini.answers.append(_reply('{"items": "none"}'))
    with pytest.raises(RuntimeError, match="no usable extraction"):
        gemini.extract("manual", text="milk")


def test_setup_mistakes_fail_at_startup(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiExtractor()
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "x/../../y")  # the name goes into the URL
    with pytest.raises(ValueError, match="GEMINI_MODEL"):
        GeminiExtractor()
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "../evil")
    with pytest.raises(ValueError, match="GEMINI_FALLBACK_MODEL"):
        GeminiExtractor()


def test_it_is_chosen_by_name_or_when_it_is_the_only_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("EXTRACTOR", "gemini")
    assert isinstance(get_extractor(), GeminiExtractor)
    monkeypatch.delenv("EXTRACTOR")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_extractor(), GeminiExtractor)  # only a Gemini key set
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert type(get_extractor()).__name__ == "ClaudeExtractor"  # Claude stays the default when both are set
