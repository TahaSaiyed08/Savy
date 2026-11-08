"""This week's real flyers from Flipp, one feed per postal code, kept fresh while the API runs.

Reads never wait on the network: they get the copy in memory (or the one saved under apps/api/data/) and, when a
postal code has nothing yet, start a background fetch and return an empty list until it lands. A refresh checks
Flipp's flyer list first (one request) and only re-downloads stores whose flyer id changed, or everything once the
copy is a day old (Flipp corrects prices in place). A failed refresh keeps the previous copy.
"""
import asyncio
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from apps.api import databricks_sync, refine
from apps.api.models import FlyerItem
from shared import flipp

log = logging.getLogger(__name__)

# Timing knobs. A flyer is replaced weekly, but Flipp also fixes prices in place, so everything is re-downloaded
# once the copy is a day old; between those, an hourly look at Flipp's flyer list catches a store's new flyer.
ENABLED = os.getenv("REALDEAL_LIVE_FLYERS", "1") != "0"  # "0": canned flyers only (tests, CI, no network)
DATA = Path(__file__).parent / "data"
DEFAULT_POSTAL = os.getenv("DEFAULT_POSTAL_CODE", flipp.DEFAULT_POSTAL).replace(" ", "").upper()
LEGACY_SNAPSHOT = DATA / "flipp_snapshot.json"  # what `make flipp-snapshot` wrote before there were postal codes
STALE_AFTER = timedelta(hours=24)
RETRY_AFTER = timedelta(minutes=10)  # a stale copy that can't be refreshed must not hit Flipp on every request
CHECK_EVERY = 3600.0  # seconds between looks at Flipp's flyer list
# Canadian postal codes alternate letter/digit: A1A1A1. Flipp's API wants them without the space.
_POSTAL = re.compile(r"^[A-Z]\d[A-Z]\d[A-Z]\d$")


def normalize(raw: str | None) -> str | None:
    """'v6t 1z4' -> 'V6T1Z4'; None when it isn't a Canadian postal code."""
    code = re.sub(r"[\s-]", "", raw or "").upper()
    return code if _POSTAL.match(code) else None


# One Feed per postal code, held in memory and mirrored to apps/api/data/flipp_<POSTAL>.json so a restart is instant.
@dataclass
class Feed:
    postal: str
    rows: list[FlyerItem] = field(default_factory=list)
    flyers: dict[str, int] = field(default_factory=dict)  # store -> id of the Flipp flyer the rows came from
    fetched_at: datetime | None = None
    refreshing: bool = False  # a download is running, so don't start a second one
    tried_at: datetime | None = None  # last attempt, successful or not: spaces out retries after a failure
    error: str | None = None
    pages: dict[str, list[FlyerItem]] = field(default_factory=dict)  # page_id -> its tiles, an index for page lookups
    meta: dict[int, dict] = field(default_factory=dict)  # Flipp flyer id -> where its page images are

    def load(self, rows: list[FlyerItem], flyers: dict[str, int], fetched_at: datetime,
             meta: dict[int, dict] | None = None) -> None:
        self.pages = {}
        for f in rows:
            self.pages.setdefault(f.page_id, []).append(f)
        self.rows, self.flyers, self.fetched_at = rows, flyers, fetched_at
        self.meta = meta if meta is not None else self.meta


# All feeds, keyed by postal code. The lock guards the dict (and the `refreshing` flag), never a download: holding it
# across the network would block every request.
_feeds: dict[str, Feed] = {}
_lock = threading.Lock()


def _path(postal: str) -> Path:
    return DATA / f"flipp_{postal}.json"


def _flyer_ids(rows: list[FlyerItem]) -> dict[str, int]:
    """store -> Flipp flyer id, read back from page ids shaped flipp-<flyer id>-<page>."""
    return {f.store: int(f.page_id.split("-")[1]) for f in rows if f.page_id.startswith("flipp-")}


def _read(postal: str) -> Feed:
    # Reads the saved copy of one feed. Anything wrong with it (missing, corrupt, old format) returns an empty feed that
    # simply downloads again, so a bad file can never take the API down.
    feed = Feed(postal)
    path = _path(postal) if _path(postal).exists() else (LEGACY_SNAPSHOT if postal == DEFAULT_POSTAL else None)
    if path is None or not path.exists():
        return feed
    try:
        data = json.loads(path.read_text())
        # One unreadable row is skipped, not fatal: rows are validated on the way in (see FlyerItem's validators).
        rows, bad = [], 0
        for r in data["rows"]:
            try:
                rows.append(FlyerItem(**r))
            except ValidationError:
                bad += 1
        if bad:
            log.warning("skipped %d unreadable rows in %s", bad, path)
        saved = data.get("fetched_at")  # the legacy snapshot has none: use the file's age
        fetched = datetime.fromisoformat(saved) if saved else datetime.fromtimestamp(path.stat().st_mtime, UTC)
        # A copy made by an older parser is still shown right away, but marked as stale so it is rebuilt in the
        # background with the improved parsing.
        if data.get("parser") != flipp.PARSER_VERSION:  # still served, but counts as stale: downloaded again behind it
            fetched = datetime.min.replace(tzinfo=UTC)
        meta = {int(k): v for k, v in data.get("meta", {}).items()}
        feed.load(rows, {k: int(v) for k, v in data.get("flyers", {}).items()} or _flyer_ids(rows), fetched, meta)
    except Exception:
        log.warning("couldn't read %s; fetching fresh", path, exc_info=True)
    return feed


