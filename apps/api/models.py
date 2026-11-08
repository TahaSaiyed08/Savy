"""Pydantic mirrors of realdeal.core tables (databricks/sql/ddl.sql) plus API response shapes.

Frozen interface: the web client is generated from the OpenAPI schema these produce (make gen-api).
Change a field here and the generated client changes with it; CI fails until you regenerate and commit.
"""
import json
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Mode = Literal["flyer_page", "receipt", "product", "manual"]
Source = Literal["receipt", "photo", "manual", "voice", "flyer"]  # flyer: identity copied from a listing
Field4 = Literal["brand", "item", "variant", "size"]
# [x0, y0, x1, y1] as fractions of the page, origin top-left. Bad rows fail on load instead of losing the highlight.
# Flipp hands some stores' links through an ad-click tracker, which lands on a generic page with Flipp's tags on it.
_NOT_A_STORE = ("doubleclick.net", "googleadservices.com", "flipp.com", "wishabi.com", "wishabi.net")


def clean_store_url(raw: str | None) -> str | None:
    """The store's own page for an item, without tracking tags. https only, and never Flipp or an ad tracker: the
    value comes from outside and ends up in a link people tap."""
    parts = urlsplit(raw or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not parts.netloc or any(host == d or host.endswith("." + d) for d in _NOT_A_STORE):
        return None
    return f"https://{parts.netloc}{parts.path}"


BBox = Annotated[list[Annotated[float, Field(ge=0, le=1)]], Field(min_length=4, max_length=4)]


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
    bbox: BBox | None = None
    page_no: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    image_url: str | None = None  # Flipp: the tile's own cutout image. Volume pages: null (the page is the image)
    image_path: str | None = None  # Volume pages: the page image. Flipp: null
    page_aspect: float | None = None  # page width / height; null for Volume pages (use the image's own size)
    regular_price: float | None = None  # Flipp's original_price, when the flyer prints one
    conditions: str | None = None  # "Get PC Optimum 1,000 pts", "Limit 4"
    store_url: str | None = None  # the store's own page for the item, when Flipp knows it
    category: str | None = None  # Dairy & eggs, Produce, ...: from the AI refiner, null until it has run

    @field_validator("store_url")
    @classmethod
    def _store_page_only(cls, v):  # also cleans rows saved to disk by an older parser
        return clean_store_url(v)

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
    done: bool = False  # basket_items.done_at is set: bought on this trip, still in the Basket's Done section


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
    savings_vs_median: float | None = None
    item_label: str  # what the user has on their list
    flyer_label: str  # what the flyer advertises
    unit: str | None = None
    week_start: date | None = None
    cost: float  # this listing's price for the user's size (logic.cost); cheapest = lowest cost
    page_id: str
    page_no: int | None = None
    bbox: BBox | None = None
    valid_from: date | None = None
    valid_to: date | None = None  # the sticky card shows these to the cashier
    image_url: str | None = None  # the tile's cutout from the flyer
    regular_price: float | None = None
    conditions: str | None = None
    store_url: str | None = None  # the store's own page for it


class FlyerListing(BaseModel):
    """One store's listing, with enough to open its exact tile."""

    label: str
    store: str
    price: float | None = None
    unit_price: float | None = None
    unit: str | None = None
    flyer_item_id: str
    page_id: str
    page_no: int | None = None
    bbox: BBox | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    image_url: str | None = None
    regular_price: float | None = None
    conditions: str | None = None
    store_url: str | None = None


class ListItem(UserItem):
    """A My List / Basket row. cheapest is what tapping the row opens; null when no flyer has the exact item."""

    cheapest: Deal | None = None
    saves_vs_next: float | None = None  # how much less cheapest is than the next store's price for this item
    closest: list[FlyerListing] = []  # similar listings, only when there is no exact one
    missing: list[Field4] = []  # empty (or unreadable size); all four are needed to match


class ItemPatch(BaseModel):
    """Edit a list item or move it to/from the basket. Only the fields sent are changed; unknown fields are ignored."""

    model_config = {"str_strip_whitespace": True}

    brand: str | None = None
    item: str = Field(None, min_length=1)  # may be omitted, never null or blank
    variant: str | None = None
    size_qty: float | None = Field(None, gt=0)
    size_unit: str | None = None
    in_basket: bool | None = None
    done: bool | None = None


class SetBasket(BaseModel):
    in_basket: bool


class Tile(BaseModel):
    item_id: str
    bbox: BBox
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
    page_count: int = 1  # pages of this store's flyer that have listings
    prev_page_id: str | None = None
    next_page_id: str | None = None


class FlyerGroup(BaseModel):
    """One product across this week's flyers, for the Flyers tab: brand/item/variant/size like a UserItem, plus
    its cheapest listing (tapping the row opens that store's page at that listing's tile)."""

    brand: str | None = None
    item: str
    variant: str | None = None
    size_qty: float | None = None
    size_unit: str | None = None
    cheapest: FlyerListing
    store_count: int
    saves_vs_next: float | None = None  # how much less cheapest is than the next store's price
    category: str | None = None


class FlyerBrowsePage(BaseModel):
    items: list[FlyerGroup]
    page: int
    page_size: int
    total: int
    stores: list[str]  # every store with a current listing, for the filter chips
    categories: list[str] = []  # categories among the listings (busiest first), for the filter chips
    ready: bool = True  # false while the first download for this postal code is still running


class AskRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    question: str = Field(min_length=2, max_length=300)
    conversation_id: str | None = None  # from the previous answer, to follow up


class AskResponse(BaseModel):
    """Genie's answer: its words, and the table behind them."""

    conversation_id: str
    answer: str | None = None
    description: str | None = None  # what the query does, in a sentence
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[str | None]] = []


class FlyersStatus(BaseModel):
    postal: str
    ready: bool  # false until the first download for this postal code has finished
    refreshing: bool
    listings: int
    stores: list[str]
    fetched_at: datetime | None = None
    source: Literal["flipp", "databricks", "canned"]
    error: str | None = None  # why the last refresh failed, if it did
    ask_enabled: bool = False  # Genie is set up, so POST /ask works


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
