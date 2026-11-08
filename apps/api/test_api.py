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
    items = c.get("/items", headers=H).json()
    assert len(items) == 5
    milk = next(i for i in items if i["item"] == "milk")
    assert milk["in_basket"] and milk["cheapest"]["store"] == "Safeway"
    assert next(i for i in items if i["item"] == "ramen")["missing"] == ["brand", "variant", "size"]
    deals = c.get("/deals", headers=H).json()
    assert {d["store"] for d in deals} >= {"No Frills", "Safeway"}

    r = c.post("/intake/receipt", headers=H, files={"file": ("r.jpg", io.BytesIO(b"x"), "image/jpeg")}).json()
    assert r["needs_confirm"] is True  # oat milk is under 0.6
    saved = c.post("/items", headers=H, json={"items": r["extraction"]["items"], "source": "receipt"}).json()
    assert len(saved) == 4 and len(c.get("/items", headers=H).json()) == 9

    b = c.get("/basket", headers=H).json()
    assert b["cheapest_store"] and b["split_total"] > 0 and b["unmatched"] == []


def test_edit_and_move_to_basket():
    h = {"X-User-Id": str(uuid.uuid4())}
    ramen = next(i for i in c.get("/items", headers=h).json() if i["item"] == "ramen")
    url = f"/items/{ramen['user_item_id']}"
    r = c.patch(url, headers=h, json={"brand": "Nissin", "item": "instant noodle", "variant": "spicy",
                                      "size_qty": 500, "size_unit": "g"}).json()
    assert r["missing"] == [] and r["cheapest"]["store"] == "T&T" and not r["in_basket"]
    assert c.patch(url, headers=h, json={"in_basket": True}).json()["brand"] == "Nissin"  # other fields kept
    basket = c.get("/basket", headers=h).json()
    assert "Nissin instant noodle spicy 500 g" in [s["item_label"] for s in basket["split"]]
    assert c.patch(url, headers=h, json={"item": ""}).status_code == 422
    assert c.patch("/items/nope", headers=h, json={"in_basket": True}).status_code == 404
    other = {"X-User-Id": str(uuid.uuid4())}
    assert c.patch(url, headers=other, json={"in_basket": False}).status_code == 404


def test_flyer_page_has_the_listing_tile_and_dates():
    milk = next(i for i in c.get("/items", headers=H).json() if i["item"] == "milk")["cheapest"]
    p = c.get(f"/flyer-pages/{milk['page_id']}").json()
    tile = next(t for t in p["tiles"] if t["item_id"] == milk["flyer_item_id"])
    assert tile["bbox"] == milk["bbox"] and p["store"] == "Safeway" and p["aspect"]
    assert (p["valid_from"], p["valid_to"]) == ("2026-11-05", "2026-11-11") and p["image_url"] is None
    assert c.get("/flyer-pages/nope").status_code == 404
    assert c.get(f"/flyer-pages/{milk['page_id']}/image").status_code == 404  # mock pages are tiles only


def test_volume_page_image_is_served(monkeypatch):
    from apps.api import store

    page = [logic.FlyerItem(item_id="f", page_id="p9", store="Save-On-Foods", week_start="2026-11-05", item="milk",
                            bbox=[0, 0, 1, 1], image_path="/Volumes/realdeal/core/flyers/save_on_foods/x/009.jpg")]
    monkeypatch.setattr(store, "page_tiles", lambda pid: page if pid == "p9" else [])
    monkeypatch.setattr(store, "page_image", lambda path: b"\xff\xd8\xffjpeg")
    assert c.get("/flyer-pages/p9").json()["image_url"] == "/flyer-pages/p9/image"
    r = c.get("/flyer-pages/p9/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content.startswith(b"\xff")


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


def test_save_uses_a_fixed_number_of_statements(monkeypatch):
    import json

    from apps.api import databricks_sql, store
    from apps.api.models import SaveItems

    writes = []
    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append((sql, p)))
    items = [{"item": f"thing {n}", "confidence": 0.9} for n in range(10)]
    store.add_items(uuid.uuid4(), SaveItems(source="receipt", items=items))

    assert len(writes) == 2  # users MERGE, user_items INSERT
    inserted = json.loads(next(p["rows"] for s, p in writes if "INSERT INTO user_items" in s))
    assert len(inserted) == 10 and inserted[0]["added_at"] and "in_basket" not in inserted[0]


def test_flyer_items_are_read_once_per_ttl(monkeypatch):
    from apps.api import databricks_sql, store

    reads = []
    row = {"item_id": "f1", "page_id": "p1", "store": "Safeway", "week_start": "2026-11-05", "item": "milk",
           "price": "5.99", "bbox": "[0.1,0.2,0.3,0.4]", "page_no": "3", "valid_to": "2026-11-11"}
    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "_flyer_cache", (0.0, []))
    monkeypatch.setattr(databricks_sql, "query", lambda sql, **p: reads.append(sql) or [row])
    first, second = store.flyer_items(), store.flyer_items()
    assert len(reads) == 1 and first is second
    assert first[0].bbox == [0.1, 0.2, 0.3, 0.4] and first[0].page_no == 3  # SQL API strings parsed
    assert "current_date()" in reads[0]  # only listings still valid today


