import io
import uuid
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api import logic
from apps.api.extractors import ClaudeExtractor, get_extractor, sniff_media_type
from apps.api.main import app
from apps.api.mock_data import FLYER_ITEMS
from apps.api.models import Extraction

c = TestClient(app)
H = {"X-User-Id": str(uuid.uuid4())}
PNG = b"\x89PNG\r\n\x1a\nrest"
HEIC = b"\0\0\0\x18ftypheic\0\0\0\0"


def test_requires_user_id():
    assert c.get("/items").status_code == 422
    assert c.get("/items", headers={"X-User-Id": "not-a-uuid"}).status_code == 422


def test_mock_flow_end_to_end():
    assert len(c.get("/items", headers=H).json()) == 5
    deals = c.get("/deals", headers=H).json()
    assert {d["store"] for d in deals} >= {"No Frills", "Safeway"}

    r = c.post("/intake/receipt", headers=H, files={"file": ("r.jpg", io.BytesIO(b"x"), "image/jpeg")}).json()
    assert r["needs_confirm"] is True  # oat milk is under 0.6
    saved = c.post("/items", headers=H, json={"items": r["extraction"]["items"], "source": "receipt"}).json()
    assert len(saved) == 4 and len(c.get("/items", headers=H).json()) == 9

    b = c.get("/basket", headers=H).json()
    assert b["cheapest_store"] and b["split_total"] > 0 and "ramen" in b["unmatched"]


def test_delete_item_removes_it():
    before = c.get("/items", headers=H).json()
    target = before[0]["user_item_id"]
    assert c.delete(f"/items/{target}", headers=H).status_code == 204
    after = c.get("/items", headers=H).json()
    assert len(after) == len(before) - 1
    assert target not in {i["user_item_id"] for i in after}


def test_delete_unknown_id_is_idempotent():
    assert c.delete("/items/does-not-exist", headers=H).status_code == 204


def test_delete_cannot_remove_another_users_item():
    user_a, user_b = {"X-User-Id": str(uuid.uuid4())}, {"X-User-Id": str(uuid.uuid4())}
    c.post("/items", headers=user_a, json={"items": [{"item": "milk", "confidence": 1}], "source": "manual"})
    target = c.get("/items", headers=user_a).json()[0]["user_item_id"]

    assert c.delete(f"/items/{target}", headers=user_b).status_code == 204  # scoped by user_id: no-op

    after = c.get("/items", headers=user_a).json()
    assert target in {i["user_item_id"] for i in after}


def test_new_items_default_out_of_basket():
    h = {"X-User-Id": str(uuid.uuid4())}
    saved = c.post("/items", headers=h, json={"items": [{"item": "milk", "confidence": 1}],
                                               "source": "manual"}).json()
    assert saved[0]["in_basket"] is False


def test_set_basket_moves_item_in_and_out():
    h = {"X-User-Id": str(uuid.uuid4())}
    target = c.post("/items", headers=h, json={"items": [{"item": "milk", "confidence": 1}],
                                                "source": "manual"}).json()[0]["user_item_id"]

    r = c.post(f"/items/{target}/basket", headers=h, json={"in_basket": True})
    assert r.status_code == 200 and r.json()["in_basket"] is True
    assert c.get("/items", headers=h).json()[0]["in_basket"] is True  # still in Pantry, now flagged

    r = c.post(f"/items/{target}/basket", headers=h, json={"in_basket": False})
    assert r.status_code == 200 and r.json()["in_basket"] is False


def test_set_basket_404_for_unknown_item():
    assert c.post("/items/does-not-exist/basket", headers=H, json={"in_basket": True}).status_code == 404


def test_basket_only_includes_items_moved_into_it():
    h = {"X-User-Id": str(uuid.uuid4())}  # fresh user: 5 seeded items, all in_basket=True
    before = c.get("/basket", headers=h).json()
    assert before["cheapest_store"]

    target = c.get("/items", headers=h).json()[0]["user_item_id"]
    c.post(f"/items/{target}/basket", headers=h, json={"in_basket": False})

    after = c.get("/basket", headers=h).json()
    assert after["split_total"] <= before["split_total"]  # one fewer item to price in


