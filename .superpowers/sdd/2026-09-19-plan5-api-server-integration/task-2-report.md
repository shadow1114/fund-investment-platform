# Task 2 report — fund and universe reads

## Delivered

- Added `FundQueries`, a thin request-scoped adapter over `FundRepository`.
  It applies the frozen fund filters, deterministic `fund_id` tie-breaking,
  pagination, and requested `as_of_date` / `is_point_in_time` metadata.
- Added fund detail, NAV, evaluation, and score query seams.  Related reads
  delegate to repository-provided `read_detail`, `read_nav_series`,
  `read_evaluation`, and `read_scores` methods when present; the route never
  recalculates NAV, factors, scores, or eligibility.
- Added `UniverseQueries` for frozen universe filters plus the recorded
  selected and rejected members and their condition results.  It delegates
  member materialization to the repository `read_members` seam.
- Routed all frozen fund and universe reads through these adapters.  Date and
  enum parameters are parsed/validated at the FastAPI boundary without adding
  paths or changing envelopes.

## Test-first record

`tests/api/test_fund_routes.py` and `tests/api/test_universe_routes.py` were
added before implementation.  Their first run failed in the expected ways:
the old routes ignored the frozen filters and dates, returned unpaginated fund
rows, left PIT metadata false, returned placeholder NAV/evaluation/score data,
and omitted universe members/exclusions.  After the query adapters and route
wiring were added, the focused suites passed.

## Verification

- `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api/test_fund_routes.py tests/api/test_universe_routes.py -q` — 6 passed.
- `PYTHONPATH=src .venv/bin/ruff check src/fip/api/routers/reads.py src/fip/api/fund_queries.py src/fip/api/universe_queries.py tests/api/test_fund_routes.py tests/api/test_universe_routes.py` — passed.
- `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/mypy --package fip.api` — passed.
- `LC_ALL=en_US.UTF-8 PYTHONPATH=src .venv/bin/pytest tests/api -q` — 30 passed; one existing Starlette deprecation warning.

## Scope note

Review changes completed in the follow-up commit:

- `FundRepository` now materializes fund/share-class summaries from the
  persisted models, resolves interval/versioned facts at the requested PIT
  visibility boundary, delegates adjusted NAV to `SqlNavPitRepository`, and
  reads persisted factor/evaluation/score rows.
- `UniverseRepository` now reads persisted snapshots, members, ranking/tier/
  score rows, and recorded selection-condition results.
- Missing NAV/evaluation/score/member materialization is a contract-shaped
  `404`; it is no longer replaced by placeholder success payloads.
- `style=form, explode=false` multi-value query strings are parsed as comma
  lists, and invalid sorts or contradictory ranges return `422`.
- Added a PostgreSQL-backed integration test that seeds the existing domain
  models and proves the concrete fund and universe repositories see those
  persisted rows.

The available data model does not associate a management company with `Fund`,
nor does it persist an API-level universe strategy or all detail presentation
fields.  The concrete adapter exposes `UNKNOWN` for those explicitly absent
facts rather than fabricating a business value.  Strict response-model work
remains Task 6 as planned.
