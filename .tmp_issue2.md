## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Extend the **Topology Builder** with weak-topology inference, edge confidence scoring, and isolated-node marking so that it matches the PRD 4.3 requirements.

## Acceptance criteria

- [x] Topology Builder infers missing internal links from unconnected out/in port pairs on the same device.
- [x] Inferred links and edges are marked with `confidence=0.6` and `inferred=true`.
- [x] Authoritative topology edges keep `confidence=1.0` and `inferred=false`.
- [x] Device/Port/Link nodes with no TOPOLOGY edges are flagged `isolated=true`.
- [x] Tests cover explicit edge confidence, inferred links, isolated nodes, and end-to-end diagnose output.
- [x] Full test suite remains green.

## Blocked by

#9 — Refactor workflow graph for heterogeneous evidence-graph diagnosis

## Status

Done — implemented and committed. 45 tests pass.
