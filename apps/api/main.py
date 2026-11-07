"""Real Deal API. Run: make dev (or uv run uvicorn apps.api.main:app --reload). Docs at /docs."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile

from apps.api import logic, store, stt
from apps.api.extractors import Extractor, get_extractor
from apps.api.models import Basket, Deal, Extraction, IntakeResponse, ManualIntake, SaveItems, UserItem

app = FastAPI(title="Real Deal API", version="0.1.0")
MAX_UPLOAD = 10 * 1024 * 1024
CONFIRM_BELOW = 0.6

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


@app.post("/intake/receipt")
def intake_receipt(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(ext.extract("receipt", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/photo")
def intake_photo(user_id: UserId, file: UploadFile, ext: Ext) -> IntakeResponse:
    return _respond(ext.extract("product", image=_read(file, "image/"), media_type=file.content_type))


@app.post("/intake/manual")
def intake_manual(user_id: UserId, body: ManualIntake, ext: Ext) -> IntakeResponse:
    return _respond(ext.extract("manual", text=body.text))


@app.post("/intake/voice")
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
