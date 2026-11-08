<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:248A3D,100:30D158&height=160&section=header&text=Real%20Deal&fontSize=50&fontColor=ffffff&animation=fadeIn" width="100%" alt="Real Deal" />
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com/?font=Fira+Code&size=20&pause=1200&color=30D158&center=true&vCenter=true&width=640&lines=Weekly+flyers+from+5+Vancouver+chains;Matched+to+what+you+actually+buy;Cheapest+store+for+your+whole+basket;Built+on+Databricks+%2B+Claude" alt="Weekly flyers from 5 Vancouver chains, matched to what you actually buy, cheapest store for your whole basket, built on Databricks + Claude" />
</p>

<p align="center">
  <img src="docs/assets/demo.gif" width="300" alt="Demo: My List populated, adding 2% milk 4 L by typing it, the parsed confirm screen, the item landing back in My List, matched in Deals, and the Basket split-shop view" />
</p>

# Real Deal

Weekly grocery flyers from five Vancouver chains, matched to what a UBC student actually buys (learned from their
receipts), with the cheapest store for the whole basket. Mobile-first PWA, HackCamp 2026, Databricks track.

- Spec: [`docs/superpowers/specs/Real Deal — MVP Design.md`](docs/superpowers/specs/Real%20Deal%20—%20MVP%20Design.md)
- Plan, workstreams, go/no-go, cut list: [`docs/plan.md`](docs/plan.md)

## Setup (every teammate)

Prereqs: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Node 20+, make (macOS/Linux; Windows uses dev.cmd), git.
WS1 also needs the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html).

```sh
git clone https://github.com/krish-arora-88/SurRealDeal.git && cd SurRealDeal
make setup   # uv sync + npm ci + copies .env.example to .env
make dev     # API on :8000, PWA on :3000; Ctrl-C stops both
```

On Windows, use the command file instead of `make setup` and `make dev`:

```powershell
.\dev.cmd setup  # install dependencies and create .env if it doesn't exist
.\dev.cmd dev    # start both servers; Ctrl-C stops them
```

`dev.cmd dev` refuses to start until setup has installed apps/web/node_modules and created .env.

Open http://localhost:3000. With an empty `.env` everything runs on **mock data**: a new device gets five seeded
list items, mock flyers for five stores, canned receipt and voice extraction. API docs: http://localhost:8000/docs.

On your phone: run `make tunnel` in a second terminal (`brew install cloudflared` once) and open the
`https://….trycloudflare.com` URL it prints. Campus Wi-Fi (eduroam) blocks phone-to-laptop traffic, and the camera,
mic and home-screen install need HTTPS anyway. The URL changes each run.

Other targets: `make test` (pytest), `make lint` (ruff + eslint + tsc), `make gen-api` (regenerate the typed web
client after changing the API; CI fails if you forget), `make flipp-snapshot` (download this week's
flyers now — see "Flyer data: Flipp integration" below).

## Environment variables

| Variable | Used by | Blank means |
| --- | --- | --- |
| `DATABRICKS_HOST` | API, fetchers, setup scripts | API runs in mock mode |
| `DATABRICKS_TOKEN` | same | |
| `DATABRICKS_WAREHOUSE_ID` | API (SQL Statement API) | |
| `ANTHROPIC_API_KEY` | API extractor (receipts, photos, manual text) | mock extractor |
| `ELEVENLABS_API_KEY` | API voice proxy | canned transcript |

Overrides: `REALDEAL_MOCK=0|1`, `EXTRACTOR=mock|claude|databricks`, `ANTHROPIC_MODEL`, `API_URL` (web → API proxy target).
Never commit `.env`.

## Flyer data: Flipp integration

Real flyer data comes from [Flipp](https://flipp.com)'s public, unauthenticated flyer API
(`https://backflipp.wishabi.com/flipp`) via `shared/flipp.py` — unofficial, so the client is throttled
(0.5 s between calls), retries once, times out at 20 s, and sends a descriptive User-Agent. Endpoints used:

| Endpoint | Gives us |
| --- | --- |
| `GET /flyers?locale=en-ca&postal_code=<postal>` | This week's flyers for a postal code; filtered to the merchant + a `categories_csv` containing "Groceries" (a merchant can run non-grocery flyers too, e.g. Superstore's Toy Book) |
| `GET /flyers/{id}?locale=en-ca` | A flyer's item list + pages. `pages[]` carries no image URL (confirmed live on five flyers) |
| `GET /items/{item_id}` | Full item detail: `description` (sometimes a size, often not), `current_price`, `image_url` (a product photo, not the page) |

`to_extracted_item()` parses an item (+ detail) into the same `ExtractedItem` shape every other extraction
mode returns, reading size from `description` first and falling back to parsing it out of the product name;
rows with no price anywhere are skipped. `fetch_grocery_flyer()` only spends the extra `/items/{id}` call when
the list data alone didn't already give a price and a parseable size.

**Fetcher** (`databricks/fetchers/flipp.py`, all five stores) writes `flyers/<store>/<week_start>/flipp.jsonl`
to the Volume with each item's exact tile box, page, price and valid dates; the pipeline turns it into
`flyer_items` (see `docs/plan.md`, WS1 step 6). Page images saved by hand still go through
`databricks/fetchers/common.py <store> <dir>`.

