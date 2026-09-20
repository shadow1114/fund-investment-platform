PY := .venv/bin/python
PYTEST := .venv/bin/pytest
export PATH := .venv/bin:$(PATH)

.PHONY: test test-unit test-integration test-api-integration test-fitness test-contract lint typecheck check migrate api-dev api-health-check worker-dev api-check frontend-install frontend-dev frontend-api frontend-build frontend-test frontend-e2e frontend-lint frontend-check

test-unit:
	$(PYTEST) tests/unit -v

test-integration:
	$(PYTEST) tests/integration -v -m integration

test-fitness:
	$(PYTEST) tests/fitness -v

test-contract:
	$(PYTEST) tests/contract -v -m contract

test:
	$(PYTEST) tests/unit tests/fitness tests/integration -v

migrate:
	.venv/bin/alembic -x db=dev upgrade head

api-dev:
	PYTHONPATH=src .venv/bin/uvicorn fip.api.app:app --reload

api-health-check:
	curl --fail http://127.0.0.1:8000/health/ready

worker-dev:
	PYTHONPATH=src .venv/bin/python -m fip.platform.jobs.worker

api-check:
	LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api -q

test-api-integration:
	LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/integration/test_api_*.py -q -m integration

lint:
	.venv/bin/ruff check src tests

typecheck:
	.venv/bin/mypy

check: lint typecheck test

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-api:
	cd frontend && npm run api:generate

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npm test -- --run

frontend-e2e:
	cd frontend && npm run test:e2e

frontend-lint:
	cd frontend && npm run lint

frontend-check:
	cd frontend && npm run check
