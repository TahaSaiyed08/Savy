"""Real Deal API. Run: make dev (or uv run uvicorn apps.api.main:app --reload). Docs at /docs."""
import os
import time
from collections import deque
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile

from apps.api import logic, store, stt
from apps.api.extractors import Extractor, get_extractor
from apps.api.models import Basket, Deal, Extraction, IntakeResponse, ManualIntake, SaveItems, UserItem

app = FastAPI(title="Real Deal API", version="0.1.0")
MAX_UPLOAD = 10 * 1024 * 1024
CONFIRM_BELOW = 0.6

# Intake calls paid APIs (Anthropic, ElevenLabs) and the app has no login, so cap them per client IP.
# request.client.host is the real visitor IP behind `make tunnel`: uvicorn resolves X-Forwarded-For from the
# local Next proxy and takes the right-most hop (Cloudflare's), so a forged header can't dodge the limit.
INTAKE_LIMIT = int(os.getenv("INTAKE_LIMIT_PER_HOUR", "30"))
_WINDOW = 3600.0
_hits: dict[str, deque[float]] = {}


def rate_limit(request: Request) -> None:
    now, ip = time.monotonic(), request.client.host if request.client else "unknown"
    if len(_hits) > 10_000:  # bound memory: forget clients idle for a full window
        for k in [k for k, q in _hits.items() if not q or now - q[-1] > _WINDOW]:
            del _hits[k]
    q = _hits.setdefault(ip, deque())
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= INTAKE_LIMIT:
        retry = str(int(_WINDOW - (now - q[0])) + 1)
        raise HTTPException(429, "Too many uploads; try again later", {"Retry-After": retry})
    q.append(now)


UserId = Annotated[UUID, Header(alias="X-User-Id", description="UUID generated on the device")]
Ext = Annotated[Extractor, Depends(get_extractor)]


def _read(upload: UploadFile, kind: str) -> bytes:
    if not (upload.content_type or "").startswith(kind):
        raise HTTPException(415, f"expected {kind}* upload")
    data = upload.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "upload over 10 MB")
    return data


def _respond(x: Extraction, transcript: str | None = None) -> IntakeResponse:
    return IntakeResponse(extraction=x, transcript=transcript,
                          needs_confirm=any(i.confidence < CONFIRM_BELOW for i in x.items))


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mock": store.MOCK}


@app.post("/intake/receipt", dependencies=[Depends(rate_limit)])
def intake_receipt(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(ext.extract("receipt", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/photo", dependencies=[Depends(rate_limit)])
def intake_photo(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(ext.extract("product", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/manual", dependencies=[Depends(rate_limit)])
def intake_manual(user_id: UserId, body: ManualIntake, ext: Ext) -> IntakeResponse:
    return _respond(ext.extract("manual", text=body.text))


@app.post("/intake/voice", dependencies=[Depends(rate_limit)])
def intake_voice(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    text = stt.transcribe(_read(file, "audio/"), file.filename or "audio.webm", file.content_type)
    return _respond(ext.extract("manual", text=text), transcript=text)


@app.get("/items")
def get_items(user_id: UserId) -> list[UserItem]:
    return store.list_items(user_id)


@app.post("/items")
def save_items(user_id: UserId, body: SaveItems) -> list[UserItem]:
    """Saves confirmed intake results."""
    return store.add_items(user_id, body)


@app.get("/deals")
def get_deals(user_id: UserId) -> list[Deal]:
    return store.list_deals(user_id)


@app.get("/basket")
def get_basket(user_id: UserId) -> Basket:
    return logic.basket(store.list_items(user_id), store.list_deals(user_id))
