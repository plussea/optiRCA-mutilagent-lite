## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Expose a single external `POST /api/v1/diagnose` endpoint that orchestrates Alarm Parser → Topology Builder → Propagation Judge → Root Cause Ranker → Critic Reviewer in one call, returns either a success dossier or a degraded response conforming to ADR-0007, and persists the case for feedback.

## Acceptance criteria

- [x] Endpoint accepts alarm CSV + topology JSON and returns `status: success` or `status: degraded`.
- [x] Degraded output uses the enum reasons from ADR-0007.
- [x] Dossier contains input, intermediate evidence graph, top candidate, critic verdict, and metadata.
- [x] Add end-to-end tests covering the 8-node fiber-cut demo and a fallback-exceeded scenario.

## Status

Done — implemented in `eb48c8f` and polished in current commit. Spec-axis findings from `/code-review 07fce10...eb48c8f` fixed: ADR-0007 reasons aligned, dossiers persisted, 8-node fiber-cut test added.
