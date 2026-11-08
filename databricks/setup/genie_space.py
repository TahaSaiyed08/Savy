"""The definition of the Real Deal Genie space: which tables it reads and what it knows about them.

Genie writes SQL from plain-language questions, so what makes its answers good is the table and column comments
(in apps/api/databricks_sync.py), the instructions below, and a few worked examples.
"""
import json
import uuid

TITLE = "Real Deal: this week's grocery deals"
DESCRIPTION = "Ask about this week's grocery flyer prices near a postal code: cheapest items, stores, discounts."
# Genie is only allowed to read these two tables (kept in sync by apps/api/databricks_sync.py).
TABLES = ["realdeal.core.live_listings", "realdeal.core.price_history"]

# Plain-language rules Genie follows when it writes SQL. Each one fixes a mistake seen in real answers: comparing unit
# prices across different units, matching "egg" inside "eggplant", or writing a regex Spark reads as nothing.
INSTRUCTIONS = [
    "Every row belongs to a postal code. Only use rows where postal matches the shopper's postal code, which comes "
    "at the start of each question.",
    "live_listings is what is on sale now. A listing is on sale today when valid_to >= current_date().",
    "price_history keeps every listing from every week, so use it for questions about how prices change.",
    "Prices are Canadian dollars. price is for the whole package; unit_price is per 100 g, per 100 ml or per each.",
    "To find the cheapest version of a product, compare unit_price among rows with the same unit (100g with 100g, "
    "100ml with 100ml, ea with ea). Do not compare unit_price across different units.",
    "size_qty is in ml, g or ea, so a 2 L carton has size_qty 2000 and size_unit ml. Say sizes the way a shopper "
    "would (2 L, 750 g).",
    "item is what the product is (Milk, Brown Eggs); brand is separate. Match product words as WHOLE words with "
    "RLIKE and letter boundaries on lower(item), never a substring LIKE: '%egg%' also finds eggplant, egg nog and Eggo "
    "waffles. Write the boundary as (^|[^a-z]) before and ([^a-z]|$) after, and allow a plural, so eggs is "
    "lower(item) RLIKE '(^|[^a-z])eggs?([^a-z]|$)'. NEVER put a backslash in SQL: in Spark a backslash-b is a "
    "backspace character and matches nothing. Then check variant and raw_text, for example 'milk' should include "
    "variants like 2% and lactose free.",
    "Leave out look-alikes that are not the thing asked for (egg nog and egg tarts are not eggs, chocolate milk is "
    "not plain milk) unless the shopper asks for them.",
    "Eggs, and other things sold by count, have size_unit 'ea': compare them by price / size_qty, the price of one. "
    "A normal carton of eggs is 6 to 30 ea.",
    "category groups listings (Dairy & eggs, Produce, Meat & seafood, Bakery, Pantry, Snacks & sweets, Frozen, Drinks, "
    "Household, Health & beauty, Other). Use it for questions like 'what dairy is on sale'. It is null for listings "
    "not yet labelled, so do not treat null as a category.",
    "A discount is regular_price - price, and only exists where regular_price is not null.",
    "Round prices to 2 decimals. Always show store, brand, item, size and price, and at most 10 rows unless asked "
    "for more.",
]

# Shown as clickable starters in the Genie space itself.
SAMPLE_QUESTIONS = [
    "What's the cheapest milk this week?",
    "Which store has the cheapest eggs?",
    "What are the biggest discounts at No Frills?",
    "Which chicken is cheapest per 100 g?",
    "How many items does each store have on sale?",
    "Compare bread prices at Safeway and No Frills",
]

# Worked examples: a question with the SQL we want for it. Genie imitates their style, so they use the same whole-word
# matching, the same unit rules and a sensible LIMIT. The first three are also the space's benchmark questions.
_COLS = "store, brand, item, variant, size_qty, size_unit, price, round(unit_price, 3) AS unit_price, unit"
EXAMPLES = [
    ("What's the cheapest milk this week?",
     f"SELECT {_COLS} FROM realdeal.core.live_listings WHERE postal = 'V6T1Z4' AND valid_to >= current_date() "
     "AND lower(item) LIKE '%milk%' AND unit_price IS NOT NULL ORDER BY unit_price ASC LIMIT 10"),
    ("Which store has the cheapest eggs?",
     "SELECT store, brand, item, variant, size_qty, size_unit, price, round(price / size_qty, 2) AS price_each "
     "FROM realdeal.core.live_listings WHERE postal = 'V6T1Z4' AND valid_to >= current_date() "
     "AND lower(item) RLIKE '(^|[^a-z])eggs?([^a-z]|$)' "
     "AND lower(item) NOT RLIKE 'nog|tart|white|plant|waffle|noodle' "
     "AND size_unit = 'ea' AND size_qty BETWEEN 6 AND 30 ORDER BY price_each ASC LIMIT 10"),
    ("What are the biggest discounts?",
     "SELECT store, brand, item, size_qty, size_unit, regular_price, price, round(regular_price - price, 2) AS saving "
     "FROM realdeal.core.live_listings WHERE postal = 'V6T1Z4' AND valid_to >= current_date() "
     "AND regular_price IS NOT NULL ORDER BY saving DESC LIMIT 10"),
    ("Compare bread prices at Safeway and No Frills",
     f"SELECT {_COLS} FROM realdeal.core.live_listings WHERE postal = 'V6T1Z4' AND valid_to >= current_date() "
     "AND lower(store) IN ('safeway', 'no frills') AND lower(item) RLIKE '(^|[^a-z])breads?([^a-z]|$)' "
     "AND unit_price IS NOT NULL ORDER BY store, unit_price ASC LIMIT 20"),
    ("How many items does each store have on sale?",
     "SELECT store, count(*) AS items_on_sale FROM realdeal.core.live_listings WHERE postal = 'V6T1Z4' "
     "AND valid_to >= current_date() GROUP BY store ORDER BY items_on_sale DESC"),
    ("How has the price of eggs changed from week to week?",
     "SELECT week_start, store, brand, item, size_qty, size_unit, price FROM realdeal.core.price_history "
     "WHERE postal = 'V6T1Z4' AND lower(item) RLIKE '(^|[^a-z])eggs?([^a-z]|$)' "
     "ORDER BY week_start DESC, price ASC LIMIT 30"),
]


# The space is described to Genie as one JSON document. These helpers shape the bits it is picky about: text goes in
# as a list of lines each ending in a newline, and every list must be sorted by a unique id.
def _lines(text: str) -> list[str]:
    return [line + "\n" for line in text.split("\n")]


def _id() -> str:
    return uuid.uuid4().hex


def _by_id(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: i["id"])  # Genie wants every list in id order


def build() -> str:
    # Called by create_genie_space.py both to create the space and to update it in place when this file changes.
    """The space as the JSON string Genie's create and update calls take (the format its own get call returns)."""
    return json.dumps({
        "version": 2,
        "config": {"sample_questions": _by_id([{"id": _id(), "question": [q]} for q in SAMPLE_QUESTIONS])},
        "data_sources": {"tables": [{"identifier": t} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": _id(), "content": [line + "\n" for line in INSTRUCTIONS]}],
            "example_question_sqls": _by_id(
                [{"id": _id(), "question": [q], "sql": _lines(sql)} for q, sql in EXAMPLES]),
        },
        "benchmarks": {"questions": _by_id([
            {"id": _id(), "question": [q], "answer": [{"format": "SQL", "content": _lines(sql)}]}
            for q, sql in EXAMPLES[:3]
        ])},
    })
