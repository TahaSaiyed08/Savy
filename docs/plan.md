# Real Deal: implementation plan

Source of truth: [`docs/superpowers/specs/Real Deal — MVP Design.md`](superpowers/specs/Real%20Deal%20—%20MVP%20Design.md).
HackCamp 2026, Sat Nov 7 to Sun Nov 8.

The scaffold runs end to end on mock data (`make setup && make dev`). Each workstream swaps one mock for the real
thing behind a frozen interface, so nobody blocks anybody.

## Frozen interfaces

| Between          | Interface                                                                      | Lives in                                                                                      | Guarded by                                                |
| ---------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 1 ↔ 2            | Table DDL for `realdeal.core`                                                  | `databricks/sql/ddl.sql`, pipeline table definitions                                          | `apps/api/models.py` mirrors every column                 |
| 2 ↔ 3            | OpenAPI schema                                                                 | `apps/api/models.py` + `main.py` → `apps/web/openapi.json` → `apps/web/src/lib/api-schema.ts` | CI `make check-api` fails if the client is stale          |
| 3 ↔ 4            | Component list: `LargeTitle`, `InsetGroup`, `Row`, `Status`, `TabBar` + tokens | `apps/web/src/components/ui.tsx`, `TabBar.tsx`, `src/app/globals.css`                         | Design changes tokens and Figma; Frontend keeps the props |
| 1 ↔ 2 ↔ pipeline | `ExtractedItem` schema and prompts                                             | `shared/prompts/*.md` (active versions in `shared/__init__.py`), `shared/units.py`            | `databricks/test_prompt_sync.py`, `shared/test_units.py`  |

Changing a frozen interface: add, don't rename or remove. If you must break it, post in the team chat first, then
change both sides in one PR.

## How to claim

