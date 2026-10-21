# RepoReview — design brief (issue #4)

Built with the Anthropic frontend-design skill. Supersedes the earlier "lab report with tracks" draft
(tracks cut, D-157). Copy this file into the repo as `docs/design.md`.

## Subject, reader, job
- Subject: a maintenance due-diligence report for one open-source dependency.
- Readers, equally: (1) a tech lead deciding whether to adopt it — skeptical, technical, in a hurry;
  (2) a reviewer judging how we decide — wants to see and challenge the rules.
- Job: verdict and reason in under a minute; evidence one click away; the rules one scroll away.

## Concept: a risk sheet of five tiles
One verdict sentence on top, then five flat tiles you can compare at a glance.
The memorable element is the **3-segment risk meter** in every tile: risk is shown by how many
segments are filled, not only by colour. Everything else is quiet.

## Tokens
Colour — light theme only, no gradients, no shadows:
| name | hex | use |
|---|---|---|
| paper | #F6F7F9 | page background |
| surface | #FFFFFF | tile background, input |
| ink | #1D2733 | text, empty meter segment outline |
| muted | #5B6676 | secondary text, context line |
| rule | #D5DAE1 | tile border, input border, dividers |
| ok | #2E7D5B | filled segments when Healthy, "Low risk" |
| watch | #B7791F | filled segments when Watch, "Medium risk" |
| risk | #B3261E | filled segments when Risk, "High risk" |
| unknown | #8A94A3 | hatch for Not enough data |

All text/background pairs must meet WCAG AA (check `watch` on white for text; if it fails, use it
only for segments and keep the status word in ink).

Type: IBM Plex Sans (Google Fonts), weights 400 and 600; `font-variant-numeric: tabular-nums` for figures.
IBM Plex Mono only for the literal `owner/repo` identifier — nowhere else.
Scale: 32 / 20 / 16 / 14. Line length ≤ 75ch. Sentence case everywhere.

Radius: 6px on input and button; 4px on tiles. Border 1px `rule`. No shadows.

## Status mapping (frontend only, no backend change)
| status | meter | word |
|---|---|---|
| green | ■□□ (1 filled, `ok`) | Healthy |
| amber | ■■□ (2 filled, `watch`) | Watch |
| red | ■■■ (3 filled, `risk`) | Risk |
| amber + `evidence.reason == "insufficient_data"` | all 3 hatched in `unknown` | Not enough data |

Verdict level: low → "Low risk", medium → "Medium risk", high → "High risk".
The meter has `role="img"` and an `aria-label` equal to the status word.

## Layout (single column, left-aligned, max-width 760px)
```
[ owner/repo or GitHub link ............................ ] [ Check repo ]
Paste a GitHub repository to see whether anyone will keep maintaining it.   <- empty state only
Try: pallets/flask   request/request   sindresorhus/p-map                    <- empty state only

GitRepoReview/repo-review                                   <- Plex Mono 16
High risk                                                   <- 32/600, level colour
GitHub found no license file — you may have no right to use it; check manually.
Also red: One author. Not enough data for Issue response, Releases.   <- verdict.reason, 20/400
Checked 20 minutes ago, from cache.                         <- 14 muted

┌ [icon] Last commit ──────────┐ ┌ [icon] One author ──────────┐
│ ■□□ Healthy                   │ │ ■■■ Risk                     │
│ Last commit 0 days ago.       │ │ ValentynShtanko wrote 100%   │
│ ▸ Show evidence               │ │ of 19 human commits.         │
└───────────────────────────────┘ │ ▸ Show evidence              │
┌ [icon] Issue response ───────┐ └──────────────────────────────┘
│ ╱╱╱ Not enough data           │ ┌ [icon] Releases ────────────┐
│ Only 2 issues closed in 90 d. │ │ ╱╱╱ Not enough data          │
└───────────────────────────────┘ └──────────────────────────────┘
┌ [icon] License ─────────────────────────────────────────────────┐
│ ■■■ Risk    GitHub found no license file                         │  <- spans both columns:
└──────────────────────────────────────────────────────────────────┘     a legal question, not maintenance (D-60)

0 stars, 0 forks, Python, created 21 Oct 2026, not archived.     <- 14 muted, one line

How we judge this
Five signals answer one question: will someone still maintain this in two years?
The thresholds are heuristics we chose, not research. Read them, or disagree, in thresholds.py.  <- link to the repo file
```
Grid: two columns from 640px, one column below. Tile order fixed: Last commit, One author,
Issue response, Releases, License (full width). Tile body = `summary` from the API as-is.
"Show evidence" = native `<details>` with a `<dl>` of evidence keys and values, keys as-is.

## Icons (5, own inline SVG)
Monochrome, `currentColor` = muted, 1.5px stroke, 20px, `aria-hidden="true"`, no fill colours, no library.
- Last commit: a dot on a horizontal line (commit node)
- One author: a single head-and-shoulders outline
- Issue response: a speech bubble
- Releases: a tag
- License: a sheet with a folded corner
Icons sit before the tile name and never carry status. **First thing to cut** if time runs out.

## States and copy
- Loading: button reads "Checking…" and is disabled (D-103). No skeletons, no spinners.
- 400 (or client-side parse failure): "That doesn't look like owner/repo or a GitHub link."
- 404: "No public repository at {owner}/{repo}. Check the spelling."
- 422: "This repository has no commits yet, so there's nothing to judge."
- 429: "This server has used its GitHub requests for the hour. Try again after {local time}, or open a repo that's already cached." + the three example buttons. If `reset_at` is missing, drop "after {time}".
- 502: "GitHub didn't respond. Try again in a minute."
- Stale (`meta.stale`): note above the verdict, muted with a `watch` left border:
  "Showing data from {age} ago — couldn't refresh because the hourly GitHub limit is used up."
- Freshness line: cached → "Checked {age} ago, from cache."; fresh → "Checked just now. {remaining} of 60 GitHub requests left this hour." Show the limit part only when `meta.rate_limit` is not null.
- The status/error region is `aria-live="polite"`. High risk is never shown without its reason.

## Motion
None on load. Only user-triggered: the evidence `<details>` opens. Respect `prefers-reduced-motion`.

## Don't
Shadows, gradients, a big-number hero, emoji, decorative illustrations, all-caps or eyebrow labels,
middle-dot meta strings, "→" on buttons or links, numbered 01/02/03 markers, a dark-mode toggle,
monospace for anything except `owner/repo`, colour as the only carrier of status,
one word of a headline accented in another colour.

## Checked against generic defaults (frontend-design review)
- Cards: the generic kit is identical rounded cards with soft shadows and one radius everywhere.
  Here: flat tiles, border only, a different radius from controls, and License spans full width
  because it answers a different question. The tile form encodes "compare five things side by side".
- Background: cool grey paper, not warm cream; accents are status colours, not a brand accent.
- Type: Plex Sans is common in dev tools; its role here is a technical report voice. Mono is
  restricted to the identifier, not used for data labels.
- Bold element: one (the meter). Icons stay muted and small so they don't compete.

## Build order (time-box ~40 min)
1. Form, all states, verdict block, tiles with meter and evidence. Shippable on its own.
2. "How we judge this" block and context line.
3. Icons — only if 1–2 are done.
