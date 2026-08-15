# Crow Platform 2.3 – Reasoning Engine RC1, Sprint 3

Sprint 3 introduces a persistent Findings Engine above the data-driven Rule Engine.
Findings retain deterministic identity across evaluations and therefore support review,
deduplication, automatic resolution, reopening, assignments, notes and full audit history.

## API

- `GET /api/projects/{project_id}/reasoning/findings`
- `POST /api/projects/{project_id}/reasoning/findings/synchronize`
- `PATCH /api/projects/{project_id}/reasoning/findings/{finding_id}`
- `GET /api/projects/{project_id}/reasoning/findings/history`
- `GET /api/projects/{project_id}/reasoning/findings.csv`

The existing raw evaluation endpoint remains available and does not mutate finding state.
