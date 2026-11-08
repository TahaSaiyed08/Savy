-- Savy: Unity Catalog objects. Run top to bottom in the SQL editor (idempotent).
-- Frozen interface between workstream 1 (pipeline) and 2 (FastAPI). Pydantic mirrors: apps/api/models.py.

CREATE CATALOG IF NOT EXISTS realdeal;
CREATE SCHEMA IF NOT EXISTS realdeal.core;
USE realdeal.core;

CREATE VOLUME IF NOT EXISTS flyers COMMENT 'Flyer pages: <store>/<week_start>/<page_no>.jpg, or flipp.jsonl from fetchers/flipp.py';
CREATE VOLUME IF NOT EXISTS uploads COMMENT 'Receipt and product photos from the app';

-- Pipeline-owned tables. Created and schema-enforced by databricks/pipeline/ (do NOT create them here,
-- the pipeline must own them):
--   flyer_pages       Bronze  page_id, store, week_start, page_no, image_path, fetched_at (+ content)
--   flipp_items       Bronze  one row per Flipp flyer item: exact tile box, price, valid dates, cutout image
--   flyer_extractions Silver  raw ai_query response per page image
--   flipp_extractions Silver  raw ai_query response per Flipp item text (brand/item/variant/size)
--   flyer_items       Silver  item_id, page_id, store, week_start, brand, item, variant, size_qty, size_unit,
--                             price, unit_price, unit, raw_text, bbox, confidence, page_no, valid_from, valid_to,
--                             image_url, image_path, page_aspect
--   weekly_prices     Gold    store, week_start, canonical_item, unit_price

-- App tables, written by FastAPI.
CREATE TABLE IF NOT EXISTS users (
  user_id    STRING    NOT NULL COMMENT 'UUID generated on the device, sent as X-User-Id',
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS user_items (
  user_item_id   STRING    NOT NULL,
  user_id        STRING    NOT NULL,
  brand          STRING,
  item           STRING    NOT NULL,
  variant        STRING,
  size_qty       DOUBLE,
  size_unit      STRING,
  source         STRING    NOT NULL COMMENT 'receipt | photo | manual | voice',
  added_at       TIMESTAMP NOT NULL,
  last_bought_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS receipts (
  receipt_id STRING NOT NULL,
  user_id    STRING NOT NULL,
  store      STRING,
  total      DOUBLE,
  bought_at  DATE,
  image_path STRING
);

-- Pantry (My List) items the user moved to the Basket (what they're buying right now). A table, not an in_basket column on
-- user_items, so this file stays idempotent: CREATE TABLE IF NOT EXISTS skips existing tables and Databricks
-- has no ADD COLUMN IF NOT EXISTS.
CREATE TABLE IF NOT EXISTS basket_items (
  user_id      STRING    NOT NULL,
  user_item_id STRING    NOT NULL,
  added_at     TIMESTAMP NOT NULL,
  done_at      TIMESTAMP  -- set when ticked off on this trip; catalogs created earlier need ALTER TABLE ... ADD COLUMN
);
