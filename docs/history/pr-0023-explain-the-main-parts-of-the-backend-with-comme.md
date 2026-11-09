# #23: Explain the main parts of the backend with comments

*Archived copy of [krish-arora-88/SurRealDeal#23](https://github.com/krish-arora-88/SurRealDeal/pull/23). The original, with its live discussion, stays in that repository.*

| | |
|---|---|
| **State** | merged |
| **Author** | TahaSaiyed08 |
| **Opened** | 2026-11-08 15:33 UTC |
| **Merged** | 2026-11-08 15:35 UTC by TahaSaiyed08 |
| **Closed** | — |
| **Branch** | `ws3/explain-code-comments` → `main` |
| **Size** | 18 files, +318 / −13, 34 commits |

## Description

> ## What this does
>
> 34 small commits that add explanatory comments to the backend, one logical area per commit, so the main ideas are written down where the code is. **No behavior changes.**
>
> Covered: `models.py` (API contract, bounding boxes), `logic.py` (words, sizes, exact matching, deals, basket totals, search ranking), `main.py` (the two modes, rate limiter, identity headers, endpoints), `store.py`, `flyers_live.py` (feeds, refresh, page-image cache), `shared/flipp.py` (client, name/size parsing, page stitching), `databricks_sql.py`, `databricks_sync.py`, `genie.py`, `refine.py`, `extractors.py`, `units.py`, `mock_data.py`, `stt.py`, the Genie setup scripts and a few small files.
>
> Two docstrings in `shared/flipp.py` were out of date (they said Flipp has no page images, and who calls `fetch_grocery_flyer`); they are corrected.
>
> ## How it was checked
> - Every commit was compared with its parent: for Python the syntax tree (ignoring docstrings) is identical, so only comments and docstrings changed. 34 of 34 commits pass.
> - `ruff` clean, `pytest` 244 passed.
>
> ## Merging
> Please use **"Create a merge commit"** or **"Rebase and merge"**, not "Squash and merge", so the commits stay separate.
>
> ## Not in this PR
> Frontend files are not commented yet. Noticed while reading, left for a separate change: the first Genie example SQL in `databricks/setup/genie_space.py` uses `LIKE '%milk%'`, which contradicts the whole-word instruction above it.
>
> ## Summary by Sourcery
>
> Document the backend’s main concepts and workflows with in-code explanations without changing application behavior.
>
> Bug Fixes:
> - Correct outdated Flipp documentation to describe page-image stitching and the current flyer-fetching path.
>
> Enhancements:
> - Add explanatory comments and docstrings throughout the backend to document API contracts, data flow, matching and ranking rules, storage modes, refresh behavior, external integrations, and operational safeguards.

## Commits (34)

- `e4e3dab` Explain the API contract, bounding boxes and table layers in models.py — TahaSaiyed08
- `96029a1` Explain list, flyers-browse, Ask and basket response shapes in models.py — TahaSaiyed08
- `fd87e45` Explain how words, sizes and exact matching work in logic.py — TahaSaiyed08
- `578096e` Explain cost, deals, savings and basket totals in logic.py — TahaSaiyed08
- `d3ebb53` Explain search ranking and the Flyers browse pipeline in logic.py — TahaSaiyed08
- `1b0a7db` Wrap an over-long comment in models.py — TahaSaiyed08
- `5ffaedb` Explain the two API modes and the intake rate limiter in main.py — TahaSaiyed08
- `1231dd9` Explain identity headers, uploads and the intake endpoints in main.py — TahaSaiyed08
- `0954c15` Explain list, comparison and flyer-page endpoints in main.py — TahaSaiyed08
- `048e531` Shorten a comment in main.py — TahaSaiyed08
- `416a012` Explain feeds, timing and the on-disk copy in flyers_live.py — TahaSaiyed08
- `d341630` Explain the read path and real page-image caching in flyers_live.py — TahaSaiyed08
- `0d2ddb7` Explain the refresh, labelling and sync steps in flyers_live.py — TahaSaiyed08
- `81294e6` Explain the Flipp client, constants and name-parsing patterns in flipp.py — TahaSaiyed08
- `54270e9` Explain how flyer names, sizes and tile positions are parsed in flipp.py — TahaSaiyed08
- `bc1d7cb` Explain flyer download and page-image stitching in flipp.py — TahaSaiyed08
- `5f044f9` Correct a docstring about who calls fetch_grocery_flyer — TahaSaiyed08
- `d9c4bb9` Explain the mock and Databricks backends and flyer loading in store.py — TahaSaiyed08
- `9c08775` Explain list reads and writes in store.py — TahaSaiyed08
- `a4a71b2` Wrap a comment in store.py — TahaSaiyed08
- `73b7ee0` Explain the Databricks SQL client and its last-good cache in databricks_sql.py — TahaSaiyed08
- `1bf3a29` Explain Ask and the Genie client in genie.py — TahaSaiyed08
- `f450d09` Explain the Databricks sync tables, batching and MERGE in databricks_sync.py — TahaSaiyed08
- `f0ea8c3` Explain the refiner's cost controls, cache and safety guard in refine.py — TahaSaiyed08
- `4204ca1` Remove a duplicated comment in refine.py — TahaSaiyed08
- `30ace42` Explain base units, size parsing and unit prices in units.py — TahaSaiyed08
- `607ea68` Explain the extractor interface and the Claude extractor in extractors.py — TahaSaiyed08
- `7772890` Explain the Databricks and mock extractors and how one is chosen in extractors.py — TahaSaiyed08
- `68a9865` Explain the canned flyers and starter pantry in mock_data.py — TahaSaiyed08
- `80d29ca` Explain the speech-to-text proxy in stt.py — TahaSaiyed08
- `71ea581` Explain the manual snapshot script in snapshot_flipp.py — TahaSaiyed08
- `ab28251` Explain how extraction prompts are versioned in shared/__init__.py — TahaSaiyed08
- `1fad0f8` Explain the Genie space definition in genie_space.py — TahaSaiyed08
- `9cae7e6` Explain the one-time Genie setup script in create_genie_space.py — TahaSaiyed08

## Conversation (2)

<details><summary>**sourcery-ai[bot]** · 2026-11-08 15:33 UTC (bot)</summary>

> Sorry @TahaSaiyed08, you've used your own review budget of 250,000 diff characters for the last 7 days.
>
> You can request another review in 6 days and 10 hours by commenting `@sourcery-ai review`. [Upgrade](https://app.sourcery.ai/dashboard/billing?connection=github&owner=krish-arora-88&from_surface=github_bot&intent=rate_limit_hit) to get a review now.

</details>

<details><summary>**sourcery-ai[bot]** · 2026-11-08 15:33 UTC (bot)</summary>

> <!-- Generated by sourcery-ai[bot]: start review_guide -->
>
> ## Reviewer's Guide
>
> ### Data structures
>
> Explain the API models and the flyer, user-item, deal, browse, and basket data structures that the backend relies on.
> - `apps/api/models.py` L35-42, L65-68, L178-181 (+12 small edits)
>
> ### API
>
> Document the API’s operating modes, request limits and headers, intake flow, item and comparison routes, and flyer and Genie endpoints.
> - `apps/api/main.py` L41-47 (+19 small edits)
>
> ### Implementation
>
> Explain how matching, deal costs, savings, search ranking, flyer browsing, and basket totals are computed, alongside the shared unit conversions those calculations use.
> - `apps/api/logic.py` L39-297 (19 small edits)
> - `shared/units.py` L6-78 (7 small edits)
>
> Explain live flyer feed loading, refresh and sync behavior, caching, and the Flipp client’s parsing and page-image stitching.
> - `apps/api/flyers_live.py` L52-55 (+25 small edits)
> - `shared/flipp.py` L48-56, L80-84, L97-103 (+26 small edits)
>
> Document the storage abstraction’s mock and Databricks modes, flyer loading, and item reads and writes.
> - `apps/api/store.py` L20-27 (+13 small edits)
>
> Explain Databricks SQL execution and fallback caching, flyer-table synchronization, and Genie question handling.
> - `apps/api/databricks_sql.py` L17-25 (+5 small edits)
> - `apps/api/databricks_sync.py` L20-24 (+10 small edits)
> - `apps/api/genie.py` L17-24 (+3 small edits)
>
> Document the extraction backends and their selection, plus the refiner’s batching, cache, and output safeguards.
> - `apps/api/extractors.py` L20-185 (12 small edits)
> - `apps/api/refine.py` L32-41 (+7 small edits)
>
> Explain the canned flyer data, starter pantry items, and speech-to-text proxy used by the backend.
> - `apps/api/mock_data.py` L47-51 (+5 small edits)
> - `apps/api/stt.py` L6-7, L15-16, L30
>
> ### Configuration
>
> Explain the Genie space definition and the setup script that creates or updates it, as well as the manual Flipp snapshot and shared extraction-prompt versioning.
> - `apps/api/snapshot_flipp.py` L17
> - `databricks/setup/create_genie_space.py` L19-75 (5 small edits)
> - `databricks/setup/genie_space.py` L11-15 (+4 small edits)
> - `shared/__init__.py` L3-4
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
> - Keep in touch with the Sourcery team by following us on [X/Twitter](https://x.com/SourceryAI), [LinkedIn](https://www.linkedin.com/company/sourcery-ai/) or [GitHub](https://github.com/sourcery-ai).
>
> </details>
>
> <!-- Generated by sourcery-ai[bot]: end review_guide -->

</details>

## Reviews (0)

## Inline code comments (0)

