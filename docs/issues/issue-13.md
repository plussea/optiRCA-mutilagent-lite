## Parent

#2 — Spec: Full PRD Refactor — Heterogeneous Evidence Graph Multi-Agent Diagnosis

## What to build

Implement the **Strategy Optimizer (GEPA)** that closes the self-improvement loop by reading an Evaluator report and evolving a Pareto frontier of strategy chromosomes ``<Prompts, Weights, Cases>``.  It proposes a recommended candidate for canary release without modifying production configuration.

## Acceptance criteria

- [x] `POST /v1/gepa` accepts `{evaluation_id, population_size, max_generations, elite_ratio}` and returns `{optimization_id, status, report_url}`.
- [x] `GET /v1/gepa/{optimization_id}` returns the full optimization report.
- [x] Chromosomes follow ADR-0004 encoding: `{prompts, weights, cases}`.
- [x] Fitness vector derives from Evaluator metrics: `[Top1_Acc, Top3_Recall, Critic_Recall, -Critic_False_Reject, -AvgLatency]`.
- [x] Mutation operators `MUTATE_WEIGHT`, `SWAP_FEW_SHOT`, `ADD_CASE`, `REMOVE_CASE`, `REGENERATE_PROMPT` are implemented.
- [x] Reflection mapping maps Evaluator error-attribution levers to preferred mutation operators.
- [x] Pareto frontier is non-empty and the recommended candidate dominates the baseline.
- [x] Tests cover report retrieval, valid weights, baseline improvement, missing evaluation, and not-found cases.
- [x] Full test suite remains green.

## Blocked by

#12 — Evaluator offline regression metrics

## Status

Done — implemented and committed in `d936d01` parent. 41 tests pass.