def test_edit_item_changes_its_fields():
    h = {"X-User-Id": str(uuid.uuid4())}
    target = c.post("/items", headers=h, json={"items": [{"item": "milk", "confidence": 1}],
                                                "source": "manual"}).json()[0]["user_item_id"]

    r = c.patch(f"/items/{target}", headers=h,
                json={"brand": "Lucerne", "item": "milk", "variant": "1%", "size_qty": 2, "size_unit": "l",
                      "confidence": 1})
    assert r.status_code == 200
    updated = r.json()
    assert (updated["brand"], updated["variant"], updated["size_qty"]) == ("Lucerne", "1%", 2)

    refetched = next(i for i in c.get("/items", headers=h).json() if i["user_item_id"] == target)
    assert refetched["brand"] == "Lucerne"


def test_edit_item_404_for_unknown_item():
    body = {"item": "milk", "confidence": 1}
    assert c.patch("/items/does-not-exist", headers=H, json=body).status_code == 404


def test_rejects_non_image_receipt():
    r = c.post("/intake/receipt", headers=H, files={"file": ("r.txt", io.BytesIO(b"x"), "text/plain")})
    assert r.status_code == 415


def test_media_type_comes_from_bytes_not_the_label():
    assert sniff_media_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert sniff_media_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert sniff_media_type(b"GIF89a") == "image/gif"
    assert sniff_media_type(b"RIFF\0\0\0\0WEBPrest") == "image/webp"
    assert sniff_media_type(b"RIFF\0\0\0\0WAVErest") is None
    assert sniff_media_type(b"") is None
    assert sniff_media_type(HEIC) is None


def _claude_with_fake_client():
    calls = []
    ext = ClaudeExtractor.__new__(ClaudeExtractor)
    ext.model = "test-model"
    ext.client = SimpleNamespace(messages=SimpleNamespace(parse=lambda **kw: calls.append(kw) or SimpleNamespace(
        stop_reason="end_turn", parsed_output=Extraction(items=[]))))
    return ext, calls


def test_claude_sends_the_sniffed_media_type():
    ext, calls = _claude_with_fake_client()
    ext.extract("receipt", image=PNG, media_type="image/jpeg")
    image_block = calls[0]["messages"][0]["content"][0]
    assert image_block["source"]["media_type"] == "image/png"


def test_heic_is_rejected_before_any_paid_call():
    ext, calls = _claude_with_fake_client()
    with pytest.raises(HTTPException) as e:
        ext.extract("receipt", image=HEIC, media_type="image/heic")
    assert e.value.status_code == 415 and not calls


def test_save_survives_matching_failure(monkeypatch):
    from apps.api import databricks_sql, store
    from apps.api.models import SaveItems

    writes, search_calls, fallback_calls = [], [], []

    def search_down():
        search_calls.append(1)
        raise RuntimeError("AI Search index unavailable")

    def fallback_down(sql, **p):
        fallback_calls.append(sql)
        raise RuntimeError("flyer_items unavailable")

    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "_unmatched", {})
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append(sql))
    monkeypatch.setattr(databricks_sql, "query", fallback_down)
    monkeypatch.setattr(databricks_sql, "_client", search_down)
    uid = uuid.uuid4()
    saved = store.add_items(uid, SaveItems(source="manual", items=[{"item": "milk", "confidence": 0.9}]))
    assert len(saved) == 1 and any("INSERT INTO user_items" in s for s in writes)
    assert search_calls, "matching never tried AI Search"
    assert fallback_calls, "matching never tried the LIKE fallback"
    assert store._unmatched[uid][1] == saved  # queued for retry


