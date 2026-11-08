"""extract(mode, image|text) -> Extraction. Same schema and prompts as the pipeline's ai_query."""
import base64
import io
import json
import logging
import os
import re
import time
import uuid
from typing import Protocol

import httpx
from fastapi import HTTPException

from apps.api.models import ExtractedItem, Extraction, Mode
from shared import load_prompt
from shared.units import normalize_unit

log = logging.getLogger(__name__)


# An extractor turns a photo or a line of text into candidate items. Three interchangeable implementations sit behind
# this one interface (Claude, Databricks ai_query, and a canned mock), and get_extractor() picks one at startup.
class Extractor(Protocol):
    def extract(
        self, mode: Mode, *, image: bytes | None = None, media_type: str = "image/jpeg", text: str | None = None
    ) -> Extraction: ...


# The first bytes of a file say what it really is. Phones and browsers often mislabel uploads (HEIC called JPEG), and
# the model APIs reject a wrong type, so the real type is detected rather than trusted.
_MAGIC = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"GIF8", "image/gif"))


def sniff_media_type(image: bytes) -> str | None:
    """Real type from magic bytes (JPEG/PNG/GIF/WebP), otherwise None. Uploads are often mislabeled."""
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return next((t for magic, t in _MAGIC if image.startswith(magic)), None)


class ClaudeExtractor:
    """Anthropic API. The fallback if ai_query is unavailable on the workspace (11:00 go/no-go)."""

    def __init__(self) -> None:
        import anthropic

        # The SDK only complains about a missing key on the first request; fail at startup instead.
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise RuntimeError("EXTRACTOR=claude needs ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic()
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")

    def extract(self, mode, *, image=None, media_type="image/jpeg", text=None):
        # A message to Claude is a list of parts: the picture (if any) first, then the text instruction.
        content: list[dict] = []
        if image:
            media_type = sniff_media_type(image)
            if media_type is None:
                raise HTTPException(415, "Unsupported image format; use JPEG, PNG, GIF or WebP "
                                         "(iPhone: Settings > Camera > Formats > Most Compatible)")
            data = base64.standard_b64encode(image).decode()
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
        content.append({"type": "text", "text": text or "Extract the items."})
        # `parse` makes the SDK validate the reply against Extraction, so a malformed answer fails here, not later.
        r = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=load_prompt(mode),
            messages=[{"role": "user", "content": content}],
            output_format=Extraction,
        )
        # A refusal or empty parse becomes a RuntimeError, which the API reports to the app as a 422 "couldn't read".
        if r.stop_reason == "refusal" or r.parsed_output is None:
            raise RuntimeError(f"extraction failed: stop_reason={r.stop_reason}")
        return r.parsed_output


# Failures of the backend itself (as opposed to a bad photo) get their own type so the API can answer 502 "try again"
# instead of blaming the person's input with a 422.
class ExtractionServiceError(Exception):
    """The extraction backend itself failed (warehouse, model endpoint, upload): a 502, not the photo's fault."""


_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
# Asks Databricks to force the model's reply to match the Extraction JSON schema, the same contract Claude uses.
_RESPONSE_FORMAT = json.dumps({"type": "json_schema", "json_schema": {
    "name": "extraction", "strict": True, "schema": Extraction.model_json_schema()}})


