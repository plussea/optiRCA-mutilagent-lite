# Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis System

## Problem Statement

The current optiRCA Lite workflow is a single-chain LangGraph pipeline (perception → diagnosis → validation → planning → human review). It lacks the architecture described in `docs/product/project_prd_refactor.md`:

- There is no shared heterogeneous evidence graph acting as a blackboard between Agents.
- The system does not separate perception, judgment, ranking, and criticism into distinct, observable Agents.
- There is no Critic-based quality gate with a bounded fallback loop.
- Degraded and partial outputs are not standardized.
- The topology is treated as auxiliary context rather than a first-class graph entity.

As a result, the system cannot reliably explain its conclusions, cannot scale to complex multi-alarm storms, and cannot evolve its own strategy through the GEPA loop described in the PRD.

## Solution

Refactor the backend into the PRD architecture:

1. **Heterogeneous Evidence Graph** as the shared blackboard, with `:Device`, `:Port`, `:Link`, `:Alarm`, `:Service` nodes and `:BELONGS_TO`, `:TOPOLOGY`, `:PROPAGATES`, `:CARRIES` edges.
2. **Seven first-class Agents** plus an Orchestrator:
   - Perception: `Alarm Parser`, `Topology Builder`
   - Judgment: `Propagation Judge` (Generator + Validator)
   - Ranking: `Root Cause Ranker` (Feature Scorer + Aggregator)
   - Review: `Critic Reviewer`
   - Archival/Iteration: `Case Archivist`, `Evaluator`, `Strategy Optimizer (GEPA)`
3. **Orchestrator** that schedules Agents, enforces timeouts, handles up to 2 fallback rounds, and assembles the final report or degraded output.
4. **Pipeline scheduling** between Judge → Ranker → Critic, with a lightweight Critic pre-filter on individual Ranker candidates.
5. **Standardized degraded output** with `status: degraded`, `confidence: 0.0`, `requires_human_review: true`, and a `degradation_reason`.

Expose three new test seams under `/v1/refactor`:

- `POST /v1/refactor/parse` — run perception Agents and return the fact table + evidence graph.
- `POST /v1/refactor/judge-rank` — accept a fact table + evidence graph, run Judge and Ranker, return Top-K candidates with scores.
- `POST /v1/refactor/critic` — accept Top-K candidates + evidence graph, run Critic, return pass/fail with reasons and fallback instructions.

A future orchestration seam (`POST /v1/refactor/diagnose`) will compose these three into the full online pipeline.

## User Stories

1. As an NOC engineer, I want the system to output a root cause report with a traceable evidence chain, so that I can trust and act on the diagnosis.
2. As an NOC engineer, I want the system to flag uncertain results for human review instead of making up a high-confidence answer, so that I do not act on false root causes.
3. As an operations expert, I want to inspect the heterogeneous evidence graph for any diagnosis, so that I can verify the physical and logical relationships used in reasoning.
4. As an operations expert, I want to see why a candidate root cause was rejected by the Critic, so that I can validate the system's logic.
5. As an algorithm engineer, I want the diagnosis pipeline to be decomposed into independent Agents, so that I can improve one Agent without rewriting the whole system.
6. As an algorithm engineer, I want a shared blackboard graph between Agents, so that each Agent's intermediate output is observable and reusable.
7. As an algorithm engineer, I want the Judge Agent to generate multiple candidate propagation chains in parallel, so that the Ranker has a diverse set of hypotheses to score.
8. As an algorithm engineer, I want the Ranker to score candidates on six features (upstream, time lead, coverage, priority, case similarity, conflict), so that the final ranking reflects multiple diagnostic signals.
9. As an algorithm engineer, I want the Critic to perform counterfactual challenges, so that pseudo root causes are intercepted before reaching the user.
10. As an operations expert, I want the system to retry at most twice after a Critic rejection, so that diagnosis latency remains bounded.
11. As an NOC engineer, I want the system to fall back to a rule-based baseline when an Agent times out, so that I still receive a conservative answer instead of an error.
12. As an algorithm engineer, I want each Agent to be a first-class unit with a defined input/output contract, so that I can unit test and mock it independently.
13. As an operations expert, I want alarms to be attributed to ports or links rather than devices, so that root causes map to the smallest repairable physical unit.
14. As an algorithm engineer, I want topology edges to carry confidence values, so that inferred links are treated differently from CMDB-authoritative links.
15. As an NOC engineer, I want the system to handle the 8-node fiber-cut demo within 30 seconds end-to-end, so that it meets the operational response target.
16. As an algorithm engineer, I want the Orchestrator to handle single-Agent failures without crashing the whole diagnosis, so that the system remains robust.
17. As an operations expert, I want a diagnosis dossier to be produced for every run, so that every decision is auditable.
18. As an algorithm engineer, I want the refactor endpoints to live under `/v1/refactor`, so that the existing `/v1/sessions` workflow remains stable during development.
19. As a frontend developer, I want the new endpoints to return stable JSON shapes, so that the UI can progressively adopt the refactored architecture.
20. As an algorithm engineer, I want the Critic's lightweight review to run only the first counterfactual check, so that obviously bad candidates are discarded without paying for a full review.

