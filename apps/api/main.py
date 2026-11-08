"""Real Deal API. Run: make dev (or uv run uvicorn apps.api.main:app --reload). Docs at /docs."""
import ipaddress
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import anthropic
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response, UploadFile

from apps.api import logic, store, stt
from apps.api.extractors import Extractor, get_extractor
from apps.api.models import (
    Basket,
    Deal,
    Extraction,
    IntakeResponse,
    ItemPatch,
    ListItem,
    ManualIntake,
    Mode,
    PageView,
    SaveItems,
    SetBasket,
    Tile,
    UserItem,
)

log = logging.getLogger(__name__)


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
def intake_receipt(user_id: UserId, file: UploadFile, ext: Ext, background: BackgroundTasks) -> IntakeResponse:
    image = _read(file, "image/")
    x = _extract(ext, "receipt", image=image, media_type=file.content_type)
    background.add_task(store.save_receipt, user_id, image, x)  # after the response, so intake isn't slower
    return _respond(x)


@app.post("/intake/photo", dependencies=[Depends(rate_limit)])
def intake_photo(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(_extract(ext, "product", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/manual", dependencies=[Depends(rate_limit)])
def intake_manual(user_id: UserId, body: ManualIntake, ext: Ext) -> IntakeResponse:
    return _respond(_extract(ext, "manual", text=body.text))


@app.post("/intake/voice", dependencies=[Depends(rate_limit)])
def intake_voice(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    audio = _read(file, "audio/")
    try:
        text = stt.transcribe(audio, file.filename or "audio.webm", file.content_type)
    except stt.SpeechServiceError as e:
        log.warning("speech-to-text failed for user %s (%s, %d bytes): %s",
                    user_id, file.content_type, len(audio), e, exc_info=True)
        raise HTTPException(502, "Speech service error; try again or type the item") from e
    if not text.strip():  # silence: don't pay for an extraction that can only invent an item
        raise HTTPException(422, "Didn't catch that; try again")
    return _respond(_extract(ext, "manual", text=text), transcript=text)


def _listed(items: list[UserItem]) -> list[ListItem]:
    """Adds each item's cheapest listing. Flyers being down must not fail the list or a write that already landed
    (the client would retry a saved POST and duplicate it), so the items come back with cheapest=None instead."""
    try:
        flyers = store.flyer_items()
    except Exception:
        log.warning("flyers unavailable; returning %d items without deals", len(items), exc_info=True)
        flyers = []
    best = logic.cheapest(logic.deals_for(items, flyers))
    return [ListItem(**i.model_dump(), cheapest=best.get(i.user_item_id), missing=logic.missing(i)) for i in items]


@app.get("/items")
def get_items(user_id: UserId) -> list[ListItem]:
    """My List (and Basket: in_basket). Tapping a row opens item.cheapest via GET /flyer-pages/{page_id}."""
    return _listed(store.list_items(user_id))


@app.post("/items")
def save_items(user_id: UserId, body: SaveItems) -> list[ListItem]:
    """Saves confirmed intake results. Items missing brand, variant or size are saved but match nothing (missing)."""
    return _listed(store.add_items(user_id, body))


@app.patch("/items/{user_item_id}")
def update_item(user_id: UserId, user_item_id: str, body: ItemPatch) -> ListItem:
    """Edit an item (brand/item/variant/size_qty/size_unit; unknown fields such as price are ignored), or move it to
    or from the Basket with in_basket. Only the fields sent are changed."""
    item = store.update_item(user_id, user_item_id, body)
    if item is None:
        raise HTTPException(404, "no such item")
    return _listed([item])[0]


@app.post("/items/{user_item_id}/basket")
def set_item_basket(user_id: UserId, user_item_id: str, body: SetBasket) -> ListItem:
    """Moves a My List item into (or out of) the Basket. Same as PATCH with only in_basket."""
    return update_item(user_id, user_item_id, ItemPatch(in_basket=body.in_basket))


@app.delete("/items/{user_item_id}", status_code=204)
def delete_item(user_id: UserId, user_item_id: str) -> None:
    store.delete_item(user_id, user_item_id)


@app.get("/deals")
def get_deals(user_id: UserId) -> list[Deal]:
    """Every store's cheapest exact listing for every item on My List."""
    return logic.deals_for(store.list_items(user_id), store.flyer_items())


@app.get("/basket")
def get_basket(user_id: UserId) -> Basket:
    """Store comparison for the Basket (items with in_basket) only."""
    items = [i for i in store.list_items(user_id) if i.in_basket]
    return logic.basket(items, logic.deals_for(items, store.flyer_items()))


@app.get("/flyer-pages/{page_id}")
def get_page(page_id: str) -> PageView:
    """The flyer page a listing is on, with every tile's box, for the price-match screen."""
    tiles = store.page_tiles(page_id)
    if not tiles:
        raise HTTPException(404, "page not in a current flyer")
    f = tiles[0]
    return PageView(
        page_id=page_id, store=f.store, page_no=f.page_no, valid_from=f.valid_from, valid_to=f.valid_to,
        image_url=f"/flyer-pages/{page_id}/image" if f.image_path else None, aspect=f.page_aspect,
        tiles=[Tile(item_id=t.item_id, bbox=t.bbox, image_url=t.image_url, label=t.raw_text or logic.label(t),
                    price=t.price) for t in tiles if t.bbox],
    )


@app.get("/flyer-pages/{page_id}/image", response_class=Response,
         responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}})
def get_page_image(page_id: str) -> Response:
    """The page JPEG/PNG from the flyers Volume (only pages that came from page images, not Flipp)."""
    path = next((t.image_path for t in store.page_tiles(page_id) if t.image_path), None)
    if not path:
        raise HTTPException(404, "no page image")
    image = store.page_image(path)
    if image is None:
        raise HTTPException(404, "page image missing from the Volume")
    media = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return Response(image, media_type=media, headers={"Cache-Control": "public, max-age=604800"})
