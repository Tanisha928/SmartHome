.PHONY: up down migrate test lint seed health openapi

up:
	docker compose up -d postgres mongo localstack
	@echo "Waiting for infra..."
	@sleep 3
	docker compose up -d backend model-worker sweepers frontend

down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && python -m pytest tests/unit -q
	@if [ -d frontend/node_modules ]; then cd frontend && npm test -- --run; fi

lint:
	cd backend && ruff check app tests && mypy --strict app || true

seed:
	cd backend && python ../scripts/seed_dev_data.py

health:
	curl -sf http://localhost:8000/healthz | python -m json.tool

openapi:
	curl -sf http://localhost:8000/openapi.json -o docs/openapi.json
	@echo "Wrote docs/openapi.json"
