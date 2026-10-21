# RepoReview

Take-home: help a team decide whether to adopt an open-source dependency —
not "does it work today" but "will we regret this in two years".
Assessed on (1) product judgment, (2) implementation quality. Completeness is NOT assessed.
Time budget: one evening (~5.5 h). One thing done well beats four half-built.

## Product decision (do not expand without asking)
"Regret" = in two years nobody maintains it and we can't easily replace or patch it.
The app scores **maintenance sustainability**, not code quality. Five signals, each with evidence:

| Signal | GitHub endpoint | Green | Amber | Red |
|---|---|---|---|---|
| Liveness | `GET /repos/{o}/{r}` + commits | latest commit ≤ 6 mo | 6–12 mo | none in 12 mo, or archived |
| Bus factor | `GET /repos/{o}/{r}/commits?since=<12mo>&per_page=100` | top human author < 50% (bots and merge commits excluded) | 50–80%; < 10 human commits (`insufficient_data`) | > 80% |
| Responsiveness | `GET /repos/{o}/{r}/issues?state=closed&since=<90d>&per_page=100` | median close ≤ 30 d | 30–90 d; < 3 closed or issues disabled (`insufficient_data`) | > 90 d; 0 closed with open issues (issues enabled) |
| Releases | `GET /repos/{o}/{r}/releases?per_page=10` | newest published non-draft ≤ 6 mo | 6–18 mo; none (`insufficient_data`) | > 18 mo |
| License | `license.spdx_id` from repo | permissive list (MIT, Apache-2.0, BSD-2/3, ISC, 0BSD, Unlicense, Zlib) | copyleft, NOASSERTION, unlisted → "check with legal" | none ("GitHub found no license file") |

Pull requests and issues closed as duplicates are excluded from responsiveness.

Verdict = traffic light (low / medium / high risk), not a number (D-81):
- **high** = archived, liveness red, license red, or ≥ 2 red signals
- **medium** = exactly 1 red, or ≥ 2 amber, not counting an amber license or `insufficient_data` ambers
- **low** = anything else

The verdict reason names each cause once. "High" means you'd maintain it yourself,
except no license: you may have no right to use it.
Stars/forks are context only. Do NOT use `/stats/contributors` (returns 202 while computing).
All thresholds live in one file: `backend/analysis/thresholds.py`.

## Rate limit (core part of the task)
No GitHub token by default (60 req/h per server IP). `GITHUB_TOKEN` env is an emergency escape only.
Note: ETag/304 does NOT save quota without a token — don't rely on it.
Protection, in order: cache 24h on disk (SQLite) → stale-while-revalidate → single-flight per repo
→ refuse to start a new analysis (not the app) if `X-RateLimit-Remaining` < 4 (429 with `reset_at`, or stale data) → pre-warm demo repos
→ UI shows data source, freshness, remaining quota. ~4 requests per uncached analysis.

## Architecture
Browser → Django only; only the backend calls GitHub.
- `backend/analysis/github_client.py` — httpx, timeouts, `X-RateLimit-*`, typed errors (`RepoNotFound`, `RateLimited`, `UpstreamError`)
- `backend/analysis/signals.py` — pure functions `raw JSON → SignalResult(status, summary, evidence)`; no HTTP here
- `backend/analysis/views.py` — `GET /api/repos/{owner}/{repo}/report` → 200 / 404 / 429 / 502
- `GET /api/health` → `{"status":"ok"}`; never calls GitHub.
- Response: `{ repo, verdict, signals: [{id, status, summary, evidence}], context, meta: {cached, fetched_at, rate_limit: {remaining, reset_at}} }`
- Cache: Django cache framework on SQLite/file. No Postgres, no Redis, no auth.
- Frontend: Vite + React + TypeScript + Tailwind, one page: form → loading → report / error.

## Stack and tooling
- Python: uv, Django, httpx, pytest, respx, Ruff
- Frontend: Vite, React, TS, Tailwind, Biome (no ESLint/Prettier)
- `compose.yaml` for dev (backend runserver + Vite with `/api` proxy). No DB service.
- Prod: multi-stage Dockerfile (Node build → Python runtime, WhiteNoise, gunicorn), deployed to selfhost.dev
- `make dev`, `make test`, `make lint`
- `make dev` runs in compose; `make lint`/`make test` run on the host and need uv and Node 24.

## Workflow
- Work is tracked as GitHub Issues #1–#6 on the project board. One issue = one branch.
- Branches are `<type>/<N>-<slug>`; the human creates them, you only suggest the name.
- **Never commit, push or open PRs.** Stage changes with `git add` only. The human commits.
- At the end of each logical step, run `/ponytail-review`, stage, then print:
  - suggested commit message(s): Conventional Commits, imperative, ≤ 50 chars, issue ref,
    e.g. `feat(signals): add bus factor signal (#2)`; split into several commits if the staged change mixes concerns
    (say which files go in which commit)
  - a "Decisions" block: any choice made that is not already in this file, with the reason
- Decisions are recorded outside the repo (project HQ). If a decision changes something in this file, propose the edit — don't apply it silently.
- Use the frontend-design skill for UI work (#4).
- TDD only for `signals.py` (issue #2). No TDD ceremony for UI/infra.
- Out of scope (list in README "what we cut"): multi-repo comparison, dependency trees, CVE/OSV,
  activity charts, auth/history, configurable thresholds, E2E tests.
- If something forces a product decision not covered here, stop and ask instead of guessing.