## Implementation Decisions

- **Shared blackboard graph store**
  - Replace or augment the current JSON graph store with a graph model that supports typed nodes (`:Device`, `:Port`, `:Link`, `:Alarm`, `:Service`) and typed edges (`:BELONGS_TO`, `:TOPOLOGY`, `:PROPAGATES`, `:CARRIES`).
  - The graph is the single source of intermediate truth; Agents do not call each other directly.

- **Agent taxonomy**
  - Seven first-class Agents: `Alarm Parser`, `Topology Builder`, `Propagation Judge`, `Root Cause Ranker`, `Critic Reviewer`, `Case Archivist`, `Evaluator`, `Strategy Optimizer (GEPA)`.
  - `Propagation Judge` and `Root Cause Ranker` are first-class Agents but internally split into submodules (`Generator`/`Validator` and `Feature Scorer`/`Rank Aggregator`) for parallelization.
  - `Orchestrator` is not an Agent; it only schedules, timeouts, fallback-counts, and assembles output.

- **Perception layer**
  - `Alarm Parser` normalizes raw alarm CSV into a fact table with `alarm_id`, `type`, `severity`, `timestamp`, `device_id`, `port_id`, `raw_text`.
  - `Topology Builder` imports static topology, performs weak-topology inference for missing links, computes edge confidence, and builds the evidence graph.

- **Judgment layer**
  - `Propagation Judge.Generator` enumerates candidate `{device, port, link}` roots and performs 2–3 hop local expansion along the optical signal direction.
  - `Propagation Judge.Validator` applies direction, time, and coverage checks:
    - Direction: path edges align with port `in`/`out` attributes.
    - Time: `0 <= delta_t <= distance_km / (2e5 km/s) * safety_factor`.
    - Coverage: `cover >= 20%`.

- **Ranking layer**
  - `Feature Scorer` computes the six-dimensional vector `[upstream, time_lead, coverage, priority, case_sim, conflict]`.
  - `Rank Aggregator` fuses with `Score = w1*upstream + w2*time_lead + w3*coverage + w4*priority + w5*case_sim - w6*conflict` and outputs Top-K candidates with score breakdowns.

- **Review layer**
  - `Critic Reviewer` runs three counterfactual challenges:
    1. Remove the candidate root and check whether remaining alarms are explainable.
    2. Check bidirectional alarm consistency for link cuts.
    3. Check for multiple alarm clusters that indicate missed multi-root causes.
  - Lightweight review in the pipeline runs only challenge #1 to discard obviously invalid candidates early.
  - Full review runs all three challenges before final acceptance.

- **Orchestrator**
  - Runs Parser and Topology Builder in parallel.
  - Schedules Judge → Ranker → Critic in a pipeline.
  - Maintains a fallback counter; at most 2 rounds of re-rank or re-generate before marking `requires_human_review`.
  - On Agent timeout or failure, assembles a degraded response using the rule baseline.

