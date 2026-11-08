"""Real Deal API. Run: make dev (or uv run uvicorn apps.api.main:app --reload). Docs at /docs."""
import ipaddress
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile

from apps.api import logic, store, stt
from apps.api.extractors import Extractor, get_extractor
from apps.api.models import Basket, Deal, Extraction, IntakeResponse, ManualIntake, Mode, SaveItems, UserItem


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_extractor()  # a bad EXTRACTOR or a missing key fails at boot, not on the first upload
    yield


app = FastAPI(title="Real Deal API", version="0.1.0", lifespan=lifespan)
MAX_UPLOAD = 10 * 1024 * 1024
CONFIRM_BELOW = 0.6

# Intake calls paid APIs (Anthropic, ElevenLabs) and the app has no login, so cap them per client and globally.
# request.client.host is the real visitor IP behind `make tunnel`: uvicorn resolves X-Forwarded-For from the
# local Next proxy and takes the right-most hop (Cloudflare's), so a forged header can't dodge the limit.
INTAKE_LIMIT = int(os.getenv("INTAKE_LIMIT_PER_HOUR", "30"))
INTAKE_GLOBAL_LIMIT = int(os.getenv("INTAKE_GLOBAL_LIMIT_PER_HOUR", "300"))  # backstop on total spend
_WINDOW = 3600.0
_hits: dict[str, deque[float]] = {}
_global: deque[float] = deque()


def _client_key(host: str) -> str:
    """IPv4 address, or the /64 for IPv6 (one host usually controls a whole /64)."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    return str(ipaddress.ip_network(f"{ip}/64", strict=False)) if ip.version == 6 else host


def _prune(q: deque[float], now: float) -> None:
    while q and now - q[0] > _WINDOW:
        q.popleft()


async def rate_limit(request: Request) -> None:
    """async on purpose: it runs on the event-loop thread, so check-then-record can't race."""
    now = time.monotonic()
    key = _client_key(request.client.host if request.client else "unknown")
    q = _hits.get(key, deque())
    _prune(q, now)
    _prune(_global, now)
    full = q if len(q) >= INTAKE_LIMIT else _global if len(_global) >= INTAKE_GLOBAL_LIMIT else None
    if full is not None:
        retry = str(int(_WINDOW - (now - full[0])) + 1)
        raise HTTPException(429, "Too many uploads; try again later", {"Retry-After": retry})
    q.append(now)
    _global.append(now)
    _hits[key] = q  # only accepted calls create entries, so memory is bounded by the global cap
    if len(_hits) > 2 * INTAKE_GLOBAL_LIMIT:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > _WINDOW]:
            del _hits[k]


UserId = Annotated[UUID, Header(alias="X-User-Id", description="UUID generated on the device")]
Ext = Annotated[Extractor, Depends(get_extractor)]


def _read(upload: UploadFile, kind: str) -> bytes:
    if not (upload.content_type or "").startswith(kind):
        raise HTTPException(415, f"expected {kind}* upload")
    data = upload.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "upload over 10 MB")
    return data


def _extract(ext: Extractor, mode: Mode, **kw) -> Extraction:
    """Turns extractor failures into client-facing errors instead of a bare 500."""
    try:
        return ext.extract(mode, **kw)
    except anthropic.APIError as e:  # status errors and connection/timeouts alike
        raise HTTPException(502, f"Extraction service error: {e.message}") from e
    except NotImplementedError:
        raise
    except RuntimeError as e:  # refusal or unparseable output
        what = "this image; try a clearer photo" if kw.get("image") else "that; try rephrasing"
        raise HTTPException(422, f"Couldn't read {what}") from e


def _respond(x: Extraction, transcript: str | None = None) -> IntakeResponse:
    return IntakeResponse(extraction=x, transcript=transcript,
                          needs_confirm=any(i.confidence < CONFIRM_BELOW for i in x.items))


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mock": store.MOCK, "extractor": type(get_extractor()).__name__}


@app.post("/intake/receipt", dependencies=[Depends(rate_limit)])
def intake_receipt(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(_extract(ext, "receipt", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/photo", dependencies=[Depends(rate_limit)])
def intake_photo(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(_extract(ext, "product", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/manual", dependencies=[Depends(rate_limit)])
def intake_manual(user_id: UserId, body: ManualIntake, ext: Ext) -> IntakeResponse:
    return _respond(_extract(ext, "manual", text=body.text))


@app.post("/intake/voice", dependencies=[Depends(rate_limit)])
def intake_voice(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    text = stt.transcribe(_read(file, "audio/"), file.filename or "audio.webm", file.content_type)
    return _respond(_extract(ext, "manual", text=text), transcript=text)


@app.get("/items")
def get_items(user_id: UserId) -> list[UserItem]:
    return store.list_items(user_id)


@app.post("/items")
def save_items(user_id: UserId, body: SaveItems) -> list[UserItem]:
    """Saves confirmed intake results."""
    return store.add_items(user_id, body)


@app.delete("/items/{user_item_id}", status_code=204)
def delete_item(user_id: UserId, user_item_id: str) -> None:
    store.delete_item(user_id, user_item_id)


@app.get("/deals")
def get_deals(user_id: UserId) -> list[Deal]:
    return store.list_deals(user_id)


@app.get("/basket")
def get_basket(user_id: UserId) -> Basket:
    return logic.basket(store.list_items(user_id), store.list_deals(user_id))