def test_save_uses_a_fixed_number_of_statements(monkeypatch):
    import json

    from apps.api import databricks_sql, store
    from apps.api.models import SaveItems

    writes, reads = [], []

    def no_index():
        raise RuntimeError("no AI Search index")

    def like(sql, rows, fresh=False):
        reads.append(sql)
        return [{"user_item_id": r["user_item_id"], "item_id": f"f-{r['item']}", "brand": "Purex"}
                for r in json.loads(rows)]

    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append((sql, p)))
    monkeypatch.setattr(databricks_sql, "query", like)
    monkeypatch.setattr(databricks_sql, "_client", no_index)
    items = [{"item": f"thing {n}", "confidence": 0.9} for n in range(9)] + [
        {"brand": "PC", "item": "bathroom tissue", "confidence": 0.9}]
    store.add_items(uuid.uuid4(), SaveItems(source="receipt", items=items))

    assert len(reads) == 1 and len(writes) == 3  # users MERGE, user_items INSERT, user_item_matches INSERT
    inserted = json.loads(next(p["rows"] for s, p in writes if "INSERT INTO user_items" in s))
    assert len(inserted) == 10 and inserted[0]["added_at"]
    matches = json.loads(next(p["rows"] for s, p in writes if "user_item_matches" in s))
    assert len(matches) == 9  # the PC item is dropped by the brand rule (flyer brand is Purex)


def test_flipp_live_fallback_fires_when_search_and_like_both_miss(monkeypatch):
    import json

    from apps.api import databricks_sql, store
    from apps.api.models import SaveItems
    from shared import flipp

    writes = []

    def no_index():
        raise RuntimeError("no AI Search index")

    def empty_like(sql, rows):
        return []  # LIKE finds nothing either

    def fake_search(q):
        assert q == "milk 2% 4 l"
        return [{"id": 999, "flyer_id": 123, "merchant_name": "Safeway",
                "name": "Lucerne 2% milk 4 L", "current_price": 5.99}]

    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "_flipp_cache", {})
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append((sql, p)))
    monkeypatch.setattr(databricks_sql, "query", empty_like)
    monkeypatch.setattr(databricks_sql, "_client", no_index)
    monkeypatch.setattr(flipp, "search", fake_search)

    store.add_items(uuid.uuid4(), SaveItems(
        source="manual", items=[{"item": "milk", "variant": "2%", "size_qty": 4, "size_unit": "l", "confidence": 0.9}]))

    flyer_writes = [p for s, p in writes if "INSERT INTO flyer_items" in s]
    match_writes = [p for s, p in writes if "INSERT INTO user_item_matches" in s]
    assert flyer_writes and match_writes
    rows = json.loads(flyer_writes[0]["rows"])
    assert rows[0]["item_id"] == "flipp-live-999" and rows[0]["store"] == "Safeway"
    matches = json.loads(match_writes[0]["rows"])
    assert matches[0]["flyer_item_id"] == "flipp-live-999"


def test_receipt_photo_and_row_are_saved(monkeypatch):
    from datetime import date

    from apps.api import databricks_sql, store

    uploads, writes = [], []
    files = SimpleNamespace(upload=lambda path, f, overwrite: uploads.append((path, f.read(), overwrite)))
    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(databricks_sql, "_client", lambda: SimpleNamespace(files=files))
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append(p))
    uid = uuid.uuid4()
    jpeg = b"\xff\xd8\xff\xe0rest"

    store.save_receipt(uid, jpeg, Extraction(items=[], store="Superstore", bought_at="2026-11-06", total=100.0))
    store.save_receipt(uid, PNG, Extraction(items=[], bought_at="06/11/2026"))

    assert uploads[0][0].startswith(f"/Volumes/realdeal/core/uploads/receipts/{uid}/")
    assert uploads[0][0].endswith(".jpg") and uploads[0][1:] == (jpeg, False) and uploads[1][0].endswith(".png")
    assert writes[0]["total"] == 100.0 and writes[0]["bought_at"] == date(2026, 11, 6)
    assert writes[0]["image_path"] == uploads[0][0] and writes[1]["bought_at"] is None


def test_receipt_intake_saves_in_background(monkeypatch):
    from apps.api import store

    saved = []
    monkeypatch.setattr(store, "save_receipt", lambda uid, image, x: saved.append((uid, image, x.store)))
    r = c.post("/intake/receipt", headers=H, files={"file": ("r.jpg", io.BytesIO(b"\xff\xd8\xffx"), "image/jpeg")})
    assert r.status_code == 200 and saved == [(uuid.UUID(H["X-User-Id"]), b"\xff\xd8\xffx", "Save-On-Foods")]


