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
Colour — light theme only, no gradients (except the verdict panel tint), no shadows (except the search focus ring):
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
| accent | #1F4FBF | the one brand colour: brand name, links, primary button, focus border. White on it 7.17:1; on `paper` 6.69:1. Hover for the button #1C49AF |

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
Hero, empty state (full-bleed white band, 1px rule below, 85vh, centred):
RepoReview                                                            <- 16/600, accent
Will we regret depending on this?                                     <- 48/600 ink, max 30ch
Checks who will maintain an open-source dependency two years from now.   <- 18 muted
[ owner/repo or GitHub link ..................... [ Review ] ]        <- one 64px container, max 680, grey border
▬▬▬▬▬▬▬▬▬▬▬▬ ▬▬▬▬▬▬▬▬▬▬▬▬ ▬▬▬▬▬▬▬▬▬▬▬▬                               <- 3px ok/watch/risk, decorative
Try: pallets/flask   request/request   sindresorhus/p-map

With a report: a 64px white bar with a 1px rule, RepoReview left, the same field (44px) right.

GitRepoReview/repo-review              View on GitHub  Homepage   <- report header, no border/background:
A small tool that checks maintenance.                                  Plex Mono 20 ink; links 14 underlined
Stars  Forks  Watching  Open issues & PRs  Language  Created  Last push  <- label 13 muted over value 16/600
2.1K   180    40        12                 Python    Mar 2024 3 days ago    wraps; 2 columns at 375px
Popularity isn't part of the verdict.                                   <- 13 muted
                                                                        16px gap
High risk ■■■                                               <- verdict panel: 32/600, level colour
GitHub found no license file — you may have no right to use it; check manually.
Also red: One author. Not enough data for Issue response, Releases.   <- verdict.reason, 20/400
Checked 20 minutes ago, from cache.                         <- 14 muted

┌ [icon] Last commit ──────────┐ ┌ [icon] One author ──────────┐
│ ■□□ Healthy                   │ │ ■■■ Risk                     │
│ Last commit 0 days ago.       │ │ ValentynShtanko wrote 100%   │
│                               │ │ of 19 human commits.         │
└───────────────────────────────┘ └──────────────────────────────┘
┌ [icon] Issue response ───────┐ └──────────────────────────────┘
│ ╱╱╱ Not enough data           │ ┌ [icon] Releases ────────────┐
│ Only 2 issues closed in 90 d. │ │ ╱╱╱ Not enough data          │
└───────────────────────────────┘ └──────────────────────────────┘
┌ [icon] License ─────────────────────────────────────────────────┐
│ ■■■ Risk    GitHub found no license file                         │  <- spans both columns:
└──────────────────────────────────────────────────────────────────┘     a legal question, not maintenance (D-60)

How we judge this
Five signals answer one question: will someone still maintain this in two years?
The thresholds are heuristics we chose, not research. Read them, or disagree, in thresholds.py.  <- link to the repo file
```
Grid: two columns from 640px, one column below. Tile order fixed: Last commit, One author,
Issue response, Releases, License (full width). Tile body = `summary` from the API as-is.
Evidence: one toggle above the tiles, right-aligned: a 36px button, 1px `rule` border, `surface` fill, radius 6, 14/600 ink label and a muted chevron (own SVG, points down closed, up open; hover border `unknown`) ("Show evidence" / "Hide evidence", `aria-expanded`,
`aria-controls` the five blocks), opens or closes every tile's block at once. State lives in the report
component and resets on a new report. A block is a `paper` panel (radius 4, 12px 14px) with a two-column
`<dl>`: label 13 muted, value 14 ink tabular-nums right-aligned (long values wrap anywhere, left-aligned),
1px `rule` between rows. Labels and formats come from one map in `format.ts`; `reason` is never shown,
null is "—", unknown keys become sentence case.

## Revisions after screenshot review
- Tiles are equal height per row. From 640px each tile is a CSS subgrid spanning five rows
  (title · key value · meter and status · summary · evidence), so statuses and summaries of
  neighbours line up; an empty key value keeps its row. License is outside the subgrid.
  Below 640px: one column, no subgrid.
- Repo context moved into a borderless report header above the verdict panel: identifier, links,
  description, seven facts, and a one-line note that popularity is not part of the verdict.
  The verdict panel keeps only level, reason and freshness. The separate "About this repo" block
  and the one-line context string are gone.
- Hero (light, supersedes the dark band and D-206): a full-bleed white band with a 1px `rule`
  below holds brand (accent), h1 (48px, 34px at 375px, max 30ch), subline 18px muted, search,
  a decorative `aria-hidden` strip (ok / watch / risk, 3px segments, gap 4px, 8px under the form)
  and examples. Empty state is 85vh (75vh at 375px), content centred.
  Search is one 64px container (max 680px, radius 10px, 1px `unknown` border (3.07:1 on white, the minimum for a control edge)) with the button inside on
  the right (48px, accent, white text, 8px inset; hover darker; disabled opacity .6). Focus: border
  turns accent plus a 3px ring rgba(31,79,191,.15), the only shadow, because it answers focus.
  Placeholder is `unknown` #8A94A3 (3.07:1 on white, below AA; the field has a hidden label).
- Once a report has been shown the band shrinks to a 64px bar: brand (link to "/") left, field
  (44px, button 36px inset 4px) right, two rows at 375px; h1 stays for screen readers only,
  subline, strip and examples are hidden. No transition. Errors and waiting before the first
  report keep the full hero without the min-height. The idle "Paste a GitHub repository…" line
  is dropped, the hero says it.
- Links in the report ("View on GitHub", "Homepage", thresholds.py) are accent and underlined.
- Button copy is "Review", busy state "Reviewing…" (was "Check repo" / "Checking…").
- Evidence is one toggle, not five `<details>`: rows grow together in the subgrid, so neighbours stay
  aligned. Raw keys (`days_since_last_commit`) became human labels and formats (see Layout).
- The report bar is sticky (`top: 0`, above content, white, 1px `rule` always, no shadow, no
  appear animation); `html { scroll-padding-top }` equals its height so focus and anchors are not
  hidden. At 375px it is one row of ~56px: the brand text is visually hidden (still a link for
  screen readers) and the field takes the full width. The empty-state hero is not sticky.

## Icons (5, own inline SVG)
Monochrome, `currentColor` = muted, 1.5px stroke, 20px, `aria-hidden="true"`, no fill colours, no library.
- Last commit: a dot on a horizontal line (commit node)
- One author: a single head-and-shoulders outline
- Issue response: a speech bubble
- Releases: a tag
- License: a sheet with a folded corner
Icons sit before the tile name and never carry status. **First thing to cut** if time runs out.

## States and copy
- Loading: button reads "Reviewing…" and is disabled (D-103); the panel says "Reviewing {owner}/{repo}…" (announced by the aria-live region); the tab title is "Reviewing {owner}/{repo}… | RepoReview". No skeletons, no spinners.
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
None on load. Only user-triggered: the evidence toggle opens. Respect `prefers-reduced-motion`.

## Don't
Shadows (exception: the 3px focus ring on the search), gradients (exception: the verdict panel tone), a big-number hero, emoji, decorative illustrations, all-caps or eyebrow labels,
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
2. "How we judge this" block and report header.
3. Icons — only if 1–2 are done.
