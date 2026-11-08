import pytest

from shared.units import Size, normalize_unit, per_weight, unit_price


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2 x 1.89 L", Size(3780, "ml")),
        ("6-pack 355 mL", Size(2130, "ml")),
        ("1.5kg", Size(1500, "g")),
        ("per 100g", Size(100, "g")),
        ("12 × 355 ml", Size(4260, "ml")),
        ("$3.99/lb", Size(453.592, "g")),
        ("4L", Size(4000, "ml")),
        ("6 pk", Size(6, "ea")),
        ("12 ea", Size(12, "ea")),
        ("24 ct", Size(24, "ea")),
        ("2.49 ea", Size(1, "ea")),  # a price, not a count
        ("bananas", None),
    ],
)
def test_normalize_unit(text, expected):
    got = normalize_unit(text)
    if expected is None:
        assert got is None
    else:
        assert got.unit == expected.unit
        assert got.qty == pytest.approx(expected.qty)


def test_unit_price_compares_across_pack_sizes():
    # The demo-breaker: a 2-pack looks cheaper on the shelf tag but loses on unit price.
    assert unit_price(9.98, normalize_unit("2 x 1.89 L")) == (pytest.approx(0.264, abs=1e-3), "100ml")
    assert unit_price(6.49, normalize_unit("4 L")) == (pytest.approx(0.162, abs=1e-3), "100ml")
    assert unit_price(1.0, None) is None


def test_per_weight():
    assert per_weight("$3.99/lb") and per_weight("Bananas 0.69 per kg")
    assert not per_weight("4 L") and not per_weight("$1.99 /L") and not per_weight("1 lb bag")