class DatabricksAIExtractor:
    """ai_query on the workspace (opt-in: EXTRACTOR=databricks). Same prompts and Extraction schema as Claude.

    Images go to the uploads Volume and are read with read_files, then deleted; text modes send the text alone.
    Measured on the demo receipt: ~25 s on a warm warehouse (Claude ~12 s), right prices and total, but weaker on
    abbreviated lines and overconfident when wrong, so Claude stays the default.
    """

    UPLOADS = "/Volumes/realdeal/core/uploads/extract"

    def __init__(self) -> None:
        missing = [v for v in ("DATABRICKS_HOST", "DATABRICKS_WAREHOUSE_ID") if not os.getenv(v)]
        if missing:
            raise RuntimeError(f"EXTRACTOR=databricks needs {', '.join(missing)}")
        self.model = os.getenv("DATABRICKS_EXTRACT_MODEL", "databricks-llama-4-maverick")
        # The endpoint name is pasted into the SQL text (SQL can't parameterise it), so only plain names are allowed.
        if not re.fullmatch(r"[\w.-]+", self.model):  # it's inlined in the SQL: endpoint names can't be parameters
            raise ValueError(f"DATABRICKS_EXTRACT_MODEL={self.model!r} isn't a serving endpoint name")

    def extract(self, mode, *, image=None, media_type="image/jpeg", text=None):
        from apps.api import databricks_sql as db

        if not image:
            sql = f"SELECT ai_query('{self.model}', concat(:prompt, '\\n\\n', :text), responseFormat => :fmt) AS r"
            return self._parse(self._run(db, sql, prompt=load_prompt(mode), text=text or "", fmt=_RESPONSE_FORMAT))
        media_type = sniff_media_type(image)
        if media_type is None:
            raise HTTPException(415, "Unsupported image format; use JPEG, PNG, GIF or WebP "
                                     "(iPhone: Settings > Camera > Formats > Most Compatible)")
        # Images take a detour: upload to a Volume, read them back inside the query, and always delete afterwards (the
        # `finally` below), so receipts don't pile up in the workspace.
        path = f"{self.UPLOADS}/{uuid.uuid4()}.{_EXT[media_type]}"
        try:
            try:
                db._client().files.upload(path, io.BytesIO(image), overwrite=False)
            except Exception as e:
                raise ExtractionServiceError(f"upload to {self.UPLOADS} failed: {e}") from e
            sql = (f"SELECT ai_query('{self.model}', :prompt, files => content, responseFormat => :fmt) AS r "
                   "FROM read_files(:path, format => 'binaryFile')")
            return self._parse(self._run(db, sql, prompt=load_prompt(mode), fmt=_RESPONSE_FORMAT, path=path))
        finally:
            try:
                db._client().files.delete(path)
            except Exception:
                log.warning("couldn't delete %s", path, exc_info=True)

    @staticmethod
    def _run(db, sql: str, **params) -> list[dict]:
        try:
            return db.run_long(sql, **params)
        except Exception as e:
            raise ExtractionServiceError(f"ai_query failed: {e}") from e

    @staticmethod
    def _parse(rows: list[dict]) -> Extraction:
        # The query returns one row with the model's JSON in column `r`; validate it against the schema.
        raw = rows[0].get("r") if rows else None
        try:
            return Extraction.model_validate_json(raw or "")
        except ValueError as e:  # the model answered, but not in the schema: same as a Claude refusal (422)
            raise RuntimeError(f"ai_query returned no usable extraction: {str(raw)[:200]}") from e


