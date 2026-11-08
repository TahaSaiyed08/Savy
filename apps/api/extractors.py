"""extract(mode, image|text) -> Extraction. Same schema and prompts as the pipeline's ai_query."""
import base64
import io
import json
import logging
import os
import re
import uuid
from typing import Protocol

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


class ExtractionServiceError(Exception):
    """The extraction backend itself failed (warehouse, model endpoint, upload): a 502, not the photo's fault."""


_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
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
        raw = rows[0].get("r") if rows else None
        try:
            return Extraction.model_validate_json(raw or "")
        except ValueError as e:  # the model answered, but not in the schema: same as a Claude refusal (422)
            raise RuntimeError(f"ai_query returned no usable extraction: {str(raw)[:200]}") from e


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


_EXTRACTORS = {"mock": MockExtractor, "claude": ClaudeExtractor, "databricks": DatabricksAIExtractor}


def get_extractor() -> Extractor:
    choice = os.getenv("EXTRACTOR") or ("claude" if os.getenv("ANTHROPIC_API_KEY") else "mock")
    if choice not in _EXTRACTORS:
        raise ValueError(f"EXTRACTOR={choice!r} is not one of: {', '.join(_EXTRACTORS)}")
    return _EXTRACTORS[choice]()