def test_patch_and_basket_statements(monkeypatch):
    from apps.api import databricks_sql, store
    from apps.api.models import ItemPatch

    writes = []
    monkeypatch.setattr(store, "MOCK", False)
    monkeypatch.setattr(store, "list_items", lambda uid: [])
    monkeypatch.setattr(databricks_sql, "execute", lambda sql, **p: writes.append((sql, p)))
    uid = uuid.uuid4()
    store.update_item(uid, "u1", ItemPatch(brand=None, size_qty=2, in_basket=True))
    (update, up), (insert, _) = writes
    assert update.startswith("UPDATE user_items SET") and up["brand"] is None and up["size_qty"] == 2
    assert "variant" not in up  # fields not sent are left alone
    assert "INSERT INTO basket_items" in insert and "NOT EXISTS" in insert
    writes.clear()
    store.update_item(uid, "u1", ItemPatch(in_basket=False))
    assert len(writes) == 1 and writes[0][0].startswith("DELETE FROM basket_items")


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


def _want(**kw):
    return _user(**{"brand": "Dairyland", "item": "milk", "variant": "2%", "size_qty": 4, "size_unit": "l", **kw})


def _flyer(**kw):
    base = dict(item_id="f", page_id="p", store="Safeway", week_start="2026-11-05", brand="Dairyland", item="milk",
                variant="2%", size_qty=4000, size_unit="ml", price=5.0)
    return logic.FlyerItem(**{**base, **kw})


@pytest.mark.parametrize("flyer, matches", [
    (dict(), True),
    (dict(brand="DAIRYLAND", item="Milk"), True),
    (dict(size_qty=3780), True),  # 2 x 1.89 L / 1 gal for 4 L
    (dict(size_qty=4400), True),  # up to +10 %
    (dict(size_qty=3700), False),  # -7.5 %: less than asked
    (dict(size_qty=2000), False),
    (dict(variant="1%"), False),
    (dict(variant="chocolate"), False),
    (dict(item="chocolate milk"), False),
    (dict(brand="Lucerne"), False),
    (dict(brand=None), False),
    (dict(size_qty=4, size_unit="kg"), False),  # different dimension
    (dict(size_qty=None, size_unit=None), False),
])
def test_exact_match(flyer, matches):
    assert logic.same_item(_want(), _flyer(**flyer)) is matches


def test_word_order_punctuation_plural_and_accents_are_not_differences():
    want = _user(brand="Dempster's", item="bagels", variant="skinless boneless", size_qty=1, size_unit="lb")
    assert logic.same_item(want, _flyer(brand="Dempster's®", item="bagel", variant="Boneless, Skinless",
                                        size_qty=500, size_unit="g"))  # 1 lb ~ 500 g
    assert logic.same_item(_want(brand="Rugen"), _flyer(brand="Rügen"))


def test_every_field_is_required_to_match():
    for blank in ("brand", "variant"):
        u = _want(**{blank: None})
        assert not logic.same_item(u, _flyer(**{blank: None})) and logic.missing(u) == [blank]
    assert logic.missing(_want(size_qty=None)) == ["size"]


def test_counts_are_exact_and_per_lb_ignores_quantity():
    eggs = _want(brand="WF", item="eggs", variant="large", size_qty=12, size_unit="ea")
    assert logic.same_item(eggs, _flyer(brand="WF", item="eggs", variant="large", size_qty=12, size_unit="ea"))
    assert not logic.same_item(eggs, _flyer(brand="WF", item="eggs", variant="large", size_qty=18, size_unit="ea"))
    bananas = _want(brand="Dole", item="banana", variant="organic", size_qty=3, size_unit="lb")
    per_lb = dict(brand="Dole", item="banana", variant="organic", size_qty=453.592, size_unit="g")
    assert logic.same_item(bananas, _flyer(**per_lb, raw_text="Dole organic bananas $0.89/lb"))
    assert not logic.same_item(bananas, _flyer(**per_lb, raw_text="Dole organic bananas 1 lb bag"))
    no_size = {**per_lb, "size_qty": None, "size_unit": None}
    assert logic.same_item(bananas, _flyer(**no_size, raw_text="DOLE ORGANIC BANANAS $0.89 /lb"))


def test_cheapest_is_by_cost_for_the_users_size():
    deals = logic.deals_for([_want()], FLYER_ITEMS)
    assert {d.store for d in deals} == {"Save-On-Foods", "Safeway", "Real Canadian Superstore"}
    best = logic.cheapest(deals)["u1"]
    assert (best.store, best.cost) == ("Safeway", 5.99)  # Superstore's 2 x 1.89 L is $7.19 scaled to 4 L
    assert best.page_id and len(best.bbox) == 4 and str(best.valid_to) == "2026-11-11"


def test_basket_compares_stores_for_basket_items_only():
    milk, eggs = _want(), _user(user_item_id="u2", brand="Western Family", item="eggs", variant="large",
                                size_qty=12, size_unit="ea")
    b = logic.basket([milk], logic.deals_for([milk, eggs], FLYER_ITEMS))
    assert b.cheapest_store == "Safeway" and b.split_total == 5.99 and b.unmatched == []


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
