# #17: Real Flipp MVP: 3-tab app, live flyers, real pages, Databricks + Genie + AI refinement

*Archived copy of [krish-arora-88/SurRealDeal#17](https://github.com/krish-arora-88/SurRealDeal/pull/17). The original, with its live discussion, stays in that repository.*

| | |
|---|---|
| **State** | merged |
| **Author** | TahaSaiyed08 |
| **Opened** | 2026-11-08 11:56 UTC |
| **Merged** | 2026-11-08 13:25 UTC by TahaSaiyed08 |
| **Closed** | — |
| **Branch** | `ws3/real-flipp-mvp` → `main` |
| **Size** | 67 files, +6767 / −926, 4 commits |

## Description

> ## What this does
>
> **Frontend (Workstream 3)**
> - Three tabs: **Pantry**, **Basket** (a checklist: To get / Done, undo, Clear done) and **Flyers** (searchable, paginated, one row per product with the cheapest price, store and category chips, sort, infinite scroll).
> - **Price Match** screen: the real stitched flyer page (zoomable), page navigation, "Original flyer" and "View on {store}'s site" links, closest-match list when nothing matches exactly.
> - Postal-code location sheet (sent as `X-Postal-Code`; default V6T1Z4), swipe rows, toasts, skeleton loading.
>
> **Backend**
> - Live per-postal Flipp feeds kept fresh in the background (hourly check, 24h refetch, refresh only on change), cached on disk (`apps/api/data/`, gitignored).
> - Real flyer page images rebuilt from Flipp's tile pyramid (tile rows count from the bottom; tested).
> - Closest-match ranking, `/flyer-items` with `category`/`store`/`sort`, `/flyers/status`, `/flyer-pages/{id}` + image.
> - Only the links, never the postal code, go into Flipp URLs.
>
> **Databricks (all opt-in, off by default)**
> - `REALDEAL_DATABRICKS_SYNC=1`: listings and price history synced to `realdeal.core.live_listings` / `price_history`.
> - Genie space + `/ask` endpoint (rate-limited; 503 if no space is configured). Setup: `make databricks-setup`.
> - `refine.py`: hosted model cleans brand / item / variant / category; answers cached per name, a failed call is retried later. Sizes and prices stay with the parser. Disable with `REALDEAL_AI_REFINE=0`.
>
> ## Notes for review
> - Merged `origin/main` into this branch; one import conflict in `apps/api/main.py` (kept both `flyers_live`/`genie` and `ExtractionServiceError`).
> - Removed the old Deals tab/components (`deals/page.tsx`, `DealCard`, `DealDetailSheet`, `products.ts`) since Flyers replaces them.
> - Items added from a flyer before AI refinement may be named slightly differently afterwards.
> - ~91% of Vancouver listings labelled so far; bare-brand names the model can only guess at are left to the parser.
>
> ## Checks (after merging main)
> - `ruff` clean, `pytest` 237 passed
> - web: `tsc`, `eslint` clean, `vitest` 44 passed
> - Playwright e2e 21 passed before the merge (not re-run after it)

## Commits (4)

- `df585f7` Real Flipp MVP: 3-tab app, live flyers, real pages, Databricks sync, Genie and AI refinement — TahaSaiyed08
- `94b9a43` Merge origin/main into ws3/real-flipp-mvp — TahaSaiyed08
- `536f0f3` Fix PR #17 blockers: app startup, passcode lockout, forged IPs, client-set flyer source — krish
- `6c3a3a1` Merge pull request #18 from krish-arora-88/ws3/real-flipp-mvp-blockers — Krish Arora

## Conversation (1)

<details><summary>**sourcery-ai[bot]** · 2026-11-08 11:56 UTC (bot)</summary>

> Sorry @TahaSaiyed08, your pull request is larger than the review limit of 150,000 diff characters

</details>

## Reviews (0)

## Inline code comments (0)