def test_failed_matching_is_retried_on_next_deals(monkeypatch):
    import json

    from apps.api import databricks_sql, store
    from apps.api.models import SaveItems

    up, writes = {"db": False}, []

    def query(sql, **p):
        if "inline" not in sql:
            return []  # the my_deals read
        if not up["db"]:
            raise RuntimeError("warehouse down")
        return [{"user_item_id": r["user_item_id"], "item_id": "f1", "brand": None} for r in json.loads(p["rows"])]

    def no_index():
        raise RuntimeError("no AI Search index")

    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "_unmatched", {})
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append((sql, p)))
    monkeypatch.setattr(databricks_sql, "query", query)
    monkeypatch.setattr(databricks_sql, "_client", no_index)
    uid = uuid.uuid4()
    saved = store.add_items(uid, SaveItems(source="manual", items=[{"item": "milk", "confidence": 0.9}]))
    assert uid in store._unmatched

    store.list_deals(uid)  # still down: kept, and backed off so the next call doesn't retry
    assert store._unmatched[uid][1] == saved and not any("user_item_matches" in s for s, _ in writes)

    up["db"] = True
    monkeypatch.setattr(store, "RETRY_AFTER", 0.0)
    store._unmatched[uid] = (0.0, saved)
    store.list_deals(uid)
    inserted = [json.loads(p["rows"]) for s, p in writes if "user_item_matches" in s]
    assert inserted == [[{"user_item_id": saved[0].user_item_id, "flyer_item_id": "f1", "match_score": 0.75}]]
    assert uid not in store._unmatched and "MERGE INTO user_item_matches" in next(
        s for s, _ in writes if "user_item_matches" in s)


def test_weekly_rematch_sweeps_each_flyer_change_once(monkeypatch):
    from datetime import UTC, datetime

    from apps.api import databricks_sql, store

    state = {"sig": "Save-On-Foods=2026-11-05:276:-347", "fail": False}
    batches, item_reads = [], []
    items = [{"user_item_id": f"u{n}", "user_id": str(uuid.uuid4()), "item": "milk", "source": "manual",
              "added_at": datetime.now(UTC)} for n in range(250)]

    def query(sql, **p):
        if sql == store._FLYER_SIGNATURE:
            return [{"sig": state["sig"]}]
        item_reads.append(state["sig"])
        return items

    def match(batch):
        if state["fail"]:
            raise RuntimeError("warehouse down")
        batches.append(len(batch))

    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "_swept_flyers", None)
    monkeypatch.setattr(store, "_match_and_store", match)
    monkeypatch.setattr(databricks_sql, "query", query)

    assert store.rematch_if_new_week() == 250 and batches == [100, 100, 50]
    assert store.rematch_if_new_week() == 0 and len(item_reads) == 1  # unchanged flyers: no item scan

    state["sig"] = "Save-On-Foods=2026-11-05:290:812"  # same week, later pages arrived
    assert store.rematch_if_new_week() == 250 and len(item_reads) == 2

    state.update(sig="PriceSmart=2026-11-07:40:5,Save-On-Foods=2026-11-05:290:812", fail=True)  # new store flyer
    with pytest.raises(RuntimeError):
        store.rematch_if_new_week()
    state["fail"] = False
    assert store.rematch_if_new_week() == 250  # the failed sweep is retried, not marked done
    assert len(item_reads) == 4


