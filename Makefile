.DEFAULT_GOAL := help
SHELL := /bin/bash

BACKEND := backend
FRONTEND := frontend

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────
.PHONY: install
install: install-backend install-frontend ## Install all dependencies

.PHONY: install-backend
install-backend: ## Install Python dependencies
	cd $(BACKEND) && python -m pip install -e ".[dev]"

.PHONY: install-frontend
install-frontend: ## Install Node dependencies
	cd $(FRONTEND) && npm install

# ── Run ──────────────────────────────────────────────────────────────────────
.PHONY: seed
seed: ## Create schema + seed the curriculum graphs
	cd $(BACKEND) && python -m app.db.seed

.PHONY: api
api: ## Run the FastAPI server (http://localhost:8000)
	cd $(BACKEND) && python -m uvicorn app.main:app --reload --port 8000

.PHONY: web
web: ## Run the Next.js dev server (http://localhost:3000)
	cd $(FRONTEND) && npm run dev

# NOTE: `next build` and `next dev` share .next/. Running a production build
# while the dev server is up wipes the chunks it is serving, and the app then
# 404s its own JavaScript while still returning 200 for the page — which looks
# exactly like a hydration bug. Stop `make web` before `make build-web`.
.PHONY: build-web
build-web: ## Production build of the frontend (stop `make web` first)
	cd $(FRONTEND) && npm run build

.PHONY: up
up: ## Run the full stack in Docker
	docker compose up --build

.PHONY: down
down: ## Stop the Docker stack
	docker compose down

# ── Quality ──────────────────────────────────────────────────────────────────
.PHONY: test
test: ## Run backend tests
	cd $(BACKEND) && python -m pytest -q

.PHONY: lint
lint: ## Lint backend + frontend
	cd $(BACKEND) && python -m ruff check app tests
	cd $(FRONTEND) && npm run lint

.PHONY: format
format: ## Auto-format backend
	cd $(BACKEND) && python -m ruff format app tests && python -m ruff check --fix app tests

.PHONY: typecheck
typecheck: ## Type-check both sides
	cd $(BACKEND) && python -m mypy app
	cd $(FRONTEND) && npm run typecheck

.PHONY: check
check: lint typecheck test ## Everything CI runs
