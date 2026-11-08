"""Bronze: Auto Loader over the flyers Volume. One row per page image, metadata parsed from the path."""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

VOLUME = "/Volumes/realdeal/core/flyers"


@dp.table(name="flyer_pages", comment="Bronze: one row per flyer page image")
@dp.expect_or_drop("has_week", "week_start IS NOT NULL")
def flyer_pages():
    parts = F.split(F.col("path"), "/")  # .../flyers/<store>/<week_start>/<page_no>.jpg
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821 (spark is injected by the pipeline runtime)
        .option("cloudFiles.format", "binaryFile")
        .option("pathGlobFilter", "*.{jpg,jpeg,png}")
        .load(VOLUME)
        .select(
            F.sha2("path", 256).alias("page_id"),
            F.element_at(parts, -3).alias("store"),
            F.to_date(F.element_at(parts, -2)).alias("week_start"),
            F.regexp_extract("path", r"(\d+)\.\w+$", 1).cast("int").alias("page_no"),
            F.col("path").alias("image_path"),
            F.current_timestamp().alias("fetched_at"),
            "content",
        )
    )


FLIPP = ("flipp_id STRING, store STRING, week_start DATE, valid_from DATE, valid_to DATE, page_id STRING, "
         "page_no INT, page_aspect DOUBLE, bbox ARRAY<DOUBLE>, image_url STRING, price DOUBLE, raw_text STRING")


@dp.table(name="flipp_items", comment="Bronze: one row per Flipp flyer item, written by databricks/fetchers/flipp.py")
@dp.expect_or_drop("has_text", "raw_text IS NOT NULL AND week_start IS NOT NULL")
def flipp_items():
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "json")
        .option("pathGlobFilter", "*.jsonl")
        .schema(FLIPP)
        .load(VOLUME)
    )
