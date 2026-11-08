"""Receipt-only rules: fresh produce loses its size and quantity, everything else keeps what it has."""
import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api import receipts
from apps.api.extractors import MockExtractor, get_extractor
from apps.api.main import app
from apps.api.models import ExtractedItem, Extraction
from shared import load_prompt


def _line(item, qty=None, unit=None, **kw):
    return ExtractedItem(item=item, size_qty=qty, size_unit=unit, confidence=0.9, **kw)


@pytest.mark.parametrize("item", [
    "apple", "banana", "avocado", "tomato", "tomatoes", "potatoes", "strawberries", "peaches", "cherry tomato",
    "baby carrot", "bell pepper", "green onion", "romaine lettuce", "jalapeno", "cilantro",
])
def test_fresh_produce_is_recognised_singular_or_plural(item):
    assert receipts.is_produce(_line(item, 3.14, "lb"))


@pytest.mark.parametrize("item, variant", [
    ("orange juice", None), ("potato chip", None), ("tomato sauce", None), ("apple sauce", None), ("lemon", "frozen"),
    ("onion ring", None), ("peanut butter", None), ("black pepper", None), ("oat milk", None), ("chicken breast", None),
    ("coffee", None), ("egg", None), ("strawberry", "jam"), ("yogurt", "strawberry"), ("grape", "juice"),
    ("banana bread", None), ("carrot cake", None), ("lemon", "chocolate"),
])
def test_packaged_and_processed_food_is_not_produce_even_when_it_names_a_fruit(item, variant):
    assert not receipts.is_produce(_line(item, 1.89, "l", variant=variant))


def test_produce_loses_size_and_quantity_but_keeps_everything_else():
    x = Extraction(items=[
        _line("apple", 3.14, "lb", variant="gala", price=9.39),
        _line("avocado", 1, "ea", price=1.99),
        _line("milk", 1, "l", brand="Dairyland", variant="2%", price=5.39),
        _line("coffee", 340, "g", price=12.99),
    ], store="Save-On-Foods", bought_at="2026-11-06", total=29.76)
    got = receipts.drop_produce_quantity(x)
    assert [(i.item, i.size_qty, i.size_unit) for i in got.items] == [
        ("apple", None, None), ("avocado", None, None), ("milk", 1, "l"), ("coffee", 340, "g")]
    assert (got.items[0].variant, got.items[0].price, got.items[0].confidence) == ("gala", 9.39, 0.9)  # only size goes
    assert (got.store, got.bought_at, got.total) == ("Save-On-Foods", "2026-11-06", 29.76)
    assert x.items[0].size_qty == 3.14  # the original extraction is not modified


def test_the_receipt_prompt_tells_the_model_the_same_rule():
    prompt = load_prompt("receipt")
    assert "Produce rule" in prompt and "null" in prompt and "frozen peas" in prompt
    assert "'" not in load_prompt("manual")  # untouched: the typed-line prompt is shared with the pipeline


@pytest.fixture
def client():
    app.dependency_overrides[get_extractor] = lambda: MockExtractor()
    yield TestClient(app)
    app.dependency_overrides.pop(get_extractor, None)


def test_scanning_a_receipt_drops_produce_size_and_keeps_packaged_size(client):
    h = {"X-User-Id": str(uuid.uuid4())}
    r = client.post("/intake/receipt", headers=h, files={"file": ("r.jpg", b"\xff\xd8\xff" + b"x" * 20, "image/jpeg")})
    assert r.status_code == 200
    items = {i["item"]: i for i in r.json()["extraction"]["items"]}
    assert (items["banana"]["size_qty"], items["banana"]["size_unit"]) == (None, None)  # canned: banana 1 lb
    assert items["banana"]["price"] == 0.79  # the price stays
    assert (items["chicken thigh"]["size_qty"], items["chicken thigh"]["size_unit"]) == (1, "kg")  # meat keeps its size
    assert (items["eggs"]["size_qty"], items["eggs"]["size_unit"]) == (12, "ea")


def test_other_intake_paths_are_not_touched(client):
    h = {"X-User-Id": str(uuid.uuid4())}
    r = client.post("/intake/manual", headers=h, json={"text": "3 lb bananas"})
    assert r.status_code == 200
    (item,) = r.json()["extraction"]["items"]
    assert item["size_qty"] is not None  # a typed line keeps its quantity: only receipts change
