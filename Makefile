PY := .venv/bin/python
PYTEST := .venv/bin/pytest
export PATH := .venv/bin:$(PATH)

.PHONY: test test-unit test-integration test-fitness test-contract lint typecheck check migrate frontend-install frontend-dev frontend-build frontend-test frontend-lint

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

lint:
	.venv/bin/ruff check src tests

typecheck:
	.venv/bin/mypy

check: lint typecheck test

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npm test -- --run

frontend-lint:
	cd frontend && npm run lint
