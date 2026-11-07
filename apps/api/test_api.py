import io
import uuid

from fastapi.testclient import TestClient

from apps.api import logic
from apps.api.main import app
from apps.api.mock_data import FLYER_ITEMS

c = TestClient(app)
H = {"X-User-Id": str(uuid.uuid4())}


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


def test_rejects_non_image_receipt():
    r = c.post("/intake/receipt", headers=H, files={"file": ("r.txt", io.BytesIO(b"x"), "text/plain")})
    assert r.status_code == 415


def test_voice_uses_mock_transcript():
    r = c.post("/intake/voice", headers=H, files={"file": ("a.webm", io.BytesIO(b"x"), "audio/webm")}).json()
    assert r["transcript"] and r["extraction"]["items"][0]["size_unit"] == "ml"


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
