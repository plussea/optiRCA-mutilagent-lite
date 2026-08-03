## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Refactor the LangGraph workflow so `/api/v1/diagnose` uses a unified compiled workflow (`perception → topology → judge → rank → critic → assemble`) instead of manual `run_phase` orchestration. Centralize fallback loops, degradation routing, event tracing, and dossier persistence inside the workflow, while preserving backward compatibility for `/v1/refactor/*` and `/v1/sessions` endpoints.

## Acceptance criteria

- [x] `build_workflow()` implements the new pipeline with conditional fallback edges (`FALLBACK_TO_JUDGE`, `FALLBACK_TO_RANKER`).
- [x] Dossier persistence lives in terminal workflow nodes (`assemble_success_node`, `assemble_degraded_node`).
- [x] `POST /api/v1/diagnose` builds initial state and invokes the compiled workflow.
- [x] `/v1/refactor/parse`, `/v1/refactor/judge-rank`, `/v1/refactor/critic` continue to work via manual `run_phase`.
- [x] Degraded reasons follow ADR-0007 enum.
- [x] Full test suite passes with no regressions.

## Blocked by

#8 — Spec-axis fixes for `/api/v1/diagnose`

## Status

Done — implemented and committed in `605c954`. All 26 tests pass.
