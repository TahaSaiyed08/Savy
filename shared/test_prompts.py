import pytest

from shared import load_prompt


@pytest.mark.parametrize("mode", ["flyer_page", "receipt", "product", "manual"])
def test_every_mode_loads_a_prompt(mode):
    assert load_prompt(mode).strip()


def test_receipt_uses_v2():
    assert load_prompt("receipt") == load_prompt("receipt", "v2") != load_prompt("receipt", "v1")


def test_manual_uses_v2():
    assert load_prompt("manual") == load_prompt("manual", "v2") != load_prompt("manual", "v1")
