"""Cleans up flyer product names with a language model hosted on Databricks.

Flipp gives one free-text name per tile ("NO NAME® NATURALLY IMPERFECT™ POTATOES"). The regex parser in
shared/flipp.py splits it well enough to find sizes, but it can't tell a product from its flavour or a brand from a
line name. The model does: brand "No Name", item "Potatoes", variant "Naturally Imperfect", category "Produce".

Only brand, item, variant and category come from the model; sizes and prices stay with the parser, which the model
can't see. Answers are cached on disk by input, so a name is asked about once ever: that keeps a product's identity
stable from refresh to refresh (items added from a flyer depend on it) and keeps the Databricks bill small.
A model failure leaves the parser's answer in place and is retried on a later refresh.
"""
import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from apps.api import logic
from apps.api.models import FlyerItem

log = logging.getLogger(__name__)

# The fixed menu of categories the model must pick from. The Flyers tab's chips and the Genie instructions use the
# same list, so adding one here means updating those too.
CATEGORIES = ["Dairy & eggs", "Produce", "Meat & seafood", "Bakery", "Pantry", "Snacks & sweets", "Frozen",
              "Drinks", "Household", "Health & beauty", "Other"]
CACHE_FILE = Path(__file__).parent / "data" / "refined.json"
MODEL = os.getenv("REFINE_MODEL", "databricks-llama-4-maverick")
# Cost and rate-limit controls: 25 names per call keeps replies short enough to parse reliably, 3 calls in flight is
# gentle on the shared endpoint, and a failed call is retried a few times with a growing pause.
BATCH = 25  # names per model call
PARALLEL = 3  # calls in flight at once
RETRIES = 3
MAX_CACHED = 50_000  # the answer cache is trimmed oldest-first beyond this, so it can't grow without bound
_NEEDS = ("DATABRICKS_HOST", "DATABRICKS_TOKEN")

# The instruction sent to the model. It asks for strict JSON in a fixed shape (one object per listing, same order) so
# parse() can check the reply. Sizes are deliberately left out: the regex parser reads those more reliably.
_PROMPT = """Parse each grocery flyer listing into brand, item, variant and category.

- brand: the maker or store brand, like "Kraft", "PC", "no name", "Western Family", or null. Each listing may come with
  a brand hint from the flyer: use it when the name does not make the brand clear.
- item: what the product is, as a short plain noun phrase in Title Case, without brand or size
  ("Peanut Butter", "Ice Cream", "Salmon Lox", "Potatoes").
- variant: flavour, fat percentage, type or other qualifier ("2%", "Eggnog", "Naturally Imperfect", "Lactose Free"),
  or null.
- category: exactly one of: {categories}.
- When a name lists several products joined by "or", describe the first one.
- Ignore sizes, counts, prices and promotion text.

Return ONLY a JSON array with one object per listing, in the same order, with keys brand, item, variant, category.

Listings:
{listings}"""

_lock = threading.Lock()
_cache: dict[str, dict] | None = None


def enabled() -> bool:
    return os.getenv("REALDEAL_AI_REFINE", "1") != "0" and all(os.getenv(k) for k in _NEEDS)


def _key(brand: str | None, name: str) -> str:
    # The cache key is the flyer's own text (name + brand hint, lowercased): the same wording always gets the same
    # answer, so a product's identity doesn't wobble between refreshes.
    return hashlib.sha1(f"{brand or ''}|{name}".lower().encode()).hexdigest()[:16]


def _load() -> dict[str, dict]:
    global _cache
    with _lock:
        if _cache is None:
            try:
                _cache = json.loads(CACHE_FILE.read_text())
            except (OSError, ValueError):
                _cache = {}
        return _cache


def _remember(new: dict[str, dict]) -> None:
    # Written after every batch, via a temp file and rename, so an interrupted run keeps what it already learned.
    cache = _load()
    with _lock:
        cache.update(new)
        while len(cache) > MAX_CACHED:
            del cache[next(iter(cache))]  # oldest first
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache))
        tmp.replace(CACHE_FILE)


def _text(v) -> str | None:
    """A short non-empty string, or None."""
    return (v.strip()[:80] or None) if isinstance(v, str) else None


