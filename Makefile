.PHONY: setup dev api web tunnel test lint gen-api check-api flipp-snapshot flyer-snapshot databricks-setup

setup:            ## install Python (uv) and web (npm) dependencies
	uv sync
	npm --prefix apps/web ci
	@test -f .env || cp .env.example .env

# Loopback by default: the tunnel connects locally, and a direct LAN client could forge the visitor-IP headers.
# Testing from another device on a trusted network: make dev WEB_HOST=0.0.0.0
WEB_HOST ?= 127.0.0.1

dev:              ## run API on :8000 and PWA on :3000 together; Ctrl-C stops both
	@trap 'kill 0' INT TERM EXIT; $(MAKE) api & $(MAKE) web & wait

api:
	uv run --env-file .env uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

web:
	npm --prefix apps/web run dev -- --hostname $(WEB_HOST)

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

flyer-snapshot: flipp-snapshot  ## same as flipp-snapshot (the name the README uses)

flipp-snapshot:    ## download this week's flyers now (the API also does this itself); POSTAL=M5V2T6 for elsewhere
	uv run python apps/api/snapshot_flipp.py $(POSTAL)

databricks-setup:  ## ONE-TIME, writes to your workspace: Delta tables, the saved flyers, and the Genie space (see the script)
	uv run --env-file .env python databricks/setup/create_genie_space.py
