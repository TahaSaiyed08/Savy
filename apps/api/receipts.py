"""Rules that apply to scanned receipts only (photos, typed lines and flyers are untouched).

A receipt records what was bought, not what a flyer advertises: "3.14 lb apples" is the weight that went on the scale,
not a package size. Keeping it would make the item look like a specific 3.14 lb pack that no flyer sells, so fresh
produce loses its size and quantity here. Packaged goods keep theirs: a 340 g bag of coffee really is a 340 g bag.
"""
import re

from apps.api import logic
from apps.api.models import ExtractedItem, Extraction

# Fresh fruit, vegetables and herbs, singular. Words that are also something else on a shelf (pepper the spice, corn
# in a can, mint the candy, bean, pea) are left out: leaving a size on a produce item is harmless, dropping one from
# a packaged item is not.
PRODUCE = frozenset("""
apple apricot arugula asparagus avocado banana basil beet blackberry blueberry bok broccoli cabbage cantaloupe carrot
cauliflower celery cherry cilantro clementine cucumber eggplant fennel garlic ginger grape grapefruit jalapeno kale kiwi
leek lemon lettuce lime mandarin mango melon mushroom nectarine onion orange papaya parsley peach pear pineapple plum
pomegranate potato radish raspberry romaine shallot spinach squash strawberry tangerine tomato turnip watermelon yam
zucchini
""".split())
PRODUCE_PAIRS = (("bell", "pepper"),)  # "bell pepper" is produce, "black pepper" is not
# If the line says it is processed, it is a packaged product even when it names a fruit or vegetable.
PROCESSED = frozenset("""
bagel bar bread butter cake candy canned cereal chip chocolate cookie cracker crisp dip dressing dried drink frozen fry
gummy granola jam jelly juice ketchup muffin oil paste pickle pie puree ring salsa sauce smoothie snack soda soup sorbet
spread syrup tea yogurt
""".split())


def _forms(word: str) -> set[str]:
    """A word and its likely singulars: the matcher already drops a plural s, so tomatoes arrives as tomatoe and
    strawberries as strawberrie."""
    forms = {word}
    if word.endswith("e"):
        forms.add(word[:-1])  # tomatoe -> tomato, peache -> peach
    if word.endswith("ie"):
        forms.add(word[:-2] + "y")  # strawberrie -> strawberry
    return forms


def is_produce(item: ExtractedItem) -> bool:
    words = logic._words(item.item)
    if words & PROCESSED or logic._words(item.variant) & PROCESSED:
        return False
    if any(a in words and b in words for a, b in PRODUCE_PAIRS):
        return True
    return any(_forms(w) & PRODUCE for w in words)


def drop_produce_quantity(extraction: Extraction) -> Extraction:
    """The same receipt, with fresh produce lines stripped of size and quantity (the price stays)."""
    bare = {"size_qty": None, "size_unit": None}
    items = [i.model_copy(update=bare) if is_produce(i) else i for i in extraction.items]
    return extraction.model_copy(update={"items": items})


def tidy(extraction: Extraction) -> Extraction:
    """What /intake/receipt returns: produce without size, and a plain date. Some models answer with a date and time
    ("2023-12-09T10:42:00") although the prompt asks for a date; the app (and the receipts table) want only the day."""
    day = re.match(r"\d{4}-\d{2}-\d{2}", extraction.bought_at or "")
    return drop_produce_quantity(extraction).model_copy(update={"bought_at": day[0] if day else None})
