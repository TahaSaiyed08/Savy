"""extract(mode, image|text) -> Extraction. Same schema and prompts as the pipeline's ai_query."""
import base64
import os
from typing import Protocol

from fastapi import HTTPException

from apps.api.models import ExtractedItem, Extraction, Mode
from shared import load_prompt
from shared.units import normalize_unit


class Extractor(Protocol):
    def extract(
        self, mode: Mode, *, image: bytes | None = None, media_type: str = "image/jpeg", text: str | None = None
    ) -> Extraction: ...


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
        content: list[dict] = []
        if image:
            media_type = sniff_media_type(image)
            if media_type is None:
                raise HTTPException(415, "Unsupported image format; use JPEG, PNG, GIF or WebP "
                                         "(iPhone: Settings > Camera > Formats > Most Compatible)")
            data = base64.standard_b64encode(image).decode()
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
        content.append({"type": "text", "text": text or "Extract the items."})
        r = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=load_prompt(mode),
            messages=[{"role": "user", "content": content}],
            output_format=Extraction,
        )
        if r.stop_reason == "refusal" or r.parsed_output is None:
            raise RuntimeError(f"extraction failed: stop_reason={r.stop_reason}")
        return r.parsed_output


class DatabricksAIExtractor:
    """ai_query on the workspace, so receipts and flyers share one model endpoint.

    TODO(workstream 2): upload the image to /Volumes/realdeal/core/uploads/<uuid> via the SDK, then run
    databricks/sql/ai_query_flyer_page.sql with the receipt/product prompt and read_files(<path>).
    """

    def extract(self, mode, *, image=None, media_type="image/jpeg", text=None):
        raise NotImplementedError("DatabricksAIExtractor: see docstring; use EXTRACTOR=claude meanwhile")


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
