## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Implement the **Case Archivist** component that closes the diagnosis loop by producing the PRD-mandated five-layer `Diagnosis Dossier` for every completed or human-closed case, persists it to SQLite, and extracts a searchable propagation template for the vector case base.

## Acceptance criteria

- [x] Archivist assembles a five-layer dossier: `input_layer`, `intermediate_layer`, `output_layer`, `feedback_layer`, `metadata`.
- [x] Dossier is created on `/api/v1/diagnose` success/degraded outcomes and on `/v1/sessions/{id}/human-decision` closure (`approved`, `rejected`, `escalated`).
- [x] `GET /v1/dossier/{dossier_id}` returns the full dossier.
- [x] Propagation templates are written to vector storage for retrieval by future Ranker iterations.
- [x] Archivist distinguishes positive cases (`approved` / successful auto-diagnosis) from negative cases (`rejected` / `escalated`) so negative cases are excluded from positive retrieval by default.
- [x] Tests cover dossier assembly, endpoint retrieval, and human-decision archiving.
- [x] Full test suite remains green.

## Blocked by

#10 — Full Critic Reviewer three-challenge checklist

## Status

Done — implemented and committed in `a6b5ac3`. All 32 tests pass.
