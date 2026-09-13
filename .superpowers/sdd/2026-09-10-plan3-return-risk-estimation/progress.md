# SDD ledger — plan: docs/superpowers/plans/2026-09-10-plan3-return-risk-estimation.md

Plan review: complete — design spec enhanced and implementation plan rewritten as 12 executable TDD tasks (60 steps); structure and existing policy baseline validated on 2026-09-10.

Preflight interface scan (2026-09-10):

| Tasks | Shared file/interface | Finding / ruling |
| --- | --- | --- |
| 1, 11 | `portfolio_service.estimation.__init__` | Task 1 establishes policy exports; Task 11 adds service/provider exports. No conflict; Task 11 preserves Task 1 exports. |
| 1, 5, 8, 11 | policy version closure | Task 1 supplies validation-policy persistence; Tasks 5/8/11 consume it. No conflict; D-1 requires all four version IDs. |
| 2, 3, 4, 5, 7–11 | estimation DTOs and canonical encoding | Task 2 is the shared foundation. No conflict; its immutable DTOs and encoding precede all consumers. |
| 3, 4, 5, 7, 11 | aligned matrix / estimation bundle | Tasks 3–4 produce pure estimates, Task 5 validates, Task 7 assembles inputs, Task 11 orchestrates. No conflict; execution order supplies dependencies. |
| 6, 7 | PIT benchmark history and ordered universe reads | Task 6 supplies both Task 7 inputs. No conflict; Task 7 must only call the new time-bound APIs. |
| 7, 10, 11 | `FactorRiskCrossCheckProvider` | Task 7 owns the Protocol; Task 10 implements it without a portfolio import; Task 11 injects it. No conflict; D-4/D-5 module boundary controls direction. |
| 8, 9, 11 | estimation ORM/run lifecycle | Tasks are sequential and share the persistent contract. No conflict; Task 8 schema first, Task 9 repository next, Task 11 service last. |
| 6, 10 | `tests/fitness/test_architecture.py` and Plan-2 guard correction | Task 6 does not modify it; Task 10 owns the dependency assertion. No conflict. |
| 8, 12 | migration/constraint documentation and quality gates | Task 8 creates schema; Task 12 documents and verifies it. No conflict. |

Ruling: Execute directly on `main` at the user's explicit request; no isolated worktree will be created. Cost if wrong: Plan-3 commits and any intermediate working-tree changes are visible on the shared branch.
Ruling: The non-executable SDD helper scripts will be invoked through `bash`. Cost if wrong: none to product behavior; this preserves the workflow without changing skill-owned file permissions.
Ruling: Task 4's literal frozen shrinkage/covariance reference conflicts with the design spec's binding `ddof=1` Ledoit-Wolf 2003 analytic calculation. Implement the canonical D-4A formula and regenerate the test fixture from an independent correct implementation, rather than tailoring the algorithm to the plan's inconsistent literal. Cost if wrong: the numerical fixture changes, but retaining the inconsistent value would violate the method/version contract and make later validation irreproducible.
Ruling: Task 5 omits the `bundle` value-object shape and the bridge from a per-share-class Factor candidate to a basis-vector risk value. Define a frozen pure `ValidationBundle` value object carrying the aggregate numerical matrices, diagnostics, input metadata, and an optional scalar `factor_volatility` for the subject share class; validation remains I/O-free and Task 11 constructs these inputs per included share class. Cost if wrong: later orchestration may need a thin adapter, but an explicit pure contract prevents service/SQL concerns leaking into the gate.
Ruling: Task 7 handles `T < 3N` as an explicit rejected basis result, not a load-wide exception. ABSOLUTE and EXCESS must preserve independent outcomes; a rejected basis carries status/reason and no consumable matrix, allowing Task 11/D-9 to persist the basis rejection while the other basis proceeds. Cost if wrong: downstream repositories must support rejected basis payloads, but raising would incorrectly couple independent bases and lose auditability.

Task 1: complete (commits 706e192..838a512, review clean)
Task 2: fix round 1/5 (2 addressed, 1 open — add public DTO ndarray annotation regression coverage; commits a50fd73..0e401df)
Task 2: fix round 2/5 (1 addressed, 0 open — public DTO ndarray annotation coverage; commits 0e401df..d149002)
Task 2: complete (commits 838a512..d149002, review clean)
Task 3: fix round 1/5 (2 addressed, 0 open — reject invalid degenerate return samples and cover clipping; commits 0a97d39..d50b7d2)
Task 3: complete (commits d149002..d50b7d2, review clean)
Task 4: fix round 1/5 (1 addressed, 0 open — covariance edge/invariant coverage; commits 91e8c0a..057e2ba)
Task 4: complete (commits d50b7d2..057e2ba, review clean)
Task 5: fix round 1/5 (3 addressed, 0 open — empty matrices and Factor lineage comparability; commits d252681..ae9f210)
Task 5: complete (commits 057e2ba..ae9f210, review clean)
Task 6: fix round 1/5 (1 addressed, 0 open — explicit ASC ordering and regression coverage; commits 3c73aec..c629e3a)
Task 6: complete (commits ae9f210..c629e3a, review clean)
Task 7: fix round 1/5 (4 addressed, 0 open — independent basis rejection, unavailable index handling, lineage completeness, switch-date evidence; commits fe46c4c..f9a6027)
Task 7: complete (commits c629e3a..f9a6027, review clean)
Task 8: fix round 1/5 (1 addressed, 1 open — executable constraint coverage; commits e4e5d2c..9749780)
Task 8: fix round 2/5 (1 addressed, 0 open — remaining RESTRICT FK coverage; commits 9749780..6cb2648)
Task 8: complete (commits f9a6027..6cb2648, review clean)
Task 9: fix round 1/5 (4 addressed, 0 open — D-9 derivation, lineage binding, two-session locking, canonical decoding; commits ff9e5c0..a0b0085)
Task 9: minor (deferred): EXCESS rows are not decoded by the approved ABSOLUTE provider; lineage remains verified and EXCESS is non-consumable.
Task 9: complete (commits 6cb2648..a0b0085, review clean)
Task 10: fix round 1/5 (1 addressed, 0 open — malformed JSONB lineage conservative parsing; commits bf56129..877fe00)
Task 10: complete (commits a0b0085..877fe00, review clean)
Task 11: complete (commits 877fe00..cc85326, review clean)
Task 12: documentation and scope review complete; PostgreSQL-backed quality gates are environment-blocked on 2026-09-14 because `127.0.0.1:5432` refuses connections and this host has no PostgreSQL runtime or container engine. Unit (292), fitness (37), Ruff, and mypy pass; integration (246), reproducibility (1), and explicit migration drift (43) were invoked but could not execute past the shared database fixture. See `task-12-report.md`; do not mark Plan-3 complete until those three commands pass against PostgreSQL.

Ruling: Plan-3 scope is Stage ⑤ only; Portfolio Construction, Optimization and Backtest remain downstream.
Ruling: PROVISIONAL estimation parameters are allowed only in explicit research/backtest runs and are rejected in LIVE mode.
Ruling: ABSOLUTE is the primary optimization input; EXCESS remains a separately versioned core estimate and must not be mixed with ABSOLUTE covariance.
Ruling: Covariance diagonal is the production risk single source of truth; Factor volatility is cross-check evidence only.
