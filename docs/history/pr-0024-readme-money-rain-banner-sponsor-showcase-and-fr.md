# #24: README: money-rain banner, sponsor showcase and fresh screenshots

*Archived copy of [krish-arora-88/SurRealDeal#24](https://github.com/krish-arora-88/SurRealDeal/pull/24). The original, with its live discussion, stays in that repository.*

| | |
|---|---|
| **State** | merged |
| **Author** | TahaSaiyed08 |
| **Opened** | 2026-11-08 15:57 UTC |
| **Merged** | 2026-11-08 15:59 UTC by TahaSaiyed08 |
| **Closed** | — |
| **Branch** | `docs/readme-sponsor-showcase` → `main` |
| **Size** | 18 files, +934 / −83, 3 commits |

## Description

> ## What this does
>
> A rewrite of the README around the app as it runs today, with animated art.
>
> - **Banner and rain dividers.** A falling money-rain banner (title always readable, rotating tagline, swinging price tag) and a thin rain strip between every section, so the rain runs from top to bottom. GitHub strips CSS/JS from READMEs, so these are self-contained animated SVGs.
> - **See it.** An animated phone that cycles through the real Flyers, Price Match, Pantry, Basket, voice and Ask screens, plus a screenshot gallery taken from the running app. The stale `demo.gif` is removed.
> - **Sponsor sections**, each with an animated card and a table of what we actually built:
>   - **Databricks**: bricks stack up (Unity Catalog tables, Lakeflow, SQL Statement API, Genie, Model Serving, `ai_query`, Volumes, Databricks App).
>   - **ElevenLabs**: a voice wave becomes "add a 4 L jug of 2% milk", then a list item.
>   - **Figma**: the five shapes assemble the logo, then design frames fill with the real screens.
>   - **Devpost**: the submission card.
> - **Current content.** How it works, a Mermaid architecture diagram, and a "what is built" list. Fixed stale parts: the old Deals tab and "five stores", a duplicated Flipp endpoint row, the claim that Flipp has no page images, and missing env vars (sync, Genie, AI refiner, live flyers). The setup and Databricks App hosting guides are kept.
> - **Ask fix.** The Ask sheet showed Genie's `**bold**` as literal asterisks (visible in the screenshot); it now renders bold. Separate commit.
>
> All the art is built by `docs/assets/generate.py` from the screenshots in `docs/assets/screens/` (exempted from the line-length lint rule since it is mostly SVG markup).
>
> ## Things to check on the rendered page
> - The animations play in GitHub's `<img>` rendering (verified locally in a browser at the README's column width, not yet on GitHub itself).
> - The four sponsor logos are simple redraws, not official artwork; swap in the real files if wanted.
> - The Devpost link is not known: there is a comment in the README marking where to add it.
>
> ## Checks
> - `ruff` clean, `pytest` 244 passed
> - web: `tsc`, `eslint` clean, `vitest` 53 passed; the Ask and price-match Playwright tests pass (full e2e suite not re-run)
>
> ## Summary by Sourcery
>
> Refresh the project documentation with animated product and sponsor showcases, current implementation details, and a fix for formatted Genie answers.
>
> New Features:
> - Add a media-rich README showcasing the current app, real screenshots, sponsor integrations, architecture, capabilities, setup, and deployment guidance.
> - Add generated self-contained animated SVG artwork for the README, including banners, section dividers, app walkthroughs, and sponsor showcases.
>
> Bug Fixes:
> - Render bold formatting in Genie Ask responses instead of displaying literal Markdown asterisks.
>
> Enhancements:
> - Refresh README content to reflect live flyer behavior, current application functionality, configuration, and optional Databricks features while removing stale or duplicated information.
>
> Build:
> - Exclude the generated README asset script from Ruff line-length checks.
>
> Documentation:
> - Rewrite the README around the current product experience, sponsor contributions, architecture, setup, environment variables, flyer integration, and built functionality.
> - Add real application screenshots and document the SVG asset generation workflow.
>
> Chores:
> - Remove the obsolete demo GIF and add source screenshots used by the README artwork.

## Commits (3)

- `fa150a2` Ask: show Genie's **bold** as bold instead of literal asterisks — TahaSaiyed08
- `02a4356` Add animated README art: money-rain banner, rain dividers, phone demo and sponsor cards — TahaSaiyed08
- `523e155` README: rewrite with the current app, sponsor sections and fresh screenshots — TahaSaiyed08

## Conversation (2)

<details><summary>**sourcery-ai[bot]** · 2026-11-08 15:57 UTC (bot)</summary>

> Sorry @TahaSaiyed08, you've used your own review budget of 250,000 diff characters for the last 7 days.
>
> You can request another review in 6 days and 10 hours by commenting `@sourcery-ai review`. [Upgrade](https://app.sourcery.ai/dashboard/billing?connection=github&owner=krish-arora-88&from_surface=github_bot&intent=rate_limit_hit) to get a review now.

</details>

<details><summary>**sourcery-ai[bot]** · 2026-11-08 15:57 UTC (bot)</summary>

> <!-- Generated by sourcery-ai[bot]: start review_guide -->
>
> ## Reviewer's Guide
>
> ### Implementation
>
> Add a Python generator that builds the README’s self-contained animated SVG artwork from screenshots and code-drawn graphics.
> - `docs/assets/generate.py` L1-533
>
> ### UI
>
> Render Genie’s `**bold**` answer text as bold in the Ask sheet rather than displaying literal asterisks.
> - `apps/web/src/components/AskSheet.tsx` L12-18, L81-82
>
> ### Configuration
>
> Exclude the SVG-heavy README asset generator from Ruff’s line-length check so its markup remains readable.
> - `pyproject.toml` L31-34
>
> ### Documentation
>
> Rewrite the README around the current app, its workflow and architecture, setup and hosting, sponsor integrations, and fresh screenshots.
> - `README.md` L2-141, L184-195, L278-341 (+7 small edits)
>
> ### Lock files and vendored code
>
> Replace the stale demo recording and add generated SVG artwork and screenshot images referenced by the README.
> - `docs/assets/banner.svg` L1-35
> - `docs/assets/databricks.svg` L1-31
> - `docs/assets/devpost.svg` L1-10
> - `docs/assets/elevenlabs.svg` L1-14
> - `docs/assets/figma.svg` L1-26
> - `docs/assets/phone-demo.svg` L1-33
> - `docs/assets/rain-divider.svg` L1-24
> - `docs/assets/demo.gif`
> - `docs/assets/screens/ask.jpg`
> - `docs/assets/screens/basket.jpg`
> - `docs/assets/screens/flyers.jpg`
> - `docs/assets/screens/pantry.jpg`
> - `docs/assets/screens/pricematch.jpg`
> - `docs/assets/screens/voice.jpg`
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

