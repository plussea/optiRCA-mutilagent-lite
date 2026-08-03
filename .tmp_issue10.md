## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Extend `Critic Reviewer` from a single counterfactual check to the full three-challenge checklist defined in the PRD, and integrate it into the compiled diagnosis workflow so failures drive `FALLBACK_TO_JUDGE` / `FALLBACK_TO_RANKER` / degraded outcomes correctly.

## Acceptance criteria

- [x] Challenge #1 (existing): removing the top candidate leaves no unexplained alarms.
- [x] Challenge #2: for `Link` candidates, both endpoints must exhibit consistent bidirectional LOS-type alarms; otherwise reject with reason `inconsistent_bidirectional_los`.
- [x] Challenge #3: detect disjoint alarm clusters that suggest a missed multi-root cause; reject with reason `multi_cluster_suspected` when clusters exist and the top candidate does not explain all of them.
- [x] Critic emits one of the PRD fallback actions (`FALLBACK_TO_JUDGE`, `FALLBACK_TO_RANKER`) or `pass` based on which challenge failed.
- [x] New behavior is covered by unit tests for the Critic skill and workflow-level tests in `test_diagnose.py`.
- [x] Full test suite remains green.

## Blocked by

#9 — Refactor workflow graph for heterogeneous evidence-graph diagnosis

## Status

Done — implemented and committed in `508db3e`. All 30 tests pass.
