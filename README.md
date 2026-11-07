# Real Deal

Weekly grocery flyers from five Vancouver chains, matched to what a UBC student actually buys (learned from their
receipts), with the cheapest store for the whole basket. Mobile-first PWA, HackCamp 2026, Databricks track.

- Spec: [`docs/superpowers/specs/Real Deal — MVP Design.md`](docs/superpowers/specs/Real%20Deal%20—%20MVP%20Design.md)
- Plan, workstreams, go/no-go, cut list: [`docs/plan.md`](docs/plan.md)

## Setup (every teammate)

Prereqs: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Node 20+, [make](https://gnuwin32.sourceforge.net/packages/make.htm), git.
WS1 also needs the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html).

```sh
git clone https://github.com/krish-arora-88/SurRealDeal.git && cd SurRealDeal
make setup   # uv sync + npm ci + copies .env.example to .env
make dev     # API on :8000, PWA on :3000; Ctrl-C stops both
```

Open http://localhost:3000. With an empty `.env` everything runs on **mock data**: a new device gets five seeded
list items, mock flyers for five stores, canned receipt and voice extraction. API docs: http://localhost:8000/docs.

On your phone: run `make tunnel` in a second terminal (`brew install cloudflared` once) and open the
`https://….trycloudflare.com` URL it prints. Campus Wi-Fi (eduroam) blocks phone-to-laptop traffic, and the camera,
mic and home-screen install need HTTPS anyway. The URL changes each run.

Other targets: `make test` (pytest), `make lint` (ruff + eslint + tsc), `make gen-api` (regenerate the typed web
client after changing the API; CI fails if you forget).

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

## Claim a workstream

Four workstreams (Data/Pipeline, Backend, Frontend, Design & Pitch) are in [`docs/plan.md`](docs/plan.md), each with
ordered tasks, the interface it must not break, and its done-when. Put your GitHub handle on its `Owner:` line, branch
as `ws<N>/<topic>`, and open small PRs to `main`. CI (pytest, ruff, eslint, tsc, build, OpenAPI drift) must pass.

## Layout

```
apps/api/        FastAPI: routes (main.py), models mirroring the tables, extractors, SQL client, STT proxy
apps/web/        Next.js 15 PWA: 3 tabs, HIG tokens (src/app/globals.css), typed client (src/lib/)
shared/          normalize_unit + tests, versioned prompts (flyer_page, receipt, product, manual)
databricks/      sql/ (DDL, views), pipeline/ (Lakeflow Bronze→Silver→Gold), fetchers/ (one per store), setup/
databricks.yml   Asset bundle for the pipeline
.mcp.json        Databricks docs MCP (devhub-docs) for Claude Code
```

## Claude Code

`.mcp.json` registers the Databricks developer docs MCP server (`devhub-docs`). Claude Code asks you to approve it
the first time you open the repo; then ask it things like "how do I trigger a Lakeflow pipeline update".
