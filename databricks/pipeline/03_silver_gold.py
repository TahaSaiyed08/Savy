"""Silver flyer_items (parsed + unit-normalized) and Gold weekly_prices.

normalize_unit comes from shared/, which the bundle syncs next to this file (see databricks.yml).
"""
import sys

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

sys.path.append(spark.conf.get("realdeal.repo_root"))  # noqa: F821
from shared.stores import STORES  # noqa: E402
from shared.units import normalize_unit, unit_price  # noqa: E402

ITEMS = (
    "STRUCT<items: ARRAY<STRUCT<brand: STRING, item: STRING, variant: STRING, size_qty: DOUBLE, "
    "size_unit: STRING, price: DOUBLE, confidence: DOUBLE, raw_text: STRING, bbox: ARRAY<DOUBLE>>>>"
)
_STORE_NAME = F.create_map(*[F.lit(x) for kv in STORES.items() for x in kv])
_UP = StructType([StructField("unit_price", DoubleType()), StructField("unit", StringType())])


@F.udf(_UP)
def _unit_price(price, size_qty, size_unit, raw_text):
    if price is None:
        return None
    size = normalize_unit(f"{size_qty}{size_unit}") if size_qty and size_unit else normalize_unit(raw_text or "")
    up = unit_price(price, size)
    return {"unit_price": up[0], "unit": up[1]} if up else None


@dp.table(
    name="flyer_items",
    comment="Silver: one row per advertised product",
    table_properties={"delta.enableChangeDataFeed": "true"},  # required by the AI Search Delta Sync index
)
@dp.expect_or_drop("has_item", "item IS NOT NULL")
@dp.expect("has_price", "price IS NOT NULL")
@dp.expect("confident", "confidence >= 0.6")
def flyer_items():
    x = dp.read_stream("flyer_extractions")
    parsed = x.withColumn("i", F.explode(F.from_json("response", ITEMS)["items"]))
    return (
        parsed.select("page_id", "store", "week_start", "i.*")
        .withColumn("store", F.coalesce(_STORE_NAME[F.col("store")], F.col("store")))
        .withColumn("item_id", F.sha2(F.concat_ws("|", "page_id", "raw_text", "item", "price"), 256))
        .withColumn("up", _unit_price("price", "size_qty", "size_unit", "raw_text"))
        .withColumn("unit_price", F.col("up.unit_price"))
        .withColumn("unit", F.col("up.unit"))
        .withColumn("match_text", F.concat_ws(" ", "brand", "item", "variant",
                                              F.concat(F.col("size_qty").cast("string"), "size_unit")))
        .drop("up")
    )


@dp.materialized_view(name="weekly_prices", comment="Gold: cheapest unit price per store, week and item")
def weekly_prices():
    return (
        dp.read("flyer_items")
        .where("unit_price IS NOT NULL")
        .withColumn("canonical_item", F.lower(F.trim(F.concat_ws(" ", "item", "variant"))))
        .groupBy("store", "week_start", "canonical_item")
        .agg(F.min("unit_price").alias("unit_price"))
    )
