# Spec: GEPA Strategy Optimizer with Evaluator and Case Archivist

## Problem Statement

The current optiRCA Lite workflow can diagnose individual alarm sessions, but it cannot systematically improve its own diagnosis quality over time. Algorithm engineers and operators have no automated way to:

- Measure end-to-end and per-Agent diagnostic quality against ground truth.
- Attribute errors to the correct strategy lever (Prompt, Weights, or Cases).
- Propose, validate, and version new strategy configurations without manual trial and error.
- Preserve closed diagnoses as structured cases for future retrieval.

Without this, the system will plateau at its initial rule-and-LLM baseline and cannot meet the production target of Top-1 ≥ 85% / Top-3 recall ≥ 90%.

## Solution

Introduce three new components that form a closed self-improvement loop:

1. **Case Archivist**: Converts approved human-review closures into structured diagnosis dossiers and persists them to the case knowledge base.
2. **Evaluator**: Runs offline regression over archived dossiers or uploaded test batches, computes multi-objective metrics, and produces natural-language error attribution.
3. **Strategy Optimizer (GEPA)**: Uses the Evaluator report as fitness signal and error attribution as reflective feedback to evolve a Pareto frontier of strategy candidates (`<Prompts, Weights, Cases>`), then proposes the best validated candidate for offline regression and canary release.

Expose two new API seams:

- `POST /v1/evaluate` — run Evaluator on a batch of dossiers or an uploaded ground-truth batch.
- `POST /v1/gepa` — run Strategy Optimizer from an Evaluator report and return policy proposals.

## User Stories

1. As an algorithm engineer, I want to upload a batch of labeled alarm sessions, so that I can compute Top-1, Top-3, Critic recall, and Critic false-reject metrics automatically.
2. As an algorithm engineer, I want the Evaluator to tell me *why* the system failed on specific cases, so that I can decide whether to tune prompts, weights, or cases.
3. As an algorithm engineer, I want the Strategy Optimizer to propose multiple non-dominated policy candidates, so that I can choose between accuracy, recall, latency, and Critic quality trade-offs.
4. As an operator, I want approved diagnoses to be archived as structured dossiers, so that they become future few-shot examples and propagation templates.
5. As an operator, I want rejected or escalated diagnoses to be archived with their human notes, so that the system can learn from negative feedback without polluting the positive case base.
6. As an algorithm engineer, I want each GEPA candidate to be evaluated in an isolated environment, so that a bad candidate cannot corrupt production prompts or weights.
7. As an algorithm engineer, I want GEPA to finish within 4 hours, so that I can iterate on strategy multiple times per day.
8. As an operator, I want to inspect the Pareto frontier of policy candidates, so that I understand the trade-offs before approving a canary release.
9. As an algorithm engineer, I want case additions and removals in a GEPA candidate to be logical-view changes only, so that the global case base remains append-only and auditable.
10. As a reviewer, I want every policy proposal to carry a versioned chromosome and a source Evaluator report ID, so that I can reproduce or roll back the proposal later.
11. As an algorithm engineer, I want GEPA to avoid modifying graph schemas, model weights, or online behavior, so that its optimization space stays bounded and safe.
12. As an operator, I want the Archivist to extract a canonical propagation template from a closed case, so that similar future alarms can retrieve it for ranking or few-shot prompting.
13. As an algorithm engineer, I want Evaluator to support fault-injection simulations, so that I can measure rare-case recall without waiting for production failures.
14. As a reviewer, I want degraded or failed GEPA runs to be recorded with a `degradation_reason`, so that I can distinguish resource limits from logic bugs.
15. As an algorithm engineer, I want the Evaluator to emit structured error attribution in the same format that the reflection model consumes, so that the GEPA loop is fully automated.

## Implementation Decisions

- **Three new backend modules**
  - `Case Archivist`: consumes `human_review` closure events and writes `DiagnosisDossier` records into SQLite and vector-indexed templates into LanceDB.
  - `Evaluator`: accepts a batch of dossiers or a CSV-with-ground-truth upload, invokes the existing diagnosis workflow for each case, and computes `Top1_Acc`, `Top3_Recall`, `Critic_Recall`, `Critic_False_Reject`, and `AvgLatency`. It also emits `error_attribution` text per failure.
  - `Strategy Optimizer (GEPA)`: implements the genetic-Pareto loop using the Evaluator as fitness function and the error attribution as reflective input.

