-- Real Deal: Unity Catalog objects. Run top to bottom in the SQL editor (idempotent).
-- Frozen interface between workstream 1 (pipeline) and 2 (FastAPI). Pydantic mirrors: apps/api/models.py.

CREATE CATALOG IF NOT EXISTS realdeal;
CREATE SCHEMA IF NOT EXISTS realdeal.core;
USE realdeal.core;

CREATE VOLUME IF NOT EXISTS flyers COMMENT 'Flyer page images: <store>/<week_start>/<page_no>.jpg';
CREATE VOLUME IF NOT EXISTS uploads COMMENT 'Receipt and product photos from the app';

-- Pipeline-owned tables. Created and schema-enforced by databricks/pipeline/ (do NOT create them here,
-- the pipeline must own them):
--   flyer_pages       Bronze  page_id, store, week_start, page_no, image_path, fetched_at (+ content)
--   flyer_extractions Silver  raw ai_query response per page
--   flyer_items       Silver  item_id, page_id, store, week_start, brand, item, variant, size_qty, size_unit,
--                             price, unit_price, unit, raw_text, bbox, match_text
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
  last_bought_at TIMESTAMP,
  in_basket      BOOLEAN COMMENT 'Pantry is every item ever added; Basket is the ones moved here to get now'
);
-- Additive, so a catalog created before this column existed still works: ALTER instead of relying on
-- CREATE TABLE IF NOT EXISTS, which skips entirely once the table already exists. Re-running this against
-- a catalog that already has the column fails (Databricks has no ADD COLUMN IF NOT EXISTS); drop the line
-- once every catalog has it.
ALTER TABLE user_items ADD COLUMNS (in_basket BOOLEAN COMMENT 'Pantry vs Basket');

CREATE TABLE IF NOT EXISTS receipts (
  receipt_id STRING NOT NULL,
  user_id    STRING NOT NULL,
  store      STRING,
  total      DOUBLE,
  bought_at  DATE,
  image_path STRING
);

-- AI Search results per user item, written by FastAPI on save. my_deals reads it.
CREATE TABLE IF NOT EXISTS user_item_matches (
  user_item_id  STRING    NOT NULL,
  flyer_item_id STRING    NOT NULL,
  match_score   DOUBLE    NOT NULL,
  matched_at    TIMESTAMP NOT NULL
);