Put your GitHub handle on the `Owner:` line below in a one-line PR (or commit to `main` if it's before 10:00).
Branch as `ws<N>/<topic>`, e.g. `ws1/ai-query`. Keep PRs small; `main` must stay green.

---

## Workstream 1: Data / Pipeline

Owner: krish-arora-88

**Must not break:** column names and types in `databricks/sql/ddl.sql` and the pipeline's `flyer_items` /
`weekly_prices` (FastAPI reads them); the Volume path layout `flyers/<store>/<week_start>/<page_no>.jpg` and `flipp.jsonl`;
the `ExtractedItem` fields; `normalize_unit`'s return type.

1. Create the Free Edition workspace (verify with LinkedIn). Create a SQL warehouse and a PAT; share
   `DATABRICKS_HOST` / `DATABRICKS_WAREHOUSE_ID` with the team.
2. Run `databricks/sql/ddl.sql` in the SQL editor: catalog `realdeal`, schema `core`, Volumes `flyers` + `uploads`,
   app tables.
3. Upload one flyer page: `uv run python databricks/fetchers/common.py save_on_foods ~/flyer-shots`.
   **10:00 go/no-go.**
4. Run the `ai_query` from `databricks/pipeline/02_extract.sql` by hand on that page (swap `${realdeal.model}`
   for the endpoint, `STREAM(flyer_pages)` for `read_files('/Volumes/...', format => 'binaryFile')`). Try
   `system.ai.llama-4-maverick`, then any Claude endpoint the workspace lists. **11:00 go/no-go:** if none returns
   structured items, tell Workstream 2 to switch to `EXTRACTOR=claude` and write rows to Silver from FastAPI.
5. Install the Databricks CLI; `databricks bundle deploy && databricks bundle run realdeal_flyers` (root
   `databricks.yml`). Check `flyer_pages`, `flyer_extractions`, `flyer_items`, `weekly_prices`.
6. `uv run --env-file .env python databricks/fetchers/flipp.py --limit 5` (all 5 stores from Flipp's public JSON:
   exact tile boxes, prices, valid dates), run the pipeline with `--full-refresh flyer_items` once (Silver is now a
   union), check the rows, then rerun without `--limit`.
7. Build the 20-page golden set; measure field accuracy. **13:00 go/no-go:** ≥ 85 %, else drop to the two cleanest stores.
8. Matching is exact (`logic.same_item`: brand, item, variant and size, size within `SIZE_WINDOW`), so there is no
   threshold or AI Search index. Check 20 known user-item ↔ flyer-item pairs match, and that near-misses don't.
10. Add `normalize_unit` cases for any flyer text that parses wrong (add to `shared/test_units.py` first).

**Done when:** `SELECT count(*) FROM realdeal.core.flyer_items` > 2,000 real rows from this week's flyers, and
the 20 known pairs match exactly.

## Workstream 2: Backend

Owner: primenumberhater666

**Must not break:** the OpenAPI schema (paths, request and response models in `apps/api/models.py`); the
`X-User-Id` contract; mock mode, which stays the default with no `.env`, so WS3 and WS4 can always run the app.

1. Run `make dev`; read `/docs` at http://localhost:8000/docs. All routes already return mock data.
2. Set `ANTHROPIC_API_KEY`; test `ClaudeExtractor` on a real receipt (`/intake/receipt`). Tune
   `shared/prompts/receipt.v1.md` (copy to `v2`, add it to `PROMPT_VERSIONS` in `shared/__init__.py`) until the demo receipt parses cleanly.
3. Once WS1 has tables, set the Databricks env vars and `REALDEAL_MOCK=0`. Exercise `store.py`'s real paths:
   `list_items`, `add_items`, `update_item` (edit, basket), `flyer_items` (exact matching runs on read).
4. Write receipts to `receipts` and the image to `/Volumes/realdeal/core/uploads/` on `/intake/receipt`.
5. Product photo: return the top candidate plus two alternates (prompt already asks for it).
6. Voice: set `ELEVENLABS_API_KEY`; confirm `/intake/voice` with a webm from Safari and Chrome.
7. If WS1 says `ai_query` works: implement `DatabricksAIExtractor` (upload → `ai_query` over `read_files`).
   If it doesn't: write flyer extractions from FastAPI to `flyer_extractions` with the same JSON shape.
8. Weekly re-match: nothing to do; matches are computed on every read against flyers valid today.
9. Optional: host FastAPI as a Databricks App (3 apps max, auto-stop after 24 h, restart before judging).

**Done when:** all endpoints return real data against WS1's tables, and OpenAPI docs are served.

## Workstream 3: Frontend

Owner: _unclaimed_

**Must not break:** the component list props (Design styles them); the three tab routes `/list`, `/deals`,
`/basket`; `withUser()` on every API call; the generated client (never hand-edit `api-schema.ts`, run `make gen-api`).

1. Run `make dev`, open http://localhost:3000. All three tabs render mock data.
2. Intake bottom sheet from My List: three actions. Receipt and product use
   `<input type="file" accept="image/*" capture="environment">`; POST multipart to `/intake/receipt` or `/intake/photo`.
3. Confirm screen: show `extraction.items`, flag `needs_confirm` rows (confidence < 0.6) for edit, then POST `/items`.
   Product photo: chip picker over the candidates.
4. Manual entry: text field → `/intake/manual` → inline edit of parsed fields → `/items`.
5. Hold-to-talk on the manual sheet: `MediaRecorder` → `/intake/voice`. Safari records `audio/mp4`, Chrome `audio/webm`.
6. Tap an item: `item.cheapest` → `GET /flyer-pages/{page_id}`, highlight the tile, sticky card with valid dates.
7. Basket: cheapest store card, split-shop list, dollar delta, "no deal this week" rows.
8. Install to home screen on an iPhone and an Android via a tunnel (e.g. `cloudflared tunnel --url http://localhost:3000`);
   make the QR for the demo slide.
9. Playwright smoke test: open the PWA, add an item manually, see it in Deals.

**Done when:** a judge can add items by all three methods on their phone and see the basket.

## Workstream 4: Design & Pitch

Owner: _unclaimed_

**Must not break:** the component list; token names in `globals.css` (change values freely).

1. **11:00 go/no-go call on `ai_query`** with WS1 (Design & Pitch owns the decision).
2. User research: 30-minute poll of UBC students; count flyer pages near campus this week (the "40 pages" stat).
3. Figma: HIG mobile frames for the three tabs and the three intake sheets, with rationale per HIG element.
4. Replace the placeholder icons in `apps/web/public/` (192, 512, 180 apple-touch with no transparency).
5. Lock the video script by 16:00; shoot after the 15:00 end-to-end check.
6. Demo script per the spec's seven steps; prepare and pre-test the Save-On-Foods receipt Saturday evening.
7. Devpost write-up with the Figma link.
8. If time: Genie space and AI/BI dashboard over `weekly_prices`.
9. Rehearse the demo twice Sunday morning.

**Done when:** Figma is linked in Devpost, the video is cut, and the demo has been rehearsed twice.

---

## Go / no-go checks

- [ ] 10:00 Sat: workspace created, UC catalog `realdeal`, Volume `flyers` exists, one flyer page uploaded
- [ ] 11:00 Sat: `ai_query` returns structured items from one flyer page. If not, switch the extractor to the Anthropic API in FastAPI
- [ ] 13:00 Sat: extraction accuracy ≥ 85 % on the 20-page golden set. If not, drop to the two stores with the cleanest flyers
- [ ] 15:00 Sat: one ugly end-to-end path works (receipt photo → deals on a phone)
- [ ] 16:00 Sat: video script locked

## 3 a.m. cut list, in order

1. StatCan "real deal" badge
2. Genie space and dashboard
3. Product-photo intake
4. Voice intake
5. Split-shop view

Receipt intake, matching and the basket are never cut.
