"""Pydantic mirrors of realdeal.core tables (databricks/sql/ddl.sql) plus API response shapes.

Frozen interface: the web client is generated from the OpenAPI schema these produce (make gen-api).
Change a field here and the generated client changes with it; CI fails until you regenerate and commit.
"""
import json
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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
    total: float | None = None  # receipt footer only, amount paid in CAD including tax


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
    bbox: list[float] | None = None  # [x0, y0, x1, y1] as fractions of the page, origin top-left
    page_no: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    image_url: str | None = None  # Flipp: the tile's own cutout image. Volume pages: null (the page is the image)
    image_path: str | None = None  # Volume pages: the page image. Flipp: null
    page_aspect: float | None = None  # page width / height; null for Volume pages (use the image's own size)

    @field_validator("bbox", mode="before")
    @classmethod
    def _bbox_from_json(cls, v):  # the SQL Statement API returns ARRAY<DOUBLE> as a JSON string
        return json.loads(v) if isinstance(v, str) else v


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
    in_basket: bool = False  # from basket_items


class Receipt(BaseModel):
    receipt_id: str
    user_id: UUID
    store: str | None = None
    total: float | None = None
    bought_at: date | None = None
    image_path: str | None = None


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


class Deal(BaseModel):
    """One flyer listing that is exactly the user's item (logic.same_item), with where to find it in the flyer."""

    user_id: UUID
    user_item_id: str
    flyer_item_id: str
    store: str
    price: float | None = None
    unit_price: float | None = None
    match_score: float = 1.0  # always 1: matching is exact
    savings_vs_median: float | None = None
    item_label: str  # what the user has on their list
    flyer_label: str  # what the flyer advertises
    unit: str | None = None
    week_start: date | None = None
    cost: float  # this listing's price for the user's size (logic.cost); cheapest = lowest cost
    page_id: str
    page_no: int | None = None
    bbox: list[float] | None = None
    valid_from: date | None = None
    valid_to: date | None = None  # the sticky card shows these to the cashier


class ListItem(UserItem):
    """A My List / Basket row. cheapest is what tapping the row opens; null when no flyer has the exact item."""

    cheapest: Deal | None = None
    missing: list[str] = []  # which of brand, item, variant, size are empty; all four are needed to match


class ItemPatch(BaseModel):
    """Edit a list item or move it to/from the basket. Only the fields sent are changed."""

    brand: str | None = None
    item: str | None = Field(None, min_length=1)
    variant: str | None = None
    size_qty: float | None = Field(None, gt=0)
    size_unit: str | None = None
    in_basket: bool | None = None


class Tile(BaseModel):
    item_id: str
    bbox: list[float]
    image_url: str | None = None  # null: draw label and price instead (mock), or the page image already shows it
    label: str
    price: float | None = None


class PageView(BaseModel):
    """One flyer page for the price-match screen: highlight the tile whose item_id is the listing's flyer_item_id."""

    page_id: str
    store: str
    page_no: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    image_url: str | None = None  # full page image, relative to the API (/flyer-pages/{id}/image); null for Flipp
    aspect: float | None = None  # width / height when there is no page image to size from
    tiles: list[Tile]


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
