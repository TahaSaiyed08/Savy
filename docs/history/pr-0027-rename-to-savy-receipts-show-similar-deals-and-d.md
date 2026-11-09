# #27: Rename to Savy; receipts show similar deals and drop produce quantity

*Archived copy of [krish-arora-88/SurRealDeal#27](https://github.com/krish-arora-88/SurRealDeal/pull/27). The original, with its live discussion, stays in that repository.*

| | |
|---|---|
| **State** | merged |
| **Author** | TahaSaiyed08 |
| **Opened** | 2026-11-08 18:20 UTC |
| **Merged** | 2026-11-08 18:22 UTC by TahaSaiyed08 |
| **Closed** | — |
| **Branch** | `feat/savy-rename-and-receipt-deals` → `main` |
| **Size** | 23 files, +326 / −49, 6 commits |

## Description

> ## What this does
>
> **1. Renamed to Savy** (everything people see): the browser-tab and home-screen title, the PWA manifest, the unlock page, the API docs title, the README and its animated banner, the docs (the design spec file is renamed too), the Databricks setup text and the Flipp User-Agent.
> Internal names are unchanged so nothing existing breaks: the `realdeal` Databricks catalog and tables, the `REALDEAL_*` settings, the browser storage keys (renaming them would reset everyone's theme, postal code and list), package names and the repo name. The Genie setup now also recognises the old space title, so the next `make databricks-setup` renames the existing space instead of creating a second one.
>
> **2. "Original flyer" opens in a new tab.** It already used `target="_blank"` with `noopener`; this adds a real-browser test proving it opens a second tab at the store's page, leaves the app on Price Match, and the new tab cannot reach back via `window.opener`. Not tested on a physical iPhone.
>
> **3. Receipts** (only the receipt path changes; typed lines, product photos and flyers are untouched):
> - **Similar deals on the confirm screen.** Under each scanned line, the cheapest similar item on sale now ("On sale: Apples Honeycrisp, $2.99 at Safeway"). It reuses the Flyers tab's search (no API change), looks at the product name only, caches each lookup, and shows nothing if a lookup fails.
> - **Fresh produce keeps no size or quantity** (a receipt records what was weighed, not a pack size). Two layers: a new receipt prompt (v3) tells the model to leave them null, and a tested rule in `/intake/receipt` does the same if a model slips. Packaged and processed food keeps its size ("orange juice", "potato chips", "tomato sauce", "banana bread"). The price stays.
> - **Fixed "Invalid Date"** on the confirm screen: Gemini can return a date and time; the endpoint now returns only the day.
>
> ## Checked
> - `ruff` clean; `pytest` 297 passed; `tsc`, `eslint` clean; `vitest` 53 passed; the full Playwright suite (26 tests, run against its own mock-mode servers) passed.
> - Live, with Gemini and real flyers: the sample receipt returned produce without sizes (packaged goods kept theirs), and all 14 lines got a similar deal.
>
> ## Things to know
> - **Similar matching is by name, so it can be loose** for generic words: "egg" matched Cadbury chocolate eggs and "banana" a steamed banana dessert. Brand/size are deliberately ignored. A follow-up could rank by category.
> - Existing receipts are unaffected; only new scans use the v3 prompt and the rule.
> - The browser-test config reuses a running dev server locally; to run the e2e suite, stop your dev servers first (or set `CI=1`).
>
> ## Summary by Sourcery
>
> Rename the application to Savy and improve receipt confirmation with relevant sale suggestions and more accurate produce extraction.
>
> New Features:
> - Show the cheapest similar flyer deal beneath each newly scanned receipt item on the confirmation screen.
> - Normalize receipt extractions so fresh produce has no size or quantity while packaged and processed foods retain theirs.
>
> Bug Fixes:
> - Prevent invalid receipt dates from appearing as “Invalid Date” by retaining only valid calendar dates.
> - Open store pages from Price Match in a separate, opener-isolated browser tab.
>
> Enhancements:
> - Rename the user-facing product and documentation from Real Deal to Savy while preserving internal compatibility and upgrading existing Genie spaces in place.
>
> Documentation:
> - Update README, design specifications, plans, API documentation, PWA metadata, and generated artwork to use the Savy branding.
>
> Tests:
> - Add coverage for receipt normalization, date handling, prompt versioning, similar receipt deals, and isolated store-page tabs.
>
> Chores:
> - Adopt the v3 receipt extraction prompt with explicit produce handling.

## Commits (6)

- `b6fb508` Rename the product to Savy (everything people see) — TahaSaiyed08
- `d556100` Test that Original flyer opens in a new tab and leaves the app where it was — TahaSaiyed08
- `d1c70ca` Receipts: fresh produce no longer keeps a size or quantity — TahaSaiyed08
- `8ed7ca8` Receipts: show the cheapest similar deal under each scanned line — TahaSaiyed08
- `634a6e2` README: describe the receipt changes — TahaSaiyed08
- `b2e3037` Receipts: fix 'Invalid Date' and let the similar-deal lines wrap — TahaSaiyed08

## Conversation (2)

<details><summary>**sourcery-ai[bot]** · 2026-11-08 18:21 UTC (bot)</summary>

> Sorry @TahaSaiyed08, you've used your own review budget of 250,000 diff characters for the last 7 days.
>
> You can request another review in 6 days and 7 hours by commenting `@sourcery-ai review`. [Upgrade](https://app.sourcery.ai/dashboard/billing?connection=github&owner=krish-arora-88&from_surface=github_bot&intent=rate_limit_hit) to get a review now.

</details>

<details><summary>**sourcery-ai[bot]** · 2026-11-08 18:21 UTC (bot)</summary>

> <!-- Generated by sourcery-ai[bot]: start review_guide -->
>
> ## Reviewer's Guide
>
> ### API
>
> Apply receipt-only cleanup at the intake endpoint, stripping fresh-produce sizes and normalizing the purchase date before saving or returning the extraction.
> - `apps/api/main.py` L15, L54, L184
> - `apps/api/receipts.py` L1-62
>
> ### Uses of the API
>
> Use the existing flyer search from the receipt confirmation sheet to show each scanned line’s cheapest similar deal, while handling date display and allowing deal text to wrap.
> - `apps/web/src/components/list/ReceiptConfirmSheet.tsx` L4-10, L19-64, L180-186 (+3 small edits)
>
> ### Implementation
>
> Add receipt v3 guidance so the model leaves size and quantity unset for fresh produce while retaining packaged-product sizes.
> - `shared/__init__.py` L7
> - `shared/prompts/receipt.v3.md` L1-20
>
> ### UI
>
> Rename user-facing app and API titles to Savy and update the banner artwork and Flipp request identity to match.
> - `apps/api/main.py` L1
> - `apps/web/src/app/layout.tsx` L8-10
> - `apps/web/src/app/manifest.ts` L5-6
> - `apps/web/src/app/unlock/route.ts` L20-23
> - `docs/assets/generate.py` L167, L611
> - `shared/flipp.py` L42
> - `docs/assets/banner.svg` L35 (removed lines)
> - `docs/assets/freebuff.svg` L13 (removed lines)
>
> ### Configuration
>
> Make Genie setup find and rename the existing Real Deal space, and update setup-facing Databricks names without changing internal catalog identifiers.
> - `databricks/setup/create_genie_space.py` L1-69 (5 small edits)
> - `databricks/setup/genie_space.py` L1, L9-11
> - `databricks/sql/ddl.sql` L1
>
> ### Documentation
>
> Update the README and project documentation to use the Savy name and describe the receipt behavior, including renaming the design-spec file.
> - `README.md` L2-436 (6 small edits)
> - `docs/plan.md` L1-3
>
> ### Tests
>
> Test produce detection and preservation of packaged sizes, the receipt endpoint’s cleanup and date normalization, and untouched intake paths.
> - `apps/api/test_receipts.py` L1-90
>
> Verify Original flyer opens safely in a second tab and receipt confirmation shows similar deals with produce sizes omitted.
> - `apps/web/e2e/basket-flyers.spec.ts` L98-117
> - `apps/web/e2e/receipt.spec.ts` L25-48
>
> Update prompt-version assertions to cover receipt v3 while keeping the manual prompt on v2.
> - `shared/test_prompts.py` L11-14
>
> ### Lock files and vendored code
>
> Refresh the checked-in OpenAPI document to reflect the renamed API title.
> - `apps/web/openapi.json` L4
>
> ### Other changes
>
> Files not grouped.
> - `docs/superpowers/specs/Real Deal — MVP Design.md` L1-147 (4 small edits)
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

