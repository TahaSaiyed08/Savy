# Real Deal — MVP Design

> **Superseded for matching (PR #12):** matching is now exact (brand, item, variant and size; see
> `apps/api/logic.py`). AI Search, `flyer_items_idx`, `my_deals`, the 0.75 threshold and "probable match" are gone,
> and one Flipp fetcher (`databricks/fetchers/flipp.py`) replaces the per-store fetchers. The rest of this spec stands.

Nov 7, 2026 · @PSA ClaudeCode2

## Overview

Real Deal reads every weekly grocery flyer from 4–5 major Vancouver chains, learns what a student actually buys from their receipts, and shows them only the deals on their own items plus the cheapest store for the whole basket. It is a mobile-first PWA for UBC students, built for HackCamp 2026 (Nov 7–8) with Databricks as the main sponsor track.

**Community problem.** Students on a food budget re-make the same decision every week: where to shop and what is actually cheap. Today that means 30–40 pages of flyers across Flipp and store apps, none of which know what you buy or compare unit prices across stores.

**Core loop.**

1. Pipeline ingests this week's flyers from 4–5 stores and extracts `{brand, item, variant, size, price, unit price}` per line item.
2. Student builds their list three ways: photo of a receipt (bulk-add), photo of a product (one item), or plain-English entry typed or spoken (ElevenLabs speech-to-text).
3. The list persists on-device; each week the app matches it against new flyers.
4. Basket view: cheapest single store for the list, and the split-shop alternative with the dollar delta.

Receipts are the retention hook: every shop updates the list, so next week's deals are ready before the student asks. A "real deal vs. fake sale" badge against a StatCan price baseline is a secondary feature, cut first if time runs short.

## Architecture and data flow

&#91;embedded content: architecture · flyers → Databricks → FastAPI → PWA\]

Three Databricks pieces are load-bearing: Lakeflow (ingest and extraction as a declarative pipeline), AI Functions (`ai_query` on flyer page images), and AI Search (fuzzy matching of user items to flyer items). Genie and an AI/BI dashboard are hour-18 extras.

FastAPI is thin: it fetches flyers and uploads them to the Volume, proxies the three intake paths, and reads Gold tables through the SQL Statement API. The PWA never talks to Databricks directly. If `ai_query` is unavailable on the account, `extract_items()` in FastAPI calls the Anthropic API and writes to the same Silver table, so the pipeline shape does not change.

## Data model

All tables live in Unity Catalog under `realdeal.core`. Flyer tables follow Bronze/Silver/Gold; user tables are written by FastAPI.

| Table | Layer | Key columns | Written by |
| --- | --- | --- | --- |
| `flyer_pages` | Bronze | `page_id, store, week_start, page_no, image_path, fetched_at` | FastAPI fetch job (SDK → Volume + insert) |
| `flyer_items` | Silver | `item_id, page_id, store, week_start, brand, item, variant, size_qty, size_unit, price, unit_price, unit, raw_text, bbox` | Lakeflow: `ai_query` over page image |
| `weekly_prices` | Gold | `store, week_start, canonical_item, unit_price` | Lakeflow: dedupe + normalize |
| `users` | App | `user_id (uuid from device), created_at` | FastAPI |
| `user_items` | App | `user_item_id, user_id, brand, item, variant, size_qty, size_unit, source (receipt, photo, manual, voice), added_at, last_bought_at` | FastAPI intake |
| `receipts` | App | `receipt_id, user_id, store, total, bought_at, image_path` | FastAPI intake |
| `my_deals` (view) | Gold | `user_id, user_item_id, flyer_item_id, store, price, unit_price, match_score, savings_vs_median` | AI Search join |

**AI Search index.** `flyer_items_idx` on `concat(brand, ' ', item, ' ', variant, ' ', size_qty, size_unit)`, Delta Sync mode from Silver. Matching is one query per `user_item`, top-3, score threshold about 0.75, tuned Saturday afternoon on 20 known pairs.