def _save(feed: Feed) -> None:
    # Everything needed to restart without the network: rows, which flyer each store is on, and where page images live.
    DATA.mkdir(parents=True, exist_ok=True)
    fetched = feed.fetched_at.isoformat() if feed.fetched_at else None
    body = {"postal": feed.postal, "parser": flipp.PARSER_VERSION, "fetched_at": fetched, "flyers": feed.flyers,
            "meta": {str(k): v for k, v in feed.meta.items()}, "rows": [f.model_dump(mode="json") for f in feed.rows]}
    tmp = _path(feed.postal).with_suffix(".tmp")
    tmp.write_text(json.dumps(body))
    tmp.replace(_path(feed.postal))  # atomic: a crash mid-write never leaves half a file


def feed(postal: str) -> Feed:
    """The feed for a postal code, read from disk the first time it is asked for. Never touches the network."""
    with _lock:
        if postal not in _feeds:
            _feeds[postal] = _read(postal)
        return _feeds[postal]


def put(postal: str, rows: list[FlyerItem]) -> None:
    """Install rows as a postal code's feed (the way a refresh does, minus the network)."""
    feed(postal).load(rows, _flyer_ids(rows), datetime.now(UTC))


def ready(postal: str) -> bool:
    f = feed(postal)
    return bool(f.rows) or (f.fetched_at is not None and not f.refreshing)


def _spawn(postal: str) -> None:
    threading.Thread(target=refresh, args=(postal,), name=f"flipp-{postal}", daemon=True).start()


def _wants_refresh(f: Feed) -> bool:
    if f.refreshing:
        return False
    if f.fetched_at is None:
        return True
    now = datetime.now(UTC)
    return now - f.fetched_at > STALE_AFTER and (f.tried_at is None or now - f.tried_at > RETRY_AFTER)


def items(postal: str) -> list[FlyerItem]:
    """Listings still valid today near this postal code. Empty while its first fetch runs; a copy that has gone stale
    (say, the API was off for days) is served as it is while a fresh one downloads."""
    f = feed(postal)
    if _wants_refresh(f):
        f.tried_at = datetime.now(UTC)
        _spawn(postal)
    today = date.today()
    return [r for r in f.rows if (r.valid_to or r.week_start + timedelta(days=6)) >= today]


def page(page_id: str) -> list[FlyerItem]:
    """Every tile on a flyer page, from whichever postal code's feed has it."""
    with _lock:
        feeds = list(_feeds.values())
    return next((f.pages[page_id] for f in feeds if page_id in f.pages), [])


def sibling_pages(tile: FlyerItem) -> list[str]:
    """page_ids of the flyer a tile is on, in page order."""
    with _lock:
        feeds = list(_feeds.values())
    for f in feeds:
        if tile.page_id in f.pages:
            ids = {r.page_id: r.page_no or 0 for r in f.rows
                   if r.store == tile.store and r.week_start == tile.week_start}
            return sorted(ids, key=lambda p: ids[p])
    return []


_PAGE_ID = re.compile(r"flipp-(\d+)-(\d+)")
_page_locks: dict[str, threading.Lock] = {}


def _page_source(page_id: str) -> tuple[dict, int] | None:
    """(the flyer's image info, page number) for a page whose real image Flipp can give us."""
    m = _PAGE_ID.fullmatch(page_id)
    if not m:
        return None
    with _lock:
        feeds = list(_feeds.values())
    for f in feeds:
        meta = f.meta.get(int(m[1]))
        if meta and m[2] in (meta.get("pages") or {}):
            return meta, int(m[2])
    return None


def page_aspect(page_id: str) -> float | None:
    """Width over height of the real page image, or None when there isn't one."""
    found = _page_source(page_id)
    if not found:
        return None
    left, right, top, bottom = found[0]["pages"][str(found[1])]
    return round((right - left) / (top - bottom), 4)


def _page_file(page_id: str) -> Path:
    return DATA / "pages" / f"{page_id.removeprefix('flipp-')}.jpg"


def page_jpeg(page_id: str) -> bytes | None:
    """The real printed page as a JPEG: from the saved copy, or stitched from Flipp's image tiles now and saved."""
    found = _page_source(page_id)
    if not found:
        return None
    path = _page_file(page_id)
    with _lock:
        lock = _page_locks.setdefault(page_id, threading.Lock())
    with lock:  # two people opening the same page download its tiles once
        if path.exists():
            return path.read_bytes()
        jpeg = flipp.render_page(*found)
        if jpeg:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(jpeg)
            tmp.replace(path)
        return jpeg