def test_search_keeps_only_current_flyers_top_three_per_store(monkeypatch):
    import json
    from datetime import UTC, datetime

    from apps.api import databricks_sql, store
    from apps.api.models import UserItem

    hits = [["old1", None, 0.99], ["old2", None, 0.98], ["old3", None, 0.97]]  # last week's rows rank first
    hits += [[f"sof{n}", None, 0.9 - n / 100] for n in range(5)] + [["ss1", None, 0.8]]
    index = SimpleNamespace(query_index=lambda **kw: SimpleNamespace(result=SimpleNamespace(data_array=hits)))
    current = [{"item_id": f"sof{n}", "store": "Save-On-Foods"} for n in range(5)]
    current += [{"item_id": "ss1", "store": "Superstore"}]
    writes, reads = [], []

    def query(sql, **p):
        reads.append(sql)
        assert "inline" not in sql, "the LIKE fallback must not run when the index answered"
        return current

    monkeypatch.setattr(databricks_sql, "_client", lambda: SimpleNamespace(vector_search_indexes=index))
    monkeypatch.setattr(databricks_sql, "query", query)
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append(p))
    store._match_and_store([UserItem(user_item_id="u1", user_id=uuid.uuid4(), item="yogurt", source="manual",
                                     added_at=datetime.now(UTC))])

    saved = [m["flyer_item_id"] for m in json.loads(writes[0]["rows"])]
    assert saved == ["sof0", "sof1", "sof2", "ss1"] and len(reads) == 1


def test_fresh_query_fails_closed_instead_of_serving_cache(monkeypatch):
    from apps.api import databricks_sql

    up = {"ok": True}

    def run(sql, params):
        if not up["ok"]:
            raise RuntimeError("warehouse down")
        return [{"n": 1}]

    monkeypatch.setattr(databricks_sql, "_run", run)
    monkeypatch.setattr(databricks_sql, "_last_good", databricks_sql.OrderedDict())
    assert databricks_sql.query("SELECT 1") == [{"n": 1}]
    up["ok"] = False
    assert databricks_sql.query("SELECT 1") == [{"n": 1}]  # screens still get the last good result
    with pytest.raises(RuntimeError):
        databricks_sql.query("SELECT 1", fresh=True)


def test_sweep_does_not_mark_done_from_a_cached_item_scan(monkeypatch):
    from datetime import UTC, datetime

    from apps.api import databricks_sql, store

    state = {"sig": "Save-On-Foods=2026-11-05:276:1", "items_up": True}
    item = {"user_item_id": "u1", "user_id": str(uuid.uuid4()), "item": "milk", "source": "manual",
            "added_at": datetime.now(UTC)}

    def run(sql, params):  # only the warehouse is faked; the real query() and its cache are exercised
        if sql == store._FLYER_SIGNATURE:
            return [{"sig": state["sig"]}]
        if not state["items_up"]:
            raise RuntimeError("user_items scan timed out")
        return [item]

    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "_swept_flyers", None)
    monkeypatch.setattr(store, "_match_and_store", lambda batch: None)
    monkeypatch.setattr(databricks_sql, "_run", run)
    monkeypatch.setattr(databricks_sql, "_last_good", databricks_sql.OrderedDict())

    assert store.rematch_if_new_week() == 1  # caches a good item scan
    state.update(sig="Save-On-Foods=2026-11-12:300:2", items_up=False)
    with pytest.raises(RuntimeError):
        store.rematch_if_new_week()  # must not re-match the cached snapshot
    assert store._swept_flyers == "Save-On-Foods=2026-11-05:276:1"  # new flyers not marked swept