def parse(reply: str, expected: int) -> list[dict | None]:
    """The model's reply as one cleaned dict per listing. None for an entry that can't be trusted (or all of them
    when the reply isn't the right shape): those listings keep the parser's answer."""
    # Models often wrap JSON in prose or code fences; take everything from the first "[" to the last "]".
    try:
        data = json.loads(reply[reply.index("["): reply.rindex("]") + 1])
    except ValueError:
        return [None] * expected
    if not isinstance(data, list) or len(data) != expected:  # off by one would give each name its neighbour's answer
        return [None] * expected
    out = []
    for d in data:
        item = _text(d.get("item")) if isinstance(d, dict) else None
        if not item:
            out.append(None)
            continue
        category = d.get("category")
        out.append({"brand": _text(d.get("brand")), "item": item, "variant": _text(d.get("variant")),
                    "category": category if category in CATEGORIES else "Other"})
    return out


def _call(batch: list[dict]) -> list[dict | None]:
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

    from apps.api import databricks_sql as db

    prompt = _PROMPT.format(categories=", ".join(f'"{c}"' for c in CATEGORIES), listings=json.dumps(batch))
    for attempt in range(RETRIES):
        try:
            r = db._client().serving_endpoints.query(
                MODEL, messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)],
                max_tokens=70 * len(batch) + 300, temperature=0)
            return parse(r.choices[0].message.content or "", len(batch))
        except Exception:
            if attempt == RETRIES - 1:
                log.warning("model call failed for %d flyer names", len(batch), exc_info=True)
                return [None] * len(batch)
            # Pauses of 2 s, then 4 s. Only the final failure is logged, so a brief rate limit doesn't spam the log.
            time.sleep(2 ** (attempt + 1))  # rate limited or briefly down: back off and try again
    return [None] * len(batch)


def _believable(item: str, name: str, brand: str | None) -> bool:
    """The model must be describing this listing: its item shares a word with what the flyer printed."""
    # A guard against a confused model: a plausible answer must share a word with what the flyer actually printed, so
    # a reply meant for a different listing (or invented) is rejected rather than applied.
    words = logic._words(f"{name} {brand or ''}")
    return any(any(w.startswith(t) or t.startswith(w) for w in words) for t in logic._words(item))


def merge(row: FlyerItem, parsed: dict) -> FlyerItem:
    """The model's brand, item, variant and category over the parser's. Where the model says nothing the parser's
    brand and variant stay (the flyer's own brand hint is often right when the model can't tell)."""
    return row.model_copy(update={
        "brand": parsed["brand"] or row.brand, "item": parsed["item"],
        "variant": parsed["variant"] or row.variant, "category": parsed["category"],
    })


def apply(rows: list[FlyerItem]) -> list[FlyerItem]:
    """The rows with the model's names for every listing it hasn't been asked about yet (and has an answer for)."""
    # 1) collect distinct names not yet labelled, 2) ask the model for the ones not in the cache, in parallel batches,
    # 3) merge every cached answer back into the rows.
    cache = _load()
    pending = {}
    for r in rows:
        if r.category is None and r.raw_text:
            pending.setdefault(_key(r.brand, r.raw_text), {"name": r.raw_text, "brand": r.brand})
    todo = {k: v for k, v in pending.items() if k not in cache}
    if todo:
        keys = list(todo)
        batches = [keys[i: i + BATCH] for i in range(0, len(keys), BATCH)]
        asked = 0

        def work(ks: list[str]) -> None:
            nonlocal asked
            answers = _call([todo[k] for k in ks])
            # An answer that doesn't fit the name (a bare brand like "Smart" the model can only guess at) is
            # remembered as {} so it is not asked again every refresh; a failed call (None) is retried later.
            got = {k: (a if _believable(a["item"], todo[k]["name"], todo[k]["brand"]) else {})
                   for k, a in zip(ks, answers, strict=True) if a}
            if got:
                _remember(got)  # saved as each batch lands, so a long run that is interrupted loses little
            asked += sum(1 for a in got.values() if a)

        with ThreadPoolExecutor(PARALLEL) as pool:
            list(pool.map(work, batches))
        log.info("refined %d of %d new flyer names", asked, len(todo))
        cache = _load()
    out = []
    for r in rows:
        hit = cache.get(_key(r.brand, r.raw_text)) if r.category is None and r.raw_text else None
        out.append(merge(r, hit) if hit else r)
    return out
