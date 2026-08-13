## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `plussea/optiRCA-mutilagent-lite`. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: one root `CONTEXT.md` plus `docs/adr/`. See `docs/agents/domain.md`.

### Project-specific notes

- The active refactor snapshots are tracked in `docs/issues/issue-9.md` through `docs/issues/issue-13.md`.
- Main API seams: `POST /api/v1/diagnose`, `GET /v1/dossier/{id}`, `POST /v1/evaluate`, `POST /v1/gepa`.
- Tests live in `backend/tests/` and should remain green; run `python -m pytest tests/ -q` from `backend/`.
- CodeGraph is enabled; prefer `codegraph_*` tools for structural queries.
