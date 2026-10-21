.PHONY: dev test lint

dev:
	docker compose up

test:
	cd backend && uv run pytest

lint: frontend/node_modules
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

frontend/node_modules: frontend/package-lock.json
	cd frontend && npm ci