- **API seams**
  - `POST /v1/evaluate`
    - Request: `{"batch_id": "...", "dossier_ids": [...]}` or multipart upload of labeled CSV.
    - Response: `{"evaluation_id": "...", "status": "running", "report_url": "/v1/evaluate/{id}"}`.
    - Final report contains scalar metrics, per-case results, and aggregated `error_attribution`.
  - `POST /v1/gepa`
    - Request: `{"evaluation_id": "...", "population_size": 5, "max_generations": 10, "elite_ratio": 0.4}`.
    - Response: `{"optimization_id": "...", "status": "running", "report_url": "/v1/gepa/{id}"}`.
    - Final report contains the Pareto frontier, each candidate chromosome, and a recommended candidate for canary.

- **Case Archivist output schema (Diagnosis Dossier)**
  - `input_layer`: raw alarms, topology reference, session metadata.
  - `intermediate_layer`: hypotheses, validation results, scores, critic challenges.
  - `output_layer`: root cause, evidence chain, confidence, suggested action.
  - `feedback_layer`: human decision, notes, ground truth (if available).
  - `metadata`: timestamps, strategy version, agent versions.

- **GEPA chromosome encoding**
  - `prompts`: `{judge_system, judge_few_shot_ids, ranker_system, critic_system}` stored as version + hash.
  - `weights`: six weights summing to 1.0 (`upstream`, `time_lead`, `coverage`, `priority`, `case_sim`, `conflict_penalty`).
  - `cases`: `{added: [...], removed: [...], retrieval_k: 5}` operating as logical views on the append-only case base.

- **Mutation operators**
  - `MUTATE_WEIGHT`: Gaussian perturbation + renormalization.
  - `SWAP_FEW_SHOT`: replace 1–3 few-shot examples.
  - `ADD_CASE` / `REMOVE_CASE`: based on error attribution.
  - `REGENERATE_PROMPT`: LLM rewrites a system prompt using failure examples.

- **Reflection mapping**
  - Sorting-preference failures → `MUTATE_WEIGHT`.
  - Few-shot inadequacy → `SWAP_FEW_SHOT`.
  - Missing or misleading cases → `ADD_CASE` / `REMOVE_CASE`.
  - Prompt miscomprehension → `REGENERATE_PROMPT`.

- **Pareto frontier**
  - Fitness vector: `[Top1_Acc, Top3_Recall, Critic_Recall, -Critic_False_Reject, -AvgLatency]`.
  - A candidate joins the frontier if no existing candidate dominates it on all objectives.

- **GEPA isolation**
  - Each candidate is deployed to a sandboxed runtime that temporarily overrides prompts/weights/case views without touching production configuration.
  - The regression batch is run against the sandbox, not the live workflow endpoint.

- **GEPA boundaries (not optimized)**
  - Heterogeneous evidence graph schema and physical topology.
  - LLM / neural-network weights.
  - Real-time alarm stream.
  - New device-type onboarding rules.

- **Case base versioning**
  - Global case base is append-only; every case has `case_id` and `case_version`.
  - Chromosomes reference `case_id` (latest version) or `case_id@vN` (locked version).

- **Archivist integration point**
  - Hook into the existing `/v1/sessions/{id}/human-decision` `approved` branch.
  - Also archive `rejected`/`escalated` outcomes, but mark them with `feedback_layer.human_decision` so they can be excluded from positive case retrieval by default.

## Testing Decisions

- **Test only external behavior, not implementation details.**
  - For `/v1/evaluate`: assert that a known batch produces expected Top-1/Top-3 metrics and that error attribution is non-empty for failures.
  - For `/v1/gepa`: assert that the Pareto frontier is non-empty, that no candidate has invalid weights, and that the recommended candidate improves a known baseline on at least one objective without regressing all others.
- **Modules under test**
  - `Evaluator` scoring and attribution logic.
  - `GEPAAdapter` candidate deployment and fitness computation.
  - `Strategy Optimizer` selection/mutation/acceptance loop.
  - `Case Archivist` dossier assembly and case-base append logic.
- **Prior art**
  - Existing `/v1/sessions` tests can be reused as seed dossiers.
  - Existing `examples/demo_alarm.csv` can serve as a small regression batch with hand-labeled ground truth.

## Out of Scope

- Canary / AB release mechanism (only the proposal is produced; deployment is manual or a future feature).
- Automatic online learning from live traffic.
- Modification of LLM weights or graph schema.
- Real-time GEPA scheduling/triggers (runs are initiated via API).
- Frontend UI for the optimizer (this spec covers backend seams only).

## Further Notes

- Default hyperparameters are intentionally small (`population_size=5`, `max_generations=10`, `elite_ratio=0.4`) to keep the run under the 4-hour strategy-iteration target.
- Estimated cost: ~20,000 LLM calls per generation, ~200,000 calls per full run. Parallel evaluation should reduce wall-clock time significantly.
- This feature directly supports the ADR-0004 GEPA specification and the Phase 3 roadmap item “Strategy Optimizer (GEPA) 接入”.
