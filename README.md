# RepoReview

**Will we regret depending on this?** Paste a GitHub repo, get a low / medium / high
risk verdict with five maintenance signals and the evidence behind each one.

**Live:** https://repo-review-37eb871b.2.31.46.47.nip.swatantra.cloud/
— try `pallets/flask`, `request/request`, `sindresorhus/p-map` (pre-warmed, cost no quota).

Stack: Django (API, GitHub client, cache) + React/TypeScript (one page). One container in prod.

---

## What "will we regret this" means

**Regret = in two years nobody maintains it, and we can't easily replace or patch it.**
That is the most common way a dependency hurts, so the app judges *maintenance
sustainability*, not code quality, security advisories or popularity.

It asks five questions, each answered from at most four GitHub requests:

| Signal (UI name) | Question | Healthy | Watch | Risk |
|---|---|---|---|---|
| Last commit | Is anyone still working on it? | ≤ 6 months | 6–12 months | none in 12 months, or archived |
| One author | What if one person leaves? (top human author's share; bots and merges excluded) | < 50% | 50–80% | > 80% |
| Issue response | Do problems get handled? (median days to close, issues closed in last 90 d) | ≤ 30 d | 30–90 d | > 90 d, or nothing closed while issues are open |
| Releases | Do fixes reach users? | ≤ 6 months | 6–18 months | > 18 months |
| License | May we use it at all? | permissive (MIT, Apache-2.0, BSD, ISC…) | copyleft / unidentified → check with legal | no license file found |

The numbers are **heuristics, not research**. They all live in one file,
[`backend/analysis/thresholds.py`](backend/analysis/thresholds.py), so disagreeing with one is a one-line change.

**Verdict** — a traffic light, not a score, so every result can be explained and argued with:

- **High**: archived, no commits in 12 months, no license, or ≥ 2 risk signals.
  High means *"you'd be maintaining it yourself"*, not *"don't use it"*. No license is the exception: you may have no right to use it.
- **Medium**: one risk signal, or ≥ 2 watch signals.
- **Low**: anything else.

Two rules keep the verdict honest:

- **Unknown is not bad.** Too few commits, too few closed issues, issues disabled, or no
  GitHub releases show as *Not enough data* (hatched, not coloured) and never push the verdict up.
  The verdict text lists them, so you know what wasn't checked.
- **A copyleft license is a legal question, not a maintenance one.** It's flagged
  ("check the license") but doesn't raise the risk level.

**Popularity is shown but not counted.** Stars are a lagging signal of past
adoption; they say nothing about who will fix a bug in 2028. The UI says so next to them.

### Predictions vs. real data

I wrote expected verdicts for four real repos *before* recording their API responses,
then let the data argue back. Two rules changed; one did not.

| Repo | Expected | First result | Final | What it taught |
|---|---|---|---|---|
| `atom/atom` (archived) | high | high | **high** | — |
| `request/request` (deprecated, not archived) | high | medium | **high** | The tool missed the exact scenario it exists for. → No commits in 12 months is now high on its own. |
| `pallets/flask` (healthy) | low | medium (bus factor 92.6%) | **medium** (87.9%) | Merge commits credited the merger, not the author. → Excluded. Still > 80%: one maintainer really does most of the work, so medium stays and the text says why. The threshold was *not* moved to make flask look good. |
| `sindresorhus/p-map` (one maintainer) | medium | high | **high** | One backlog sweep (old issues closed in one go) set the median close time to ~1000 days. Kept as a known limitation, see below. |

The fixtures are committed ([`backend/analysis/fixtures/`](backend/analysis/fixtures/)) and the smoke tests
pin these results, with the original predictions in comments.

## The decision I'm least sure about

**"No commits in 12 months" alone means high risk.**

Before this rule, the deprecated `request/request` scored *medium* — a tool about
regret was calm about a library its own authors had abandoned. So silence became decisive.

The cost: a small, **finished** library — a 40-line utility that simply needs no
changes — also gets *high*. Commit history can't tell "done" from "dead".
I softened it with words, not rules: the verdict says *"you'd likely maintain it yourself"*,
which for a tiny library may be perfectly acceptable.

What would change my mind: a handful of known-finished libraries scoring high in
practice. The alternative I'd try is "silence **plus** one other warning sign
(open issues piling up, bus factor) → high", at the price of missing some abandoned repos.

## GitHub rate limit

Unauthenticated GitHub allows **60 requests per hour per server IP**. I treated that as part of the problem, not something to escape with a token.

- **4 requests per analysis** (repo, commits, issues, releases — one page each), measured on real GitHub. Checking `/rate_limit` first is free.
- **Only the backend talks to GitHub**, so the cache and the budget live in one place.
- **Cache** in SQLite: a report is fresh for 24 h (zero requests). Raw responses are cached, not the report, so "12 days ago" is recomputed on every view.
- **Stale-if-limited**: an expired entry is refreshed if the budget allows, otherwise served with a *stale* banner instead of an error.
- **Refuse early**: with fewer than 4 requests left, no new analysis starts (a half-fetched report would lie); the user gets the reset time. Partial results are never cached.
- **Not-found and empty repos** are cached for an hour, because GitHub charges for repeated misses.
- **Pre-warm**: on start-up the three demo repos are fetched (12 requests), so a reviewer's first clicks cost nothing.
- The UI always says where the data came from: fresh, cached, or stale, and how many requests are left.

Known trade-offs of the deploy: the host has no persistent volume, so every redeploy loses the cache
and spends 12 requests on warm-up; and the endpoint is public, so anyone can spend the hour's budget —
after that the app keeps serving cached reports and says when new ones will be possible.
<!-- TODO(human): D-240 — add "After deploy, `meta.rate_limit.remaining` was N." if useful -->

## Known limitations of the signals

- **Issue response** measures time to *close*, not time to first reply (that costs more requests). Issues closed as duplicates are excluded. A backlog sweep still dominates the median (p-map above); excluding `not_planned` wouldn't help there — 10 of its 11 closures were `completed` — so the rule was left as is.
- **Open issues** as reported by GitHub include open pull requests.
- **One author** looks at up to 100 recent commits. On busy repos that's weeks, not a year; the evidence shows the actual window. Who *merges* (a gatekeeper) is not measured.
- **Releases** sees only GitHub Releases. Projects that only push tags get *Not enough data*, not a penalty.
- **Many unknowns can add up to "low"**: a repo with little activity and no releases may pass. The verdict text lists every unknown; no extra rule was added.
- A renamed repo is cached under both names.

## What I deliberately cut

- **Security advisories, code quality, dependency trees, multi-repo comparison** — they answer "is it good today?", not "will anyone maintain it?".
- **Configurable thresholds** — one file to edit is enough for a tool this size.
- **GitHub's `/stats/contributors`** — it answers 202 "computing" and needs retries; authors come from commits instead.
- **Pagination and background refresh** — each would multiply requests or add a worker; one page per endpoint keeps an analysis at 4 requests.
- **Single-flight** (deduplicating concurrent requests for the same repo) — a demo has one user; the button is disabled while a request runs. Worst case: 8 requests instead of 4.
- **Threshold scales in the UI** (where a value sits relative to its limits) — designed, then cut for time.
- **Frontend tests and E2E** — backend logic is covered by tests; the frontend is one page checked by hand.
- **Auth, a database, history.**

## What I'd do next

1. Show each value on a scale with its thresholds, served from the backend (`GET /api/rules`), so a reader can see *how close* to the line a repo is.
2. A lock so concurrent requests for one repo spend 4 requests, not 8.
3. A persistent volume in prod (cache survives deploys).
4. Fall back to tags when a project has no GitHub Releases.
5. Calibrate on 20–30 repos with known outcomes (abandoned vs. finished), starting with the "silence = high" rule.
6. Planned refactors (backend module boundaries, frontend hooks) and an accessibility pass.

## How I used AI

AI wrote most of the code; I decided what it should do and checked that it did.

**Setup.** Two Claude roles:
- an **HQ chat** for planning, product decisions and review, with a decision journal (~240 entries);
- **Claude Code** locally, writing the code, one chat and one branch per ticket (#1–#6).

The agent could not commit: it staged files and proposed commit messages, I committed and merged (blocked in `.claude/settings.json`, not just asked).
Rules for the agent live in [`CLAUDE.md`](CLAUDE.md). Skills: test-first only for `signals.py`, a frontend-design skill for the UI, and code-review passes.

**What was mine:**
- the definition of regret and the five signals; popularity as context only;
- reading the results on real repos and deciding which rules change (request → silence is high) and which don't (flask's threshold stays);
- what to cut, the order of work, and the time-box calls;
- design direction: I rejected a flashy "neon" reference and big popularity numbers.


**Time.** I went over the "one evening" budget: about 5.5 hours in total (first commit 17:19, deploy merged 22:45).
Roughly: scaffolding 0.5 h, backend and tests 1 h, frontend 1.5 h, hosting 0.5 h; the rest went to manual testing,
reviewing the agent's work and the README. The frontend took longest because of design iterations — that's what I'd cut first next time.

## Running it

Requirements: Docker; for tests and lint also [uv](https://docs.astral.sh/uv/) (Python 3.12) and Node 24.

```sh
make dev     # backend :8000 + Vite :5173 with /api proxy → http://localhost:5173
make test    # backend tests (pytest, no network)
make lint    # Ruff, Biome, TypeScript
```

Production image (Django serves the API and the built React app):

```sh
docker build -t repo-review .
docker run -p 8000:8000 \
  -e DJANGO_SECRET_KEY=change-me \
  -e DJANGO_ALLOWED_HOSTS=localhost \
  -v rr-data:/data \
  repo-review
```

`GITHUB_TOKEN` is optional and meant only as an emergency switch (60 → 5000 requests per hour).

Test fixtures in `backend/analysis/fixtures/` are raw GitHub responses recorded once; author emails are replaced by stable hashes.