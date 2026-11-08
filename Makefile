.PHONY: setup dev api web tunnel test lint gen-api check-api flipp-snapshot

setup:            ## install Python (uv) and web (npm) dependencies
	uv sync
	npm --prefix apps/web ci
	@test -f .env || cp .env.example .env

dev:              ## run API on :8000 and PWA on :3000 together; Ctrl-C stops both
	@trap 'kill 0' INT TERM EXIT; $(MAKE) api & $(MAKE) web & wait

api:
	uv run --env-file .env uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

web:
	npm --prefix apps/web run dev -- --hostname 0.0.0.0

tunnel:           ## HTTPS URL for your phone (run alongside make dev; needs: brew install cloudflared)
	cloudflared tunnel --no-autoupdate --url http://localhost:3000

test:
	uv run pytest -q
	npm --prefix apps/web run test

lint:
	uv run ruff check .
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck

gen-api:          ## regenerate the typed web client after changing apps/api
	uv run python -c "import json; from apps.api.main import app; print(json.dumps(app.openapi(), indent=2))" > apps/web/openapi.json
	npm --prefix apps/web run gen:api

check-api: gen-api  ## CI: fail if the committed client is stale
	git diff --exit-code apps/web/openapi.json apps/web/src/lib/api-schema.ts

flipp-snapshot:    ## refresh mock data with this week's real prices from Flipp (apps/api/data/flipp_snapshot.json)
	uv run python apps/api/snapshot_flipp.py