class GeminiExtractor:
    """Google's Gemini API (EXTRACTOR=gemini, or the default when only GEMINI_API_KEY is set).

    Same prompts and Extraction schema as Claude and ai_query, called over REST with httpx so it adds no dependency. The
    model is asked for JSON that matches the schema, and the reply is validated against it, so a malformed answer fails
    here (as a 422) instead of reaching the app.
    """

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    TIMEOUT = 40.0  # one attempt on the main model: a receipt takes 5 to 20 s, so longer means it has stalled
    FALLBACK_TIMEOUT = 25.0  # one attempt on a lighter model, which answers the same receipt in about 4 s
    # A model that just failed is skipped for a while, so the next scan does not spend 10 to 20 s waiting on it again.
    # Shared by every request: one scan finding the main model out of quota helps all the ones after it.
    COOLDOWN = {429: 120.0, 500: 30.0, 502: 30.0, 503: 30.0, "timeout": 60.0}
    _cooling: dict[str, float] = {}  # model -> time.monotonic() until which it is skipped

    def __init__(self) -> None:
        self.key = os.getenv("GEMINI_API_KEY")
        if not self.key:  # fail at startup, like the other extractors, not on the first upload
            raise RuntimeError("EXTRACTOR=gemini needs GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        if not re.fullmatch(r"[\w.-]+", self.model):  # the name goes into the URL path
            raise ValueError(f"GEMINI_MODEL={self.model!r} isn't a model name")
        # When the main model is out of quota, busy or stalled, these answer instead, in this order. Each lighter model
        # has its own quota and its own busy spells, which is why there are several. Set it empty to turn this off.
        default = "gemini-3.5-flash-lite,gemini-flash-lite-latest,gemini-3.1-flash-lite"
        names = os.getenv("GEMINI_FALLBACK_MODEL", default)
        self.fallbacks = [n.strip() for n in names.split(",") if n.strip() and n.strip() != self.model]
        for n in self.fallbacks:
            if not re.fullmatch(r"[\w.-]+", n):
                raise ValueError(f"GEMINI_FALLBACK_MODEL has {n!r}, which isn't a model name")

    def _post(self, body: dict) -> httpx.Response:
        """Ask Gemini, and keep going past the two things that go wrong in practice: a model is out of quota or busy
        (429, 500, 502, 503) or it stalls (a timeout). The main model goes first, then each fallback in turn, each at
        most once; a model that failed recently is skipped (unless every model did). Returns the last refusal (so the
        caller reports its status) or re-raises the last timeout; any other answer, an error like 400 or 403
        included, is returned at once."""
        headers = {"x-goog-api-key": self.key}
        chain = [self.model, *self.fallbacks]
        if len(chain) == 1:
            chain *= 2  # nothing to fall back to: try the one model again
        now = time.monotonic()
        ready = [m for m in chain if self._cooling.get(m, 0) <= now]
        last: httpx.Response | Exception | None = None
        for n, model in enumerate(ready or chain):
            if n:
                time.sleep(1)  # a short pause between models
            try:
                r = httpx.post(self.URL.format(model=model), headers=headers, json=body,
                               timeout=self.TIMEOUT if model == self.model else self.FALLBACK_TIMEOUT)
            except httpx.TimeoutException as e:
                self._cooling[model] = time.monotonic() + self.COOLDOWN["timeout"]
                last = e
                continue
            if r.status_code not in self.COOLDOWN:
                return r
            self._cooling[model] = time.monotonic() + self.COOLDOWN[r.status_code]
            last = r
        if isinstance(last, Exception):
            raise last
        return last  # type: ignore[return-value]  # the chain is never empty, so something was tried

    def extract(self, mode, *, image=None, media_type="image/jpeg", text=None):
        parts: list[dict] = []
        if image:
            media_type = sniff_media_type(image)
            if media_type is None:
                raise HTTPException(415, "Unsupported image format; use JPEG, PNG, GIF or WebP "
                                         "(iPhone: Settings > Camera > Formats > Most Compatible)")
            parts.append({"inline_data": {"mime_type": media_type, "data": base64.standard_b64encode(image).decode()}})
        parts.append({"text": text or "Extract the items."})
        body = {
            "system_instruction": {"parts": [{"text": load_prompt(mode)}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseJsonSchema": Extraction.model_json_schema(), "temperature": 0},
        }
        try:
            r = self._post(body)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:  # only the status: the response can echo parts of the request
            raise ExtractionServiceError(f"Gemini answered {e.response.status_code}") from e
        except (httpx.HTTPError, ValueError) as e:
            raise ExtractionServiceError(f"Gemini request failed: {type(e).__name__}") from e
        try:
            reply = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:  # blocked, or an empty answer
            reason = (data.get("promptFeedback") or {}).get("blockReason") or "no answer"
            raise RuntimeError(f"Gemini returned no usable extraction: {reason}") from e
        try:
            return Extraction.model_validate_json(reply)
        except ValueError as e:  # the model answered, but not in the schema: treated like a Claude refusal (422)
            raise RuntimeError(f"Gemini returned no usable extraction: {reply[:200]}") from e


# What the app uses with no API keys, so a fresh clone runs end to end. The numbers are chosen to exercise the UI: one
# low-confidence item per mode shows the "please confirm" sheet.
class MockExtractor:
    """Canned output so the app runs from a fresh clone with no keys."""

    def extract(self, mode, *, image=None, media_type="image/jpeg", text=None):
        if mode == "manual":
            s = normalize_unit(text or "")
            return Extraction(items=[ExtractedItem(
                item=(text or "").removeprefix("add ").strip(), confidence=0.9,
                size_qty=s.qty if s else None, size_unit=s.unit if s else None,
            )])
        if mode == "product":
            return Extraction(items=[
                ExtractedItem(brand="Bertolli", item="olive oil", variant="extra virgin", size_qty=1,
                              size_unit="l", confidence=0.82),
                ExtractedItem(brand="Bertolli", item="olive oil", variant="extra virgin", size_qty=0.5,
                              size_unit="l", confidence=0.4),
            ])
        return Extraction(store="Save-On-Foods", bought_at="2026-11-06", items=[
            ExtractedItem(brand="PC", item="chicken thigh", variant="boneless", size_qty=1, size_unit="kg",
                          price=11.99, confidence=0.93),
            ExtractedItem(item="banana", size_qty=1, size_unit="lb", price=0.79, confidence=0.97),
            ExtractedItem(item="eggs", variant="large", size_qty=12, size_unit="ea", price=4.49, confidence=0.88),
            ExtractedItem(item="oat milk", variant="original", size_qty=1.75, size_unit="l", price=5.29,
                          confidence=0.55),
        ])


_EXTRACTORS = {"mock": MockExtractor, "claude": ClaudeExtractor, "databricks": DatabricksAIExtractor,
               "gemini": GeminiExtractor}


def get_extractor() -> Extractor:
    # Explicit EXTRACTOR wins; otherwise an Anthropic key means Claude, a Gemini key means Gemini, and no key means the
    # mock.
    choice = os.getenv("EXTRACTOR") or (
        "claude" if os.getenv("ANTHROPIC_API_KEY") else "gemini" if os.getenv("GEMINI_API_KEY") else "mock")
    if choice not in _EXTRACTORS:
        raise ValueError(f"EXTRACTOR={choice!r} is not one of: {', '.join(_EXTRACTORS)}")
    return _EXTRACTORS[choice]()
