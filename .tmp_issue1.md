## Parent

#1 — ADR-0002: Split Judge and Ranker internal submodules

## What to build

Refactor `PropagationJudgeSkill` and `RootCauseRankerSkill` so each remains a first-class Agent while its internals are split into explicit, testable submodules aligned with the PRD and ADR-0002.

## Acceptance criteria

- [x] `optirc_lite/skills/judge/` package exists with `__init__.py`, `generator.py`, `validator.py`.
- [x] `ChainHypothesisGenerator` enumerates candidate root-cause chains.
- [x] `ChainValidator` applies pass-through direction/time/coverage checks with metadata.
- [x] `optirc_lite/skills/rank/` package exists with `__init__.py`, `scorer.py`.
- [x] `FeatureScorer` computes the six-dimensional feature vector.
- [x] `RankAggregator` performs weighted fusion, conflict penalty, and Top-K sorting.
- [x] `PropagationJudgeSkill` and `RootCauseRankerSkill` remain registered as first-class Agents.
- [x] External input/output schemas (`JudgeSkillOutput`, `RankSkillOutput`) are preserved.
- [x] End-to-end behavior unchanged: 8-node fiber-cut test still returns `link:B-C`.
- [x] `tests/test_judge_submodules.py` and `tests/test_rank_submodules.py` added and passing.
- [x] Full test suite remains green.

## Blocked by

#9 — Refactor workflow graph for heterogeneous evidence-graph diagnosis

## Status

Done — submodules split, tests passing, old monolithic files removed.