**Mock mode with live flyers** (the default for `make dev`): the API pulls this week's real flyers from Flipp's public
API (`apps/api/flyers_live.py`), one set per postal code. It saves them under `apps/api/data/` (gitignored), serves
requests from memory, and checks Flipp hourly, re-downloading only the stores whose flyer changed (everything once
a day). The first run for a postal code downloads in the background, about 30 seconds; the app shows a loading state
until it lands. The app sends the shopper's postal code in an `X-Postal-Code` header (set from the Flyers tab);
`DEFAULT_POSTAL_CODE` (default `V6T1Z4`) is used when there is none. `make flipp-snapshot [POSTAL=M5V2T6]`
forces a download now. `REALDEAL_LIVE_FLYERS=0` turns this off and serves the small canned list (tests and CI do).
Flipp's API is unofficial, so treat this as demo data.

**Real flyer pages.** Flipp's website draws each flyer from a pyramid of 256 px image tiles
(`f.wishabi.net/<flyer path>/<level>_<col>_<row>.jpg`, rows counted from the bottom). When someone opens a page, the
API fetches just that page's tiles, stitches them into the real printed page (about 1 MB) and keeps it under
`apps/api/data/pages/`; the Price Match screen shows it with the item outlined. Pages next to it are drawn in the
background, and pages of ended flyers are deleted. If Flipp has no tiles for a page, the app lays the page out from the
items' own pictures instead.

**Databricks and Genie (optional, you switch it on).** `make databricks-setup` is a one-time step that writes to your
workspace: it creates `realdeal.core.live_listings` and `price_history`, loads the flyers already downloaded, and creates
a Genie space over them. Then set `REALDEAL_DATABRICKS_SYNC=1` in `.env` and every refresh keeps the tables current
(price history builds up week by week). Once the space exists the Flyers tab shows an **Ask** button: plain-language
questions answered by Genie, with the table and the SQL it wrote. Nothing is written to Databricks unless you do this.

**Optional live match fallback**: if AI Search and the SQL `LIKE` fallback both come up empty for a saved
item, `apps/api/store.py` tries one cached (1 h) Flipp search and scores results with the usual
`logic.match_score` threshold — the only network call allowed on a request path, and only reached when both
of the normal paths already failed.

## Claim a workstream

Four workstreams (Data/Pipeline, Backend, Frontend, Design & Pitch) are in [`docs/plan.md`](docs/plan.md), each with
ordered tasks, the interface it must not break, and its done-when. Put your GitHub handle on its `Owner:` line, branch
as `ws<N>/<topic>`, and open small PRs to `main`. CI (pytest, ruff, eslint, tsc, build, OpenAPI drift) must pass.

## Workstream 3: Frontend — status

Done, on [`ws3/polish`](https://github.com/krish-arora-88/SurRealDeal/pull/3) (owner: [@TahaSaiyed08](https://github.com/TahaSaiyed08)):

- Intake bottom sheet from My List: receipt photo, product photo, manual text, hold-to-talk voice
  (`src/components/list/{AddMethodsSheet,ReceiptConfirmSheet,PickProductSheet,TypeOrSaySheet}.tsx`)
- Confirm screens flag low-confidence rows (`confidence < 0.6`) for edit before `POST /items`; product photo
  shows a chip picker over the extractor's candidates
- Deals (exact matches only: brand, item, variant and size) and Basket (cheapest store, split-shop, dollar delta,
  "no deal this week") tabs
- Client-side image downscale (≤2000px, JPEG q0.8) before every upload; avoids the API's 413 and normalizes
  iPhone HEIC
- Error handling throughout: status-mapped upload errors (413/415/429 with `Retry-After`), a save-retry banner
  instead of losing confirmed items on failure, optimistic delete with rollback, `AbortController` + 30s
  timeout per intake call, revoked object URLs
- Voice: aria-labelled hold-to-talk, empty-recording and unsupported-browser messages, a released-before-start
  guard and stream cleanup on `MediaRecorder` failure
- `/dev/states` (the reviewer-only screen gallery) is gated out of production builds
- One Playwright smoke test (`apps/web/e2e/smoke.spec.ts`): opens the PWA, adds an item manually, confirms the
  match in Deals — wired into CI alongside `pytest`/`ruff`/`eslint`/`tsc`/`next build`/`make check-api`

## Layout

```
apps/api/        FastAPI: routes (main.py), models mirroring the tables, extractors, SQL client, STT proxy
apps/web/        Next.js 15 PWA: 3 tabs, HIG tokens (src/app/globals.css), typed client (src/lib/)
shared/          normalize_unit + tests, versioned prompts (flyer_page, receipt, product, manual)
databricks/      sql/ (DDL), pipeline/ (Lakeflow Bronze→Silver→Gold), fetchers/ (Flipp, all 5 stores), setup/
databricks.yml   Asset bundle for the pipeline
.mcp.json        Databricks docs MCP (devhub-docs) for Claude Code
```

## Claude Code

`.mcp.json` registers the Databricks developer docs MCP server (`devhub-docs`). Claude Code asks you to approve it
the first time you open the repo; then ask it things like "how do I trigger a Lakeflow pipeline update".