def test_every_current_store_gets_matched_via_search_or_fallback(monkeypatch):
    import json
    from datetime import UTC, datetime

    from apps.api import databricks_sql, store
    from apps.api.models import UserItem

    # Global top-N is all Save-On; No Frills is in the index (store-filtered search finds it); T&T isn't synced yet.
    by_store = {None: [["sof1", None, 0.9], ["sof2", None, 0.85]], "No Frills": [["nf1", None, 0.8]], "T&T": []}
    searches = []

    def query_index(**kw):
        s = json.loads(kw["filters_json"])["store"][0] if "filters_json" in kw else None
        searches.append(s)
        return SimpleNamespace(result=SimpleNamespace(data_array=by_store[s]))

    current = [{"item_id": "sof1", "store": "Save-On-Foods"}, {"item_id": "sof2", "store": "Save-On-Foods"},
               {"item_id": "nf1", "store": "No Frills"}, {"item_id": "tt1", "store": "T&T"}]
    like_stores, writes = [], []

    def query(sql, **p):
        if "inline" in sql:  # LIKE fallback
            rows = json.loads(p["rows"])
            like_stores.extend(r["stores"] for r in rows)
            return [{"user_item_id": rows[0]["user_item_id"], "item_id": "tt1", "brand": None}]
        return current

    monkeypatch.setattr(databricks_sql, "_client",
                        lambda: SimpleNamespace(vector_search_indexes=SimpleNamespace(query_index=query_index)))
    monkeypatch.setattr(databricks_sql, "query", query)
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append(p))
    store._match_and_store([UserItem(user_item_id=f"u{n}", user_id=uuid.uuid4(), item="yogurt", source="manual",
                                     added_at=datetime.now(UTC)) for n in (1, 2)])

    from collections import Counter
    # Per item: one global search; per store: one probe; per item again only for stores the index holds.
    # Save-On needed no top-up, and unsynced T&T is probed once, not searched per item.
    assert Counter(searches) == {None: 2, "No Frills": 3, "T&T": 1}
    assert like_stores == [["T&T"], ["T&T"]]  # fallback only for the store the index can't answer
    saved = {(m["user_item_id"], m["flyer_item_id"]) for m in json.loads(writes[0]["rows"])}
    assert saved == {(u, f) for u in ("u1", "u2") for f in ("sof1", "sof2", "nf1")} | {("u1", "tt1")}


def test_weekly_rematch_does_nothing_in_mock_mode(monkeypatch):
    from apps.api import store

    monkeypatch.setattr(store, "MOCK", True)
    assert store.rematch_if_new_week() == 0


def test_unknown_extractor_is_rejected(monkeypatch):
    monkeypatch.setenv("EXTRACTOR", "gpt")
    with pytest.raises(ValueError, match="mock, claude, databricks"):
        get_extractor()


