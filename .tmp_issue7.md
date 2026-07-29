## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Move topology navigation logic currently duplicated in judge.py, critic.py, and topology.py into EvidenceGraph as first-class methods. Generate `:PROPAGATES` edges from `:Port`/`:Link` to downstream `:Alarm`s so the shared blackboard captures propagation direction, and centralise node-id prefix parsing (`dev:`, `port:`, `link:`, `alm:`) in one place.

## Acceptance criteria

- [x] EvidenceGraph exposes `parse_node_id`, `get_alarms_for_node`, `get_neighbors_by_type`, and `add_propagates_edge` methods.
- [x] `:PROPAGATES` edges are built during topology construction for alarms reachable from each port/link.
- [x] Judge, Ranker, and Critic skills use the new EvidenceGraph methods instead of manual prefix parsing.
- [x] Existing evidence graph tests still pass.

## Blocked by

None — can start immediately.

## Status

Done — implemented in `07fce10`.