**Unit normalization.** One pure Python function, `normalize_unit`, used by both the pipeline and FastAPI, with a shared test file. "2 × 1.89 L" and "6-pack 355 mL" are where demos break.

**Identity.** No login. The PWA generates a UUID on first open and sends it as `X-User-Id`. A judge's phone is a fresh user.

## Ownership split

Four workstreams run independently once the scaffold is pushed. Interfaces between them are frozen in the scaffold on day one: the table DDL (1↔2), the OpenAPI schema (2↔3), and a component list (3↔4).

| # | Owner | Workstream | Done when |
| --- | --- | --- | --- |
| 1 | Data / Pipeline | Databricks workspace, UC catalog, Volume, flyer fetcher (4–5 stores), Lakeflow Bronze→Silver→Gold, `ai_query` prompt, `normalize_unit`, AI Search index | `SELECT count(*) FROM flyer_items` > 2,000 real rows from this week's flyers; index queryable |
| 2 | Backend | FastAPI: `/intake/receipt`, `/intake/photo`, `/intake/manual`, `/intake/voice`, `/items`, `/deals`, `/basket`; SQL Statement API client; Anthropic fallback extractor; ElevenLabs STT proxy | All endpoints return real data against workstream 1's tables; OpenAPI docs served |
| 3 | Frontend | Next.js PWA (manifest, service worker, QR-installable): camera capture, voice input, My List, Deals, Basket; HIG-compliant components | Judge can add items by all three methods on their phone and see the basket |
| 4 | Design & Pitch | Figma (HIG mobile frames + rationale), user research (30-min poll + flyer-count stat), 4-min video, demo script, Devpost write-up; Genie space + dashboard if time | Figma linked in Devpost; video cut; demo rehearsed twice |

Workstream 4 also owns the hour-1 go/no-go on `ai_query` (see Constraints and risks).

## Intake, extraction, matching, basket

**One extraction function, three prompts.** `extract(image, mode)` with `mode` in `{flyer_page, receipt, product}` returns the same `ExtractedItem[]` schema: `brand, item, variant, size_qty, size_unit, price?, confidence`. Prompts are versioned files in `shared/prompts/`. The same function runs as `ai_query` in the pipeline (flyer pages) and through the FastAPI extractor (receipts, products), so the two never drift.

| Intake path | What happens | Confirm step |
| --- | --- | --- |
| Receipt photo | Extract all lines; abbreviations like `PC CHKN THGH BNLS 1KG` resolve with store context from the header. Each line becomes a `user_item` with `last_bought_at` = receipt date | Parsed list shown for one-tap confirm before save |
| Product photo | Extract one item from packaging; return top candidate plus two alternates | Chip picker |
| Manual / voice | ElevenLabs speech-to-text → plain English → text-only Claude call maps "the big Kirkland olive oil" to the schema. Typed input skips STT | Inline edit of the parsed fields |

**Matching.** On save, embed the user item text and query AI Search for the top-3 flyer items this week. Brand match is required if the user specified a brand, otherwise a generic match is allowed. Size within ±25 %, or compare on unit price. Score ≥ 0.75. `match_score` is stored so the UI can show "probable match" vs. "exact".

**Basket.** For the list: per store, sum of matched unit prices × quantity; unmatched items show "no deal this week" with last known price if any. Output is the cheapest single store for the whole basket and the split-shop option (best price per item across stores) with the dollar delta, so the judge sees the real decision.

**Error handling that matters for the demo.**

- Extractions with confidence < 0.6 go to a confirm screen instead of saving silently.
- AI Search cold or down falls back to SQL `LIKE` + trigram on `flyer_items`, so the demo degrades rather than dies.
- Every Databricks call has a 5 s timeout and a cached last-good response.

## PWA and HIG

The app is a mobile-first PWA, not a native app: no store review, a QR code on the demo slide opens it on a judge's phone in seconds, and one set of Figma frames covers it. Reference: [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines).

**PWA setup.** Next.js App Router with `next-pwa` manifest and service worker; `display: standalone`; 180 px apple-touch-icon; safe-area insets. Camera via `<input capture="environment">`, which works in Safari with only the camera permission prompt. Web Push is a bonus on Android; iOS needs home-screen install first, so the demo never depends on it.