def test_bad_extractor_config_fails_at_startup(monkeypatch):
    monkeypatch.setenv("EXTRACTOR", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"), TestClient(app):
        pass


def test_health_reports_extractor(monkeypatch):
    monkeypatch.delenv("EXTRACTOR", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert c.get("/health").json()["extractor"] == "MockExtractor"


class _Failing:
    def __init__(self, exc):
        self.exc = exc

    def extract(self, mode, **kw):
        raise self.exc


@pytest.mark.parametrize("exc, status", [
    (anthropic.APIStatusError("overloaded", response=httpx.Response(
        529, request=httpx.Request("POST", "https://api.anthropic.com")), body=None), 502),
    (RuntimeError("extraction failed: stop_reason=refusal"), 422),
])
def test_extractor_failures_become_client_errors(exc, status):
    app.dependency_overrides[get_extractor] = lambda: _Failing(exc)
    try:
        r = c.post("/intake/manual", headers=H, json={"text": "milk"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == status, r.text


def test_voice_uses_mock_transcript():
    r = c.post("/intake/voice", headers=H, files={"file": ("a.webm", io.BytesIO(b"x"), "audio/webm")}).json()
    assert r["transcript"] and r["extraction"]["items"][0]["size_unit"] == "ml"


def _voice():
    return c.post("/intake/voice", headers=H, files={"file": ("a.webm", io.BytesIO(b"x"), "audio/webm")})


def _elevenlabs_replies(status=200, body=b'{"text": "milk"}', exc=None):
    def post(url, **kw):
        if exc:
            raise exc
        return httpx.Response(status, content=body, request=httpx.Request("POST", url))
    return post


@pytest.mark.parametrize("reply", [
    _elevenlabs_replies(exc=httpx.ConnectError("ElevenLabs unreachable")),
    _elevenlabs_replies(status=503, body=b'{"detail": "busy"}'),
    _elevenlabs_replies(body=b"<html>not json</html>"),
    _elevenlabs_replies(body=b'{"words": []}'),
    _elevenlabs_replies(body=b'{"text": null}'),
    _elevenlabs_replies(body=b'["milk"]'),
], ids=["unreachable", "http-503", "invalid-json", "missing-text", "null-text", "not-an-object"])
def test_speech_service_failures_are_a_logged_502(monkeypatch, caplog, reply):
    from apps.api import stt

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(stt.httpx, "post", reply)
    with caplog.at_level("WARNING", logger="apps.api.main"):
        r = _voice()
    assert r.status_code == 502 and "Speech service" in r.json()["detail"]
    assert any("speech-to-text failed" in m and H["X-User-Id"] in m for m in caplog.messages)


def test_speech_service_transcript_is_returned(monkeypatch):
    from apps.api import stt

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(stt.httpx, "post", _elevenlabs_replies(body=b'{"text": "add eggs"}'))
    assert _voice().json()["transcript"] == "add eggs"


def test_silent_recording_skips_extraction(monkeypatch):
    from apps.api import stt

    monkeypatch.setattr(stt, "transcribe", lambda *a: "  ")
    app.dependency_overrides[get_extractor] = lambda: _Failing(AssertionError("extractor must not be called"))
    try:
        r = _voice()
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422 and "catch" in r.json()["detail"]


def _user(**kw):
    base = dict(user_item_id="u1", user_id=uuid.uuid4(), source="manual", added_at="2026-11-07T00:00:00Z")
    return logic.UserItem(**{**base, **kw})


def test_brand_rule_blocks_other_brands():
    pc = _user(brand="PC", item="chicken thigh")
    stores = {d.store for d in logic.deals_for([pc], FLYER_ITEMS)}
    assert stores == {"Real Canadian Superstore", "No Frills"}  # Western Family at Save-On is excluded


def test_basket_scales_unit_price_to_user_size_and_splits():
    milk, bananas = _user(item="milk", variant="2%", size_qty=4, size_unit="l"), _user(
        user_item_id="u2", item="banana", size_qty=2, size_unit="lb")
    b = logic.basket([milk, bananas], logic.deals_for([milk, bananas], FLYER_ITEMS))
    split = {s.item_label.split()[0]: (s.store, s.cost) for s in b.split}
    assert split["milk"] == ("No Frills", 5.79)
    assert split["banana"] == ("T&T", 1.18)  # 2 lb at $0.59/lb
    assert b.unmatched == []
    # Safeway carries both ($5.99 + 2 lb x $0.69); split is No Frills milk + T&T bananas.
    assert b.cheapest_store == "Safeway" and b.delta == round(5.99 + 1.38 - 5.79 - 1.18, 2)


def test_basket_totals_are_sane_for_counted_items():
    eggs = _user(item="eggs", variant="large", size_qty=12, size_unit="ea")
    b = logic.basket([eggs], logic.deals_for([eggs], FLYER_ITEMS))
    assert {s.store: s.total for s in b.stores}["No Frills"] == 3.99


def test_intake_is_rate_limited_per_ip(monkeypatch):
    from apps.api import main

    monkeypatch.setattr(main, "INTAKE_LIMIT", 3)
    main._hits.clear(), main._global.clear()
    body = {"text": "milk"}
    codes = [c.post("/intake/manual", headers=H, json=body).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert c.get("/deals", headers=H).status_code == 200  # reads are never limited
    main._hits.clear(), main._global.clear()


def test_global_cap_backstops_many_ips(monkeypatch):
    from apps.api import main

    monkeypatch.setattr(main, "INTAKE_GLOBAL_LIMIT", 2)
    main._hits.clear(), main._global.clear()
    ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]
    codes = [TestClient(app, client=(ip, 1)).post("/intake/manual", headers=H, json={"text": "x"}).status_code
             for ip in ips]
    assert codes == [200, 200, 429]
    assert len(main._hits) == 2  # rejected clients cost no memory
    main._hits.clear(), main._global.clear()


def test_ipv6_clients_share_a_slash_64():
    from apps.api import main

    a, b = main._client_key("2001:db8:1:2::1"), main._client_key("2001:db8:1:2:ffff::9")
    assert a == b != main._client_key("2001:db8:1:3::1")
    assert main._client_key("10.0.0.7") == "10.0.0.7"
