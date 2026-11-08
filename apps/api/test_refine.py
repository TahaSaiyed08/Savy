import json
from types import SimpleNamespace as NS

import pytest

from apps.api import databricks_sql, refine
from apps.api.models import FlyerItem


def _row(name="NO NAME® NATURALLY IMPERFECT™ POTATOES", brand="no name", item="Naturally Imperfect Potatoes", **kw):
    base = dict(item_id=f"i-{abs(hash((name, brand)))}", page_id="flipp-1-1", store="No Frills",
                week_start="2026-11-05", item=item, brand=brand, raw_text=name, price=3.0)
    return FlyerItem(**{**base, **kw})


GOOD = {"brand": "No Name", "item": "Potatoes", "variant": "Naturally Imperfect", "category": "Produce"}


@pytest.fixture
def model(monkeypatch, tmp_path):
    """The model replaced by a function we control; its cache in a temp file."""
    monkeypatch.setattr(refine, "CACHE_FILE", tmp_path / "refined.json")
    monkeypatch.setattr(refine, "_cache", None)
    calls = []
    answers = {"fn": lambda batch: [GOOD for _ in batch]}
    monkeypatch.setattr(refine, "_call", lambda batch: calls.append(batch) or answers["fn"](batch))
    return NS(calls=calls, answers=answers)


# --- reading the model's reply ------------------------------------------------------------------------------


def test_parse_reads_a_reply_wrapped_in_prose_and_code_fences():
    answer = {"brand": "Kraft", "item": "Peanut Butter", "variant": None, "category": "Pantry"}
    reply = f"Sure! ```json\n{json.dumps([answer])}\n``` Done."
    assert refine.parse(reply, 1) == [answer]


def test_parse_distrusts_a_reply_with_the_wrong_number_of_answers_since_names_would_get_their_neighbours():
    assert refine.parse('[{"item": "A", "category": "Pantry"}]', 2) == [None, None]
    assert refine.parse("I can't help with that", 2) == [None, None]
    assert refine.parse('{"item": "A"}', 1) == [None]


def test_parse_clamps_what_it_is_given():
    got = refine.parse(json.dumps([{"item": "A", "category": "Space food", "brand": "  ", "variant": "x" * 200},
                                   {"item": "  "}, "junk", {"brand": "B"}]), 4)
    assert got[0] == {"brand": None, "item": "A", "variant": "x" * 80, "category": "Other"}
    assert got[1:] == [None, None, None]  # no item, not an object, no item


# --- applying it ----------------------------------------------------------------------------------------------


def test_the_models_names_replace_the_parsers_and_sizes_and_prices_are_left_alone(model):
    row = _row(size_qty=2270.0, size_unit="g", unit_price=0.13, unit="100g")
    (got,) = refine.apply([row])
    assert (got.brand, got.item, got.variant) == ("No Name", "Potatoes", "Naturally Imperfect")
    assert got.category == "Produce"
    assert (got.size_qty, got.size_unit, got.unit_price) == (2270.0, "g", 0.13)
    assert (got.price, got.item_id) == (3.0, row.item_id)


def test_where_the_model_says_nothing_the_flyers_own_brand_and_the_parsers_variant_stay(model):
    model.answers["fn"] = lambda batch: [
        {"brand": None, "item": "Collection", "variant": None, "category": "Snacks & sweets"}]
    (got,) = refine.apply([_row("Ferrero Rocher Collection", "Ferrero Rocher", "Collection", variant="Dark")])
    assert (got.brand, got.variant) == ("Ferrero Rocher", "Dark")


def test_a_name_is_asked_about_once_ever_even_across_restarts(model, monkeypatch):
    refine.apply([_row()])
    refine.apply([_row(), _row()])  # the same listing again, and a duplicate
    assert len(model.calls) == 1 and len(model.calls[0]) == 1
    monkeypatch.setattr(refine, "_cache", None)  # a new process reads the saved file
    assert refine.apply([_row()])[0].category == "Produce" and len(model.calls) == 1


def test_names_go_to_the_model_in_batches_and_identical_ones_are_sent_once(model):
    rows = [_row(f"NAME {n}", "b", f"Name {n}") for n in range(refine.BATCH * 2 + 3)] + [_row("NAME 0", "b", "Name 0")]
    refine.apply(rows)
    assert sorted(len(b) for b in model.calls) == [3, refine.BATCH, refine.BATCH]
    assert model.calls[0][0].keys() == {"name", "brand"}


def test_a_model_failure_leaves_the_rows_alone_and_is_not_remembered(model):
    model.answers["fn"] = lambda batch: [None] * len(batch)
    row = _row()
    assert refine.apply([row]) == [row]
    model.answers["fn"] = lambda batch: [GOOD for _ in batch]
    assert refine.apply([row])[0].category == "Produce"  # asked again, since the failure was not cached


def test_an_answer_about_something_else_is_rejected(model):
    model.answers["fn"] = lambda batch: [{"brand": None, "item": "Motor Oil", "variant": None, "category": "Household"}]
    row = _row()
    assert refine.apply([row]) == [row]
    assert refine.apply([row]) == [row] and len(model.calls) == 1  # the rejection is remembered, not re-asked


def test_listings_already_labelled_or_without_a_name_are_not_sent(model):
    done = _row("A", "b", "A", category="Pantry")
    nameless = _row("", "b", "x", raw_text=None)
    assert refine.apply([done, nameless]) == [done, nameless] and model.calls == []


# --- talking to Databricks ------------------------------------------------------------------------------------


def _client(replies):
    seen = []

    def query(model, **kw):
        seen.append((model, kw))
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return NS(choices=[NS(message=NS(content=r))])

    return NS(serving_endpoints=NS(query=query)), seen


def test_the_call_backs_off_and_retries_then_parses(monkeypatch):
    client, seen = _client([RuntimeError("429"), RuntimeError("503"),
                            json.dumps([GOOD])])
    monkeypatch.setattr(databricks_sql, "_client", lambda: client)
    sleeps = []
    monkeypatch.setattr(refine.time, "sleep", sleeps.append)
    assert refine._call([{"name": "NO NAME POTATOES", "brand": "no name"}]) == [GOOD]
    assert sleeps == [2, 4] and seen[0][0] == refine.MODEL and seen[0][1]["temperature"] == 0


def test_the_call_gives_up_after_its_retries_without_raising(monkeypatch):
    client, _ = _client([RuntimeError("down")] * refine.RETRIES)
    monkeypatch.setattr(databricks_sql, "_client", lambda: client)
    monkeypatch.setattr(refine.time, "sleep", lambda s: None)
    assert refine._call([{"name": "x", "brand": None}, {"name": "y", "brand": None}]) == [None, None]


def test_the_prompt_names_every_category_and_says_sizes_are_not_wanted(monkeypatch):
    client, seen = _client([json.dumps([GOOD])])
    monkeypatch.setattr(databricks_sql, "_client", lambda: client)
    refine._call([{"name": "x", "brand": None}])
    prompt = seen[0][1]["messages"][0].content
    assert all(c in prompt for c in refine.CATEGORIES) and "Ignore sizes" in prompt


@pytest.mark.parametrize("flag, creds, want", [(None, True, True), ("0", True, False), (None, False, False)])
def test_refining_runs_when_databricks_is_configured_unless_switched_off(monkeypatch, flag, creds, want):
    for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN"):
        monkeypatch.setenv(k, "x") if creds else monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REALDEAL_AI_REFINE", flag) if flag else monkeypatch.delenv("REALDEAL_AI_REFINE", raising=False)
    assert refine.enabled() is want
