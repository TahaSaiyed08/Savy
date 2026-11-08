"""Size parsing shared by the Lakeflow pipeline and FastAPI. Keep it pure: no imports beyond stdlib."""
import re
from typing import NamedTuple


# Every size is stored in a base unit so any two can be compared directly: grams for weight, millilitres for volume,
# and "ea" (each) for counts. A "2 L" is 2000 ml and a "1 lb" is 453.592 g.
class Size(NamedTuple):
    qty: float  # in base units
    unit: str  # "g", "ml" or "ea"


# Multipliers from a written unit to its base unit, and which base it belongs to.
_FACTORS = {
    "mg": (0.001, "g"), "g": (1, "g"), "kg": (1000, "g"),
    "lb": (453.592, "g"), "lbs": (453.592, "g"), "oz": (28.3495, "g"),
    "ml": (1, "ml"), "l": (1000, "ml"),
}
# Building blocks for the patterns below: a unit word, then "a number followed by a unit", "per <unit>" prices,
# multipliers ("6-pack", "2 x"), and counts ("12 ea") that must not be confused with a price like "2.49 ea".
_UNIT = r"(kg|mg|g|ml|l|lbs?|oz)\b"
_QTY = re.compile(r"(\d+(?:\.\d+)?)\s*" + _UNIT, re.I)
_PER = re.compile(r"(?:per|/)\s*" + _UNIT, re.I)  # "$3.99/lb" -> 1 lb
_MULT = re.compile(r"(\d+)\s*(?:x|×|-?\s*pack|pk)", re.I)
_COUNT = re.compile(r"(?<![\d.])(\d+)\s*(?:ea|each|ct|count)\b", re.I)  # "12 ea", not "2.49 ea"
_EACH = re.compile(r"\b(?:ea|each)\b", re.I)


def normalize_unit(text: str) -> Size | None:
    """'2 x 1.89 L' -> Size(3780, 'ml'); '6-pack 355 mL' -> Size(2130, 'ml'); 'per 100g' -> Size(100, 'g').

    Returns None when no size can be read, so callers fall back to comparing on price.
    """
    # Try the readings from most to least specific: an explicit amount, a "per kg" price, a pack count, then "each".
    m = _QTY.search(text)
    if m:
        factor, unit = _FACTORS[m[2].lower()]
        qty = float(m[1]) * factor
        # A multiplier only counts when it comes BEFORE the amount ("2 x 1.89 L"), not text that follows it.
        mult = _MULT.search(text[: m.start()])
        if mult:
            qty *= int(mult[1])
        return Size(round(qty, 3), unit)
    m = _PER.search(text)
    if m:
        factor, unit = _FACTORS[m[1].lower()]
        return Size(factor, unit)
    mult = _MULT.search(text) or _COUNT.search(text)
    if mult:
        return Size(float(mult[1]), "ea")
    if _EACH.search(text):
        return Size(1.0, "ea")
    return None


def size_from(qty: float | None, unit: str | None) -> Size | None:
    """A (size_qty, size_unit) pair as a Size: (12, 'ea') -> 12 ea, (4, 'l') -> 4000 ml. None if missing/unreadable."""
    if not qty or not unit:
        return None
    # Counts are used as given; weights and volumes go back through normalize_unit so they land in base units.
    s = Size(float(qty), "ea") if unit.lower() == "ea" else normalize_unit(f"{qty:g} {unit}")
    return s if s and s.qty > 0 else None


def per_weight(text: str) -> bool:
    """'$3.99/lb', 'per kg': sold by weight, so any amount of it is the same listing.

    Not when a fixed weight is also printed ('1 kg pack $13.21/kg'): that pack only comes in one size.
    """
    m = _PER.search(text)
    return bool(m) and _FACTORS[m[1].lower()][1] == "g" and not _QTY.search(text)


def unit_price(price: float, size: Size | None) -> tuple[float, str] | None:
    """Price per 100 g / 100 mL / each, the basis every store comparison uses."""
    if size is None or size.qty <= 0:
        return None
    # Weights and volumes are priced per 100 (a nicer number than per gram); counts are priced per single item.
    if size.unit == "ea":
        return round(price / size.qty, 4), "ea"
    return round(price / size.qty * 100, 4), f"100{size.unit}"
