# #12: Backend/exact match

*Archived copy of [krish-arora-88/SurRealDeal#12](https://github.com/krish-arora-88/SurRealDeal/pull/12). The original, with its live discussion, stays in that repository.*

| | |
|---|---|
| **State** | merged |
| **Author** | krish-arora-88 |
| **Opened** | 2026-11-08 05:41 UTC |
| **Merged** | 2026-11-08 05:59 UTC by krish-arora-88 |
| **Closed** | — |
| **Branch** | `backend/exact-match` → `main` |
| **Size** | 39 files, +1754 / −1103, 11 commits |

## Description

> ## Exact matching, Basket, flyer-page view, and Flipp flyers for all 5 stores
>
> This is the backend for the new flow: **Add item → Pantry → Basket → tap an item → its flyer page, which you show the cashier**.
>
> ### Matching is now exact (`apps/api/logic.py`)
> - An item matches only when **brand, item, variant and size** are all filled in and equal the flyer's. Items missing any of them still save, but they match nothing. `ListItem.missing` lists the empty fields so the UI can ask for them.
> - Text is compared after ignoring case, accents, punctuation, word order and a plural "s". So `Dempster's®` = `dempsters` and `skinless boneless` = `boneless skinless`, but `2%` ≠ `1%` and milk ≠ chocolate milk.
> - Sizes can differ only enough to cover metric/imperial rounding (`SIZE_WINDOW`):
>   - Volume −6% / +10%: 3.78 L counts as 4 L, 946 mL counts as 1 L, 750 mL does not.
>   - Weight −10% / +11%: 1 lb counts as 500 g.
>   - Counts must be exact.
>   - Anything priced per lb or per kg matches any amount.
> - Removed: word-overlap scoring, AI Search, the LIKE fallback, `user_item_matches`, the `my_deals` view, the retry queue, `MATCH_THRESHOLD`, `views.sql` and `ai_search_index.py`.
> - Matches are worked out on every read against flyer items still valid today, with a 10-minute in-memory cache.
>
> ### API
> - `GET` and `POST /items` return `ListItem` (`UserItem` plus `missing` and `cheapest`). `cheapest` is the cheapest listing for the user's size and carries `page_id`, `bbox` and `valid_from`/`valid_to`.
> - `PATCH /items/{id}` edits only the fields sent; it accepts the full ExtractedItem body the current frontend sends. `in_basket` can be sent too.
> - `POST /items/{id}/basket` keeps PR #10's frontend contract.
> - `GET /basket` compares stores for Basket items only.
> - `GET /flyer-pages/{page_id}` returns every item's box on that page plus the valid dates, for the highlight and the cashier's sticky card. `GET /flyer-pages/{id}/image` serves full page images from the Volume.
>
> ### Data
> - `ddl.sql` adds a `basket_items` table instead of PR #10's `in_basket` column. With a table, `ddl.sql` can still be re-run safely; Databricks has no `ADD COLUMN IF NOT EXISTS`. It has already been run on the workspace.
> - New `databricks/fetchers/flipp.py` pulls all 5 stores from Flipp's public JSON: each item's exact position on its page, its price (multi-buys divided per unit), the flyer's valid dates and a cut-out image. It writes `flipp.jsonl` to the Volume. It replaces the 5 empty per-store fetchers.
> - Pipeline changes:
>   - New Bronze table `flipp_items`.
>   - New Silver table `flipp_extractions`: a text ai_query that reuses the app's `manual.v2` prompt, so flyer items and users' items get normalized by the same rules.
>   - `flyer_items` is now the union of page-image rows and Flipp rows, with new columns `page_no`, `valid_from`/`valid_to`, `image_url`, `image_path` and `page_aspect`.
> - ai_query uses the `databricks-llama-4-maverick` endpoint and a JSON-schema `responseFormat`.
> - The API filters for valid dates in Python, so it works whether or not the pipeline has added the new columns yet.
>
> ### Frontend
> - Only a type rename: `Schemas["UserItem"]` → `Schemas["ListItem"]`, because every items endpoint now returns `ListItem`.
> - The e2e test now looks for the new seed label `Dole banana organic`.
>
> ### Testing
> - Clean clone: ruff, 82 pytest, `make check-api`, eslint, tsc, vitest (18), `next build`, Playwright (7/7).
> - Pipeline test on Databricks with 5 Safeway Flipp items: completed. `flyer_items` has 281 rows, all with page numbers and valid dates. The Flipp rows' positions, prices and sizes looked right.
>
> ### Known gaps
> - `manual.v2` sometimes drops descriptive words ("Pure Basmati Rice" came back as item `rice` with no variant). Users' input goes through the same prompt, so the bigger risk is false matches (basmati rice matching jasmine rice). Needs a prompt fix.
> - A Flipp item offering several products ("X or Y or Z") is extracted as its first product only.
> - Save-On's OCR rows usually have no variant, so few of them match exactly.
> - Fetching the same week again needs `--full-refresh flipp_items,flipp_extractions,flyer_items`, because Auto Loader won't re-read a file it has already seen.
> - Full 5-store run (about 1,500 text ai_query calls) not done yet.
>
> ## Summary by Sourcery
>
> Implement exact item matching and the basket-to-flyer-page flow across the backend, data pipeline, and supporting frontend contracts.
>
> New Features:
> - Add exact grocery flyer matching across brand, item, variant, and size, including normalized text comparison and metric/imperial size tolerances.
> - Expose item match status, cheapest listings, basket operations, and flyer-page details and images through the backend API.
> - Add Flipp ingestion for all five stores with flyer dates, prices, tile positions, and item images.
> - Support comparing basket costs across stores and opening a matched product on its flyer page.
>
> Bug Fixes:
> - Prevent stale flyer or database reads from masking recent writes and preserve existing item results when flyer data is temporarily unavailable.
> - Handle multi-buy Flipp prices as per-unit prices and filter flyer listings to currently valid dates.
>
> Enhancements:
> - Replace persisted and probabilistic matching with read-time exact matching and short-lived flyer caching.
> - Replace the basket flag column with an idempotent basket_items table and support partial item updates.
> - Unify flyer and user-item normalization through shared extraction prompts and structured model responses.
>
> Documentation:
> - Update project documentation and API types for exact matching, flyer-page navigation, basket behavior, and Flipp-based ingestion.
>
> Tests:
> - Expand API, matching, flyer-page, Flipp ingestion, caching, prompt synchronization, and unit tests for the new behavior.
>
> Chores:
> - Remove the previous AI Search, match-score, retry-queue, persisted-match, and per-store fetcher infrastructure.

## Commits (11)

- `00c6015` Exact matching, basket, item edit, flyer-page view, Flipp fetcher for all 5 stores — krish
- `0554596` Web: list state is ListItem (the shape GET/POST /items now return) — krish
- `70c0cb6` Read flyer_items validity in Python so the API works before and after the pipeline adds valid_to — krish
- `5d6913c` e2e: seed banana now has brand and variant — krish
- `0096715` Merge remote-tracking branch 'origin/main' into backend/exact-match — krish
- `6dfbb33` Flipp: keep '2/' out of raw_text once the price is per unit (ai_query read it as a 2-pack) — krish
- `a2b90dc` Fix PR #12 review findings — krish
- `fb8fa47` Merge main into backend/exact-match, resolve conflicts with ws2/backend re-match work — TahaSaiyed08
- `a2cd557` Merge origin/backend/exact-match (review-findings fixes), rename fresh->fallback — TahaSaiyed08
- `2aa88b6` store: every SQL statement is a fixed literal (Semgrep sqlalchemy-execute-raw-query) — krish
- `a6b38ad` Merge remote-tracking branch 'origin/backend/exact-match' into backend/exact-match — krish

## Conversation (1)

<details><summary>**sourcery-ai[bot]** · 2026-11-08 05:41 UTC (bot)</summary>

> <!-- Generated by sourcery-ai[bot]: start review_guide -->
>
> ## Reviewer's Guide
>
> ### Schema and migrations
>
> Replace the basket flag and persisted-match schema with basket membership in its own table, and define the Bronze/Silver flyer data needed for the new Flipp-backed listings.
> - `databricks/pipeline/01_bronze.py` L27-42
> - `databricks/pipeline/03_silver_gold.py` L34-63 (+8 small edits)
> - `databricks/sql/ddl.sql` L14-19, L50-56 (+3 small edits)
>
> ### Data structures
>
> Define the flyer, list-item, deal, patch, tile, and page-view structures that the matcher and API rely on.
> - `apps/api/models.py` L6-17, L65-76, L135-199 (+3 small edits)
>
> ### API
>
> Expose enriched item responses, partial edits and basket updates, exact deals, and flyer-page/image routes; make query fallback behavior explicit for reads after writes.
> - `apps/api/databricks_sql.py` L49-52, L62
> - `apps/api/main.py` L21-28, L156-198, L209-240 (+7 small edits)
> - `apps/web/openapi.json` L593-669, L1096-1290, L1306-1389 (+19 small edits)
> - `apps/web/src/lib/api-schema.ts` L198-237, L362-425, L933-995 (+17 small edits)
>
> ### Uses of the API
>
> Update the web client’s item state and list/deal callers to use enriched list items and the API’s cost-ranked cheapest listing.
> - `apps/web/e2e/delete.spec.ts` L3, L9
> - `apps/web/src/app/list/page.tsx` L37, L43, L50-57
> - `apps/web/src/lib/use-items.ts` L7, L75
>
> ### Implementation
>
> Implement exact normalized identity and size matching, listing-cost comparison, and basket totals from current flyer rows.
> - `apps/api/logic.py` L1-22, L31-93, L116-124 (+1 small edits)
> - `shared/units.py` L49-65
>
> Load and cache valid flyer rows, serve page images, and perform owner-scoped item and basket writes without relying on persisted matches.
> - `apps/api/store.py` L22-51, L70-121, L161-193 (+10 small edits)
>
> Fetch Flipp listings and page coordinates, upload flyer assets, and transform image- and Flipp-derived rows into the unified flyer table.
> - `databricks/fetchers/common.py` L1-7, L11 (removed lines), L23-35
> - `databricks/fetchers/flipp.py` L1-141
> - `databricks/pipeline/02_extract.sql` L26-61
> - `databricks/fetchers/no_frills.py` (deleted)
> - `databricks/fetchers/safeway.py` (deleted)
> - `databricks/fetchers/save_on_foods.py` (deleted)
> - `databricks/fetchers/superstore.py` (deleted)
> - `databricks/fetchers/tnt.py` (deleted)
> - `databricks/setup/ai_search_index.py` (deleted)
> - `databricks/sql/views.sql` (deleted)
>
> ### UI
>
> Adjust list rows and edit sheets to consume the enriched list-item shape and remove the obsolete probable-match presentation.
> - `apps/web/src/components/list/EditItemSheet.tsx` L14
> - `apps/web/src/components/list/ListRow.tsx` L21
> - `apps/web/src/components/deals/DealCard.tsx` L53 (removed lines)
>
> ### Configuration
>
> Point the pipeline bundle at the serving endpoint used for flyer extraction.
> - `databricks.yml` L9
>
> ### Documentation
>
> Update the project overview, implementation plan, and MVP spec to describe exact matching, Flipp ingestion, and the flyer-page flow.
> - `README.md` L78, L97
> - `docs/plan.md` L48-57 (+6 small edits)
> - `docs/superpowers/specs/Real Deal — MVP Design.md` L3-6
>
> ### Tests
>
> Cover enriched API behavior, exact matching, flyer caching and ingestion, basket writes, prompt synchronization, and SQL setup parsing.
> - `apps/api/test_api.py` L44-87, L211-316, L472-573 (+5 small edits)
> - `databricks/test_flipp.py` L1-72
> - `databricks/test_prompt_sync.py` L1-8, L14-19
> - `databricks/test_run_sql.py` L21
> - `shared/test_units.py` L3, L37-42
>
> ### Other changes
>
> Files not grouped.
> - `apps/api/mock_data.py` L1-6, L14-32, L37-69
> - `databricks/setup/run_sql.py` L3
>
> ---
>
> <details>
> <summary>Tips and commands</summary>
>
> #### Interacting with Sourcery
>
> - **Trigger a new review:** Comment `@sourcery-ai review` on the pull request.
> - **Continue discussions:** Reply directly to Sourcery's review comments.
> - **Generate a GitHub issue from a review comment:** Ask Sourcery to create an
>   issue from a review comment by replying to it. You can also reply to a
>   review comment with `@sourcery-ai issue` to create an issue from it.
> - **Generate a pull request title:** Write `@sourcery-ai` anywhere in the pull
>   request title to generate a title at any time. You can also comment
>   `@sourcery-ai title` on the pull request to (re-)generate the title at any time.
> - **Generate a pull request summary:** Write `@sourcery-ai summary` anywhere in
>   the pull request body to generate a PR summary at any time exactly where you
>   want it. You can also comment `@sourcery-ai summary` on the pull request to
>   (re-)generate the summary at any time.
> - **Generate reviewer's guide:** Comment `@sourcery-ai guide` on the pull
>   request to (re-)generate the reviewer's guide at any time.
> - **Resolve all Sourcery comments:** Comment `@sourcery-ai resolve` on the
>   pull request to resolve all Sourcery comments. Useful if you've already
>   addressed all the comments and don't want to see them anymore.
> - **Dismiss all Sourcery reviews:** Comment `@sourcery-ai dismiss` on the pull
>   request to dismiss all existing Sourcery reviews. Especially useful if you
>   want to start fresh with a new review - don't forget to comment
>   `@sourcery-ai review` to trigger a new review!
>
> #### Customizing Your Experience
>
> Access your [dashboard](https://app.sourcery.ai/dashboard/review-settings?connection=github&owner=krish-arora-88&from_surface=github_bot&intent=review_settings) to:
> - Enable or disable review features such as the Sourcery-generated pull request
>   summary, the reviewer's guide, and others.
> - Change the review language.
> - Add, remove or edit custom review instructions.
> - Adjust other review settings.
>
> #### Getting Help
>
> - [Contact our support team](mailto:support@sourcery.ai) for questions or feedback.
> - Visit our [documentation](https://docs.sourcery.ai) for detailed guides and information.
> - Keep in touch with the Sourcery team by following us on [X/Twitter](https://x.com/SourceryAI), [LinkedIn](https://www.linkedin.com/company/sourcery-ai/) or
>
> *(truncated: 112 more characters in the original)*

</details>

## Reviews (1)

<details><summary>**sourcery-ai[bot]** · commented · 2026-11-08 05:44 UTC (bot)</summary>

> Hey - I've found 3 security issues, and 3 other issues
>
> **Security issues**:
> - Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option. ([link](https://github.com/krish-arora-88/SurRealDeal/pull/12/files#diff-9bc433ec9b4093df7376156a0c4222f07c2217ad34afd4447f93d05cd45aec37R132))
> - Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option. ([link](https://github.com/krish-arora-88/SurRealDeal/pull/12/files#diff-9bc433ec9b4093df7376156a0c4222f07c2217ad34afd4447f93d05cd45aec37R138))
> - Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option. ([link](https://github.com/krish-arora-88/SurRealDeal/pull/12/files#diff-9bc433ec9b4093df7376156a0c4222f07c2217ad34afd4447f93d05cd45aec37R150))
>
> <details>
> <summary>Prompt for AI Agents</summary>
>
> ~~~markdown
> Please address the comments from this code review:
>
> ## Individual Comments
>
> ### Comment 1
> <location path="apps/api/store.py" line_range="93" />
> <code_context>
> -    new = [_new_item(user_id, req.source, req.bought_at,
> -                     **i.model_dump(include={"brand", "item", "variant", "size_qty", "size_unit"}))
> -           for i in req.items]
> +    new = [_new_item(user_id, req.source, req.bought_at, **i.model_dump(include=set(_EDITABLE))) for i in req.items]
>      if MOCK:
>          _mock_items(user_id)[:0] = new
> </code_context>
> <issue_to_address>
> **Save retries create duplicates**
>
> When a save commits but its response is lost or reported as failed and the client retries, `add_items()` generates fresh UUIDs and inserts every submitted item again, so the retry creates duplicate Pantry entries.
>
> Make saving the same submitted items idempotent across retries.
> </issue_to_address>
>
> ### Comment 2
> <location path="databricks/fetchers/flipp.py" line_range="39" />
> <code_context>
> +
> +def _get(path: str, **params) -> dict:
> +    r = http.get(f"{API}/{path}", params=params)
> +    r.raise_for_status()
> +    return r.json()
> +
> </code_context>
> <issue_to_address>
> **One fetch error drops a store**
>
> When any one of the concurrent item-detail requests times out or returns a non-success response, a failed or timed-out Flipp item-detail request raises out of `_get()` and `pool.map()`, aborting `rows()` before it writes that store's JSONL file; the store's flyer data is absent until someone reruns the fetch.
>
> Retry transient detail requests and handle per-item failures so one failed request does not discard the entire store's fetch.
> </issue_to_address>
>
> ### Comment 3
> <location path="shared/units.py" line_range="52" />
> <code_context>
> +def per_weight(text: str) -> bool:
> +    """'$3.99/lb', 'per kg': sold by weight, so any amount of it is the same listing."""
> +    m = _PER.search(text)
> +    return bool(m) and _FACTORS[m[1].lower()][1] == "g"
> +
> +
> </code_context>
> <issue_to_address>
> **Packaged items bypass size matching**
>
> When a fixed-size flyer listing's raw text includes a price basis such as `per g` or `/g`, `per_weight()` treats any `per g` or `/g` text as sold by weight, and `same_item()` then skips the size window. A fixed-size listing with that unit-price wording therefore matches users asking for a different quantity.
>
> Only bypass size checks for wording that identifies a product sold by weight, not a unit-price basis for a packaged item.
>
> Also at `apps/api/logic.py:54`.
> </issue_to_address>
>
> ### Comment 4
> <location path="apps/api/store.py" line_range="132" />
> <code_context>
>         db.execute(f"UPDATE user_items SET {', '.join(f'{k} = :{k}' for k in fields)} {mine}", **fields, **ids)
> </code_context>
> <issue_to_address>
> **security (python.sqlalchemy.security.sqlalchemy-execute-raw-query):** Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option.
>
> *Source: opengrep*
> </issue_to_address>
>
> ### Comment 5
> <location path="apps/api/store.py" line_range="138" />
> <code_context>
>         db.execute(f"DELETE FROM basket_items {mine}", **ids)
> </code_context>
> <issue_to_address>
> **security (python.sqlalchemy.security.sqlalchemy-execute-raw-query):** Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option.
>
> *Source: opengrep*
> </issue_to_address>
>
> ### Comment 6
> <location path="apps/api/store.py" line_range="150" />
> <code_context>
>         db.execute(f"DELETE FROM {table} {_MINE}", user_id=str(user_id), user_item_id=user_item_id)
> </co
>
> *(truncated: 2370 more characters in the original)*

</details>

## Inline code comments (6)

<details><summary>**sourcery-ai[bot]** on `apps/api/store.py` line 146 · 2026-11-08 05:44 UTC (bot)</summary>

> **🟡 Medium · Save retries create duplicates**
>
> When a save commits but its response is lost or reported as failed and the client retries, `add_items()` generates fresh UUIDs and inserts every submitted item again, so the retry creates duplicate Pantry entries.
>
> Make saving the same submitted items idempotent across retries.
>
> <details>
> <summary>Prompt for AI agents</summary>
>
> ~~~markdown
> In `apps/api/store.py` at line 93:
>
> **Save retries create duplicates**
>
> When a save commits but its response is lost or reported as failed and the client retries, `add_items()` generates fresh UUIDs and inserts every submitted item again, so the retry creates duplicate Pantry entries.
>
> Make saving the same submitted items idempotent across retries.
> ~~~
>
> </details>

</details>

<details><summary>**sourcery-ai[bot]** on `databricks/fetchers/flipp.py` line 40 · 2026-11-08 05:44 UTC (bot)</summary>

> **🟡 Medium · One fetch error drops a store**
>
> When any one of the concurrent item-detail requests times out or returns a non-success response, a failed or timed-out Flipp item-detail request raises out of `_get()` and `pool.map()`, aborting `rows()` before it writes that store's JSONL file; the store's flyer data is absent until someone reruns the fetch.
>
> Retry transient detail requests and handle per-item failures so one failed request does not discard the entire store's fetch.
>
> <details>
> <summary>Prompt for AI agents</summary>
>
> ~~~markdown
> In `databricks/fetchers/flipp.py` at line 39:
>
> **One fetch error drops a store**
>
> When any one of the concurrent item-detail requests times out or returns a non-success response, a failed or timed-out Flipp item-detail request raises out of `_get()` and `pool.map()`, aborting `rows()` before it writes that store's JSONL file; the store's flyer data is absent until someone reruns the fetch.
>
> Retry transient detail requests and handle per-item failures so one failed request does not discard the entire store's fetch.
> ~~~
>
> </details>

</details>

<details><summary>**sourcery-ai[bot]** on `shared/units.py` · 2026-11-08 05:44 UTC (bot)</summary>

> **🟡 Medium · Packaged items bypass size matching**
>
> When a fixed-size flyer listing's raw text includes a price basis such as `per g` or `/g`, `per_weight()` treats any `per g` or `/g` text as sold by weight, and `same_item()` then skips the size window. A fixed-size listing with that unit-price wording therefore matches users asking for a different quantity.
>
> Only bypass size checks for wording that identifies a product sold by weight, not a unit-price basis for a packaged item.
>
> Also at `apps/api/logic.py:54`.
>
> <details>
> <summary>Prompt for AI agents</summary>
>
> ~~~markdown
> In `shared/units.py` at line 52:
>
> **Packaged items bypass size matching**
>
> When a fixed-size flyer listing's raw text includes a price basis such as `per g` or `/g`, `per_weight()` treats any `per g` or `/g` text as sold by weight, and `same_item()` then skips the size window. A fixed-size listing with that unit-price wording therefore matches users asking for a different quantity.
>
> Only bypass size checks for wording that identifies a product sold by weight, not a unit-price basis for a packaged item.
>
> Also at `apps/api/logic.py:54`.
> ~~~
>
> </details>
>
> ✅ Addressed in a2b90dc2f46c5dce1e4323253a75d6004ab1cc01: `per_weight()` now returns false when `_QTY` finds a fixed quantity in the raw text, so packaged listings with explicit sizes still undergo size matching.

</details>

<details><summary>**sourcery-ai[bot]** on `apps/api/store.py` · 2026-11-08 05:44 UTC (bot)</summary>

> **security (python.sqlalchemy.security.sqlalchemy-execute-raw-query):** Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option.
>
> *Source: opengrep*
>
> ✅ Addressed in a6b38ad1518f1d43fbe9fc44545188e1097659e0

</details>

<details><summary>**sourcery-ai[bot]** on `apps/api/store.py` · 2026-11-08 05:44 UTC (bot)</summary>

> **security (python.sqlalchemy.security.sqlalchemy-execute-raw-query):** Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option.
>
> *Source: opengrep*
>
> ✅ Addressed in 2aa88b6e06a8e46b9065514052e33a6e3ce89c13

</details>

<details><summary>**sourcery-ai[bot]** on `apps/api/store.py` · 2026-11-08 05:44 UTC (bot)</summary>

> **security (python.sqlalchemy.security.sqlalchemy-execute-raw-query):** Avoiding SQL string concatenation: untrusted input concatenated with raw SQL query can result in SQL Injection. In order to execute raw query safely, prepared statement should be used. SQLAlchemy provides TextualSQL to easily used prepared statement with named parameters. For complex SQL composition, use SQL Expression Language or Schema Definition Language. In most cases, SQLAlchemy ORM will be a better option.
>
> *Source: opengrep*
>
> ✅ Addressed in a6b38ad1518f1d43fbe9fc44545188e1097659e0

</details>