**HIG mapping.**

| HIG element | Real Deal implementation |
| --- | --- |
| Tab bar | 3 tabs: My List, Deals, Basket |
| Navigation | Large-title headers, back by swipe |
| Typography | System font stack (`-apple-system`), Dynamic Type via `rem` |
| Touch targets | 44 pt minimum everywhere |
| Lists | Grouped inset lists for items and deals |
| Modality | Bottom sheets for the three intake paths |
| Appearance | Light and dark via `prefers-color-scheme` |
| Motion | Transitions under 200 ms |
| Voice | Hold-to-talk button on the manual sheet, streaming audio to `/intake/voice` |

Three screens are the whole MVP. Settings, history and a flyer-overlay view are stretch goals.

**Testing.** Unit tests for `normalize_unit` and the matching rules (pure functions); a 20-pair golden set for extraction accuracy run at 1 p.m. Saturday; one Playwright smoke test that opens the PWA, adds an item manually, and sees it in Deals.

## Demo path

Seven steps, about three minutes. Everything on this path is rehearsed twice Sunday morning; anything not on it is cut first.

1. Slide: a photo of 40 pages of flyers. "This is what 'on sale' looks like near UBC every Thursday."
2. Judge scans the QR and opens the PWA on their own phone.
3. Judge photographs a real receipt we bring (Save-On-Foods, this week). Items parse; they confirm.
4. Deals tab fills with their items matched across the stores. Basket shows the cheapest store and the split-shop delta.
5. Judge says into the phone "add a 4 L jug of 2 % milk." It appears, matched.
6. Laptop, 20 seconds: Lakeflow DAG, `flyer_items` row count, the `ai_query` SQL, the AI Search index.
7. Close: "Next Thursday, their deals are already waiting."

The receipt in step 3 is pre-tested against the extractor Saturday evening. The voice line in step 5 is one we know matches.

## Constraints and risks

**Databricks Free Edition limits** ([source](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations), checked Nov 7, 2026). Everyone verifies with LinkedIn at signup; it raises usage limits.

| Limit | Effect on this design |
| --- | --- |
| Outbound internet from compute restricted to trusted domains | Flyer scraping and the Claude API fallback run in FastAPI, not notebooks; files reach the Volume via the SDK |
| One SQL warehouse, 2X-Small | FastAPI caches Gold reads; no heavy ad-hoc queries during judging |
| One active Lakeflow pipeline per type | One pipeline covers Bronze→Silver→Gold |
| One AI Search endpoint, one search unit | One index, `flyer_items_idx` |
| Model Serving endpoints limited; "certain models unavailable" | Hour-1 check that `ai_query` with a hosted vision model works on the account |
| 3 Databricks Apps, auto-stop after 24 h | Optional: host FastAPI as an App; restart before judging |
| 5 concurrent job tasks | Fetch job runs serially per store |

**Go / no-go checks.**

- [ ] 10:00 Sat: workspace created, UC catalog `realdeal`, Volume `flyers` exists, one flyer page uploaded
- [ ] 11:00 Sat: `ai_query` returns structured items from one flyer page. If not, switch the extractor to the Anthropic API in FastAPI
- [ ] 13:00 Sat: extraction accuracy ≥ 85 % on the 20-page golden set. If not, drop to the two stores with the cleanest flyers
- [ ] 15:00 Sat: one ugly end-to-end path works (receipt photo → deals on a phone)
- [ ] 16:00 Sat: video script locked

**3 a.m. cut list, in order.** StatCan "real deal" badge → Genie space and dashboard → product-photo intake → voice intake → split-shop view. Receipt intake, matching and the basket are never cut.

**Known comparables.** Flipp has typed shopping lists matched to flyers. nürish (HackCamp 2022) was a static campus deals list. Real Deal's differentiators are receipt-driven list building, a persistent profile, and cross-store unit-price comparison; those three must work live.
