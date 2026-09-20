# SDD ledger — plan: docs/superpowers/plans/2026-09-19-plan5-api-server-integration.md

## Preflight

Ruling: execute in the current main checkout — the user explicitly authorized direct main work and requested local command startup; creating a worktree would conflict with that instruction.

### Task self-consistency scan

| Task | Internal consistency | Ruling |
|---|---|---|
| 1 | Repository adapters and dependency provider are tested before route integration. | Proceed. |
| 2 | Read routes consume Task 1 adapters and tests cover the stated filters/PIT semantics. | Proceed. |
| 3 | Portfolio read adapters are isolated from Task 2 and preserve business statuses. | Proceed. |
| 4 | Persistent operation service replaces the current in-memory registry and uses existing jobs. | Proceed; PostgreSQL availability is an execution prerequisite for integration tests. |
| 5 | Commands consume Task 4 persistence and add audit-bearing review behavior. | Proceed. |
| 6 | Strict response models replace dictionaries after endpoint fields stabilize. | Proceed. |
| 7 | Auth and audit depend on the command/resource adapters without changing paths. | Proceed. |
| 8 | Local startup and frontend acceptance consume all prior tasks; no deployment work is included. | Proceed. |

### Shared-file/interface scan

| Tasks | Shared surface | Finding / ruling |
|---|---|---|
| 1 → 2 | `src/fip/api/repositories.py`, `ApiRepositories` | Task 1 owns construction and adapter interfaces; Task 2 only consumes them. Proceed. |
| 2 → 3 | `src/fip/api/routers/reads.py` | Both extend reads; keep query modules separate and route functions thin. Proceed. |
| 3 → 4 | operation/result IDs | Task 3 exposes business result reads; Task 4 owns technical operation persistence. Keep statuses separate. Proceed. |
| 4 → 5 | `commands.py`, `OperationRecord` | Task 4 supplies persistent submission; Task 5 supplies domain command payloads. Proceed. |
| 5 → 6 | command response data | Task 6 may tighten models only after Task 5 settles fields. Proceed sequentially. |
| 5 → 7 | review/audit | Task 5 validates review action; Task 7 persists actor/audit policy. Proceed. |
| 7 → 8 | auth and local startup | Task 8 only wires local acceptance; it must not weaken Task 7 authorization. Proceed. |

## Execution

- Task 1: complete — commits `2d57d8d`, `97a01a9`, `bb1f063`, `32327e6`; repository seam, app-owned engine lifecycle, canonical detail routes, and 24 API tests verified.
- Task 2: complete — commits `60fb094`, `3d39fe0`, `ee574f9`, `df8bcac`, `6bfc959`, `98cab9e`, `8e5ba62`; concrete PIT-backed fund/universe reads, contract-aligned NAV/evaluation/score projections, and focused API/integration tests verified. Reviewer approved after final PIT completeness fixes.
- Task 3: complete — commits `0c3edbf`, `db0b685`, `b94f43b`, `483393f`, `5a36b64`; portfolio/optimization/decision ORM records, Alembic migration and registration, principal visibility, pagination, ownership checks, contract-shaped payloads, and provenance metadata verified. Reviewer approved with 45 architecture/API tests.
- Task 4: complete — commits `9d3576e`, `2e1faf8`, `8fbbc61`, `92732bb`, `fe7fc12`, `2ba5b60`, `aae6d8c`; persistent job-backed operation service, dedicated resource/result references, idempotency, terminal failure mapping, unknown progress semantics, session cleanup, and PostgreSQL/API tests verified. Reviewer approved with 30 focused tests.
- Task 5: complete — commits `8b20109`, `70662be`, `9c558d3`, `3a85979`, `d0ff31d`, `0bbe00c`, `98ca43a`, `8032490`, `b2fbc9e`, `00c30ef`; command validation, atomic optimization persistence, backtest resource lifecycle/result gating, decision review snapshot updates, and audit persistence verified. Reviewer approved with 24 focused tests.
- Task 6: complete — commits `5762986`, `1ed21f1`, `2fc42c6`, `e6c5e80`, `554810b`, `40dd77b`; typed command/operation envelopes, production endpoint response bindings, strict top-level read payload validation, nullable metric models, and validation-error envelope verified by the API suite.
- Task 7: complete — commits `1bfb514`, `57d50fa`, `e6c5e80`; injectable principal dependency, production fail-closed identity boundary, portfolio-linked decision/optimization visibility, and governance audit writer verified by auth/API tests.
- Task 8: complete — commit `6372b46`; local `api-dev`, API integration target, frontend API smoke fixture, `make api-check`, `make frontend-check`, and Playwright acceptance verified. No deployment/container files added.

## Freeze

Plan-5 frozen on 2026-09-20 after API tests, PostgreSQL API integration target, local FastAPI+Vite Playwright smoke, frontend format/lint/build checks, and the full frontend suite (with the known 5-second BacktestPage timing threshold independently verified at 15 seconds). No deployment or containerization work is included.