- **Degraded output schema**
  - `status`: `"success"` or `"degraded"`.
  - `confidence`: `0.0` for degraded outputs.
  - `requires_human_review`: `true` for degraded outputs and for max-fallback cases.
  - `degradation_reason`: one of `judge_timeout`, `ranker_timeout`, `critic_timeout`, `agent_failure`, `max_fallback_exceeded`.
  - `root_cause`: rule baseline (earliest upstream alarm, or highest severity, or empty).

- **Evidence graph schema decision**
  - `:PROPAGATES` edges originate from `:Port` or `:Link`, not `:Device`.
  - `:BELONGS_TO` maps `:Alarm` → `:Port`.
  - `:TOPOLOGY` connects `:Device`/`:Port` → `:Port`/`:Link` with `distance_km`, `latency_ms`, `confidence`.
  - `:CARRIES` maps `:Service` → `:Device`/`:Link` with `bandwidth_ratio`.

- **API seams**
  - `POST /v1/refactor/parse`
    - Input: multipart CSV upload or JSON `{alarms: [...], topology: {...}}`.
    - Output: `{fact_table: {...}, evidence_graph: {...}, status: "perceived"}`.
  - `POST /v1/refactor/judge-rank`
    - Input: `{fact_table: {...}, evidence_graph: {...}, k: 3}`.
    - Output: `{candidates: [...], scores: [...], status: "ranked"}`.
  - `POST /v1/refactor/critic`
    - Input: `{candidates: [...], evidence_graph: {...}, full_review: true}`.
    - Output: `{verdict: "pass" | "reject", reasons: [...], fallback_action: "FALLBACK_TO_RANKER" | "FALLBACK_TO_JUDGE" | null}`.

- **Case Archivist, Evaluator, Strategy Optimizer**
  - Defined at the architectural level but implemented in a follow-up issue (see issue #1 for the GEPA/Evaluator/Archivist spec).
  - This refactor prepares the graph schema and Agent boundaries they will consume.

## Testing Decisions

- **Test external behavior only**, not internal Agent implementation.
- For `/v1/refactor/parse`: assert that the returned fact table contains the expected alarm fields and that the evidence graph contains the five node types and four edge types for the input.
- For `/v1/refactor/judge-rank`: assert that a known 8-node fiber-cut scenario returns the true root cause in Top-3 and that score vectors sum to the displayed total score.
- For `/v1/refactor/critic`: assert that removing the true root cause from a synthetic graph makes the remaining alarms unexplainable and produces a `reject`; assert that a correct candidate receives `pass`.
- For Orchestrator/fallback behavior: assert that a Critic reject triggers at most 2 re-invocations and that the final degraded response has `status: degraded`, `confidence: 0.0`, and `requires_human_review: true`.
- **Modules tested through the seams**: `Alarm Parser`, `Topology Builder`, `Propagation Judge`, `Root Cause Ranker`, `Critic Reviewer`, and `Orchestrator`.
- **Prior art**: existing `/v1/sessions` and `/v1/demo-session` endpoints provide the upload-and-poll pattern; `examples/demo_alarm.csv` provides a starting test fixture.

## Out of Scope

- Full online end-to-end endpoint (`POST /v1/refactor/diagnose`) that composes the three seams through Orchestrator. (It will be added once the seams are validated.)
- Case Archivist, Evaluator, and Strategy Optimizer (GEPA) implementation. (Covered by issue #1.)
- Frontend migration to the new endpoints.
- Cross-domain optical networks.
- Device-side probe/Agent development.
- General LLM pretraining or fine-tuning.

## Further Notes

- This refactor aligns with ADR-0001 (shared blackboard), ADR-0002 (Judge/Ranker internal submodules), ADR-0003 (Critic gate with fallback limit), ADR-0005 (`:PROPAGATES` from Port/Link), ADR-0006 (pipeline light-review boundary), and ADR-0007 (degraded output schema).
- The `/v1/refactor` namespace is intentionally separate from `/v1/sessions` so the existing demo workflow continues to work while the new architecture is built and tested.
- Phase 1 of the PRD roadmap targets Parser + Topology + Judge + Ranker + 8-node demo; this spec covers exactly that scope through the three seams.
