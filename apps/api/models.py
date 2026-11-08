"""Pydantic mirrors of realdeal.core tables (databricks/sql/ddl.sql) plus API response shapes.

Frozen interface: the web client is generated from the OpenAPI schema these produce (make gen-api).
Change a field here and the generated client changes with it; CI fails until you regenerate and commit.
"""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Mode = Literal["flyer_page", "receipt", "product", "manual"]
Source = Literal["receipt", "photo", "manual", "voice"]


class ExtractedItem(BaseModel):
    """The one schema every extraction mode returns (shared/prompts/*.md)."""

    brand: str | None = None
    item: str
    variant: str | None = None
    size_qty: float | None = None
    size_unit: str | None = None
    price: float | None = None
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    items: list[ExtractedItem]
    store: str | None = None  # receipt header only
    bought_at: str | None = None  # receipt header only, ISO date


# --- realdeal.core tables -------------------------------------------------


class FlyerPage(BaseModel):  # Bronze
    page_id: str
    store: str
    week_start: date
    page_no: int
    image_path: str
    fetched_at: datetime


class FlyerItem(BaseModel):  # Silver
    item_id: str
    page_id: str
    store: str
    week_start: date
    brand: str | None = None
    item: str
    variant: str | None = None
    size_qty: float | None = None
    size_unit: str | None = None
    price: float | None = None
    unit_price: float | None = None
    unit: str | None = None  # "100g", "100ml" or "ea"
    raw_text: str | None = None
    bbox: list[float] | None = None


class WeeklyPrice(BaseModel):  # Gold
    store: str
    week_start: date
    canonical_item: str
    unit_price: float


class User(BaseModel):
    user_id: UUID
    created_at: datetime


class UserItem(BaseModel):
    user_item_id: str
    user_id: UUID
    brand: str | None = None
    item: str
    variant: str | None = None
    size_qty: float | None = None
    size_unit: str | None = None
    source: Source
    added_at: datetime
    last_bought_at: datetime | None = None


class Receipt(BaseModel):
    receipt_id: str
    user_id: UUID
    store: str | None = None
    total: float | None = None
    bought_at: date | None = None
    image_path: str | None = None


class MyDeal(BaseModel):  # Gold view
    user_id: UUID
    user_item_id: str
    flyer_item_id: str
    store: str
    price: float | None = None
    unit_price: float | None = None
    match_score: float
    savings_vs_median: float | None = None


# --- API shapes -----------------------------------------------------------


class IntakeResponse(BaseModel):
    """Parsed but NOT saved. The client confirms, then POSTs /items."""

    extraction: Extraction
    needs_confirm: bool  # any item under 0.6 confidence
    transcript: str | None = None  # voice only


class ManualIntake(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SaveItems(BaseModel):
    items: list[ExtractedItem] = Field(min_length=1, max_length=100)
    source: Source
    bought_at: datetime | None = None


class Deal(MyDeal):
    item_label: str  # what the user has on their list
    flyer_label: str  # what the flyer advertises
    unit: str | None = None
    week_start: date | None = None  # None in non-mock mode until the Gold view carries it


class StoreTotal(BaseModel):
    store: str
    total: float
    matched: int
    missing: int


class SplitLine(BaseModel):
    user_item_id: str
    item_label: str
    store: str
    cost: float


class Basket(BaseModel):
    stores: list[StoreTotal]  # best first: fewest missing, then cheapest
    cheapest_store: str | None
    split: list[SplitLine]
    split_total: float
    delta: float  # cheapest single store minus split-shopping the same items, in CAD
    unmatched: list[str]  # "no deal this week"