def warm_neighbours(page_id: str) -> None:
    """Draw the pages either side of this one, since the next thing someone does is swipe to them."""
    m = _PAGE_ID.fullmatch(page_id)
    if not m:
        return
    for n in (int(m[2]) + 1, int(m[2]) - 1):
        try:
            page_jpeg(f"flipp-{m[1]}-{n}")
        except Exception:
            log.warning("couldn't warm page %s of flyer %s", n, m[1], exc_info=True)


def _prune_pages() -> None:
    """Forget saved page images for flyers that are no longer anyone's current flyer."""
    with _lock:
        live = {fid for f in _feeds.values() for fid in f.flyers.values()}
    for path in (DATA / "pages").glob("*.jpg") if (DATA / "pages").exists() else []:
        if int(path.stem.split("-")[0]) not in live:
            path.unlink(missing_ok=True)


def refresh(postal: str, force: bool = False) -> None:
    """Bring a postal code up to date. Blocks for as long as the work takes: seconds to check, tens of seconds to
    download, minutes the first time the AI refiner names a whole flyer set.

    The saved copy, its time and Databricks are only touched when something actually changed: a new flyer, a store
    whose flyer ended, or names the refiner has just labelled. An hourly check that finds nothing does nothing."""
    f = feed(postal)
    with _lock:
        if f.refreshing:
            return
        f.refreshing = True
        f.tried_at = datetime.now(UTC)
    try:
        listed = flipp.grocery_flyers_for(postal)
        age = datetime.now(UTC) - f.fetched_at if f.fetched_at else None
        everything = force or age is None or age > STALE_AFTER
        old = {s: [r for r in f.rows if r.store == s] for s in f.flyers}
        rows, flyers, meta, downloaded = [], {}, {}, False
        for store, flyer in listed.items():
            if not everything and f.flyers.get(store) == flyer["id"] and old.get(store) and flyer["id"] in f.meta:
                rows += old[store]
                flyers[store] = flyer["id"]
                meta[flyer["id"]] = f.meta[flyer["id"]]
                continue
            try:
                fetched = flipp.fetch_flyer(flyer, store)
            except Exception:
                log.warning("couldn't fetch %s near %s; keeping what we had", store, postal, exc_info=True)
                if old.get(store):
                    rows += old[store]
                    flyers[store] = f.flyers[store]
                    if f.flyers[store] in f.meta:
                        meta[f.flyers[store]] = f.meta[f.flyers[store]]
                continue
            rows += [FlyerItem(**r) for r in fetched["rows"]]
            flyers[store] = flyer["id"]
            downloaded = True
            if fetched.get("meta"):
                meta[flyer["id"]] = fetched["meta"]
        if not rows:  # a blank answer from Flipp must not wipe the copy we have
            raise RuntimeError(f"no flyers found near {postal}")
        changed = downloaded or set(flyers) != set(f.flyers)
        if changed:
            f.load(rows, flyers, datetime.now(UTC), meta)  # people can see the new flyers now, before the AI step
            _save(f)
            _prune_pages()
            log.info("flyers near %s: %d listings from %s", postal, len(rows), ", ".join(flyers))
        f.error = None
        labelled = _label(f)
        if changed or labelled:
            _sync(postal, f.rows, f.fetched_at)
    except Exception as e:
        f.error = str(e) or type(e).__name__
        if f.fetched_at is None:
            f.fetched_at = datetime.now(UTC)  # nothing to show, but don't retry on every request; the next check will
        log.warning("flyer refresh near %s failed", postal, exc_info=True)
    finally:
        f.refreshing = False


def _label(f: Feed) -> bool:
    """Have the AI refiner name any listings it hasn't yet. True when it labelled some, which are then saved."""
    if not refine.enabled() or not any(r.category is None for r in f.rows):
        return False
    refined = refine.apply(f.rows)
    if all(a.category == b.category for a, b in zip(refined, f.rows, strict=True)):
        return False  # the model had nothing for them (down, or out of quota): they are asked again next time
    f.load(refined, f.flyers, f.fetched_at or datetime.now(UTC))
    _save(f)
    return True


def _sync(postal: str, rows: list[FlyerItem], fetched_at: datetime | None) -> None:
    """Hand the new listings to Databricks (when switched on) without making the refresh wait for the warehouse."""
    if not databricks_sync.enabled() or fetched_at is None:
        return

    def push() -> None:
        try:
            databricks_sync.push(postal, rows, fetched_at)
        except Exception:
            log.warning("couldn't sync flyers near %s to Databricks", postal, exc_info=True)

    threading.Thread(target=push, name=f"databricks-sync-{postal}", daemon=True).start()


def tick() -> None:
    """One pass of the hourly check over every postal code that has been asked for."""
    with _lock:
        postals = list(_feeds)
    for postal in postals:
        refresh(postal)


async def keep_fresh() -> None:
    """Runs for the life of the API: warm the default postal code at boot, then look for new flyers hourly."""
    if not ENABLED:
        return
    await asyncio.to_thread(items, DEFAULT_POSTAL)  # reads the saved copy (or starts the first fetch)
    while True:
        await asyncio.to_thread(tick)  # a copy saved before the API stopped may be a week behind
        await asyncio.sleep(CHECK_EVERY)
