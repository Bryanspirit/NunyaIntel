# NunyaIntel: Shared Task Board

Junie and Claude Code both work from this board. Status: `[ ]` todo, `[~]` in progress, `[x]` done.
Format: `- [status] ID: description (owner: junie|claude|user|-)`

## Schedule: everything finished by **Wed 6 Jan 2027** (official deadline 12 Jan, so 6 days of buffer)

| Milestone | Due | Scope |
|---|---|---|
| M1 Core analytics ✓ | Sun 29 Nov | T1 ✓, T2 ✓, O1 ✓, O2 ✓, U1 ✓ |
| M2 Feature depth ✓ | Sun 13 Dec | T3 ✓, U2 ✓, U3 ✓, O3 ✓, D1 ✓ |
| M3 Feature-complete (feature freeze) ✓ | Sun 20 Dec | D2 React web app working end-to-end (W1–W5) |
| M4 Polish + demo | Sun 3 Jan | R1, P1–P9 done; K1–K4 drafted (21 Dec–3 Jan is holiday buffer) |
| **Finish** | **Wed 6 Jan** | D3: K1–K7 complete, checked and **submitted** |

If a milestone slips, cut scope (first candidates now: P5 polish extras, K5 blog, K6 feedback). Don't move the 6 Jan date.

## Setup
- [x] S1: Project skeleton, pyproject, tests, agent guidelines (owner: claude)
- [ ] S2: Add Competition Plan v4 to `docs/` and update the cover name to NunyaIntel (owner: -)
- [x] S3: Data source = GRID starter repo; streaming reader `data/grid.py` + pre-commit data guard (owner: claude)
- [x] S4: Feed replay (handles `!` reversals and rolled-back games) → local SQLite extract `data/cache/nunyaintel.sqlite` via `nunyaintel build-cache` (owner: claude)

## Tactical Scouting
- [x] T1: `scouting/team_rounds.py` (one row per round from a team's view, incl. own/opponent buy) + `scouting/overview.py`: maps (games, wins, rounds), attack/defense round win %, win types (owner: claude)
- [x] T2: `scouting/economy_report.py`: pistol win % per side, conversion/break after pistols, eco upsets, anti-eco losses, buy-vs-buy win grid; `nunyaintel scout --team <t> [--map] [--since]` (owner: claude)
- [x] T3: `nunyaintel/maps.py` (valorant-api.com callouts: region_of, site_of, to_minimap) + `scouting/sites.py`: attack plant sites (share, win %, plant time), defense holds per site, default setups (first area seen in 20 s), opening-duel regions; in `scout --map` (owner: claude)

## Utility Placement
- [x] U1: `load_utility()` + `nunyaintel utility --team <t> --map <m> [--side]`: casts with supplement position/aim, timing vs. buy-phase end (extract v2 adds `rounds.buy_ended_at`), per-ability summary (owner: claude)
- [x] U2: `find_lineups()` (DBSCAN on cast spot + aim, per team/map/side/agent/ability, recurring in >= 2 matches) + `nunyaintel utility ... --lineups [--radius --angle --min-matches]` (owner: claude)
- [x] U3: `utility/effectiveness.py` `score_lineups()`: win-rate lift vs. team baseline (shrunk with k=10 prior rounds), ability damage per cast, team K-D in 10 s after in-round casts; `nunyaintel utility ... --lineups --score` (owner: claude)

## Operator Profiler
- [x] O1: `profile_players()` + `nunyaintel operator --team <id|name> [--map m]`: rounds with Op, buy rate, Op kills, first bloods, Op K/D, win % with Op (owner: claude)
- [x] O2: `nunyaintel operator --economy` (Op rate per team economy state) and `--duels` (opening duels with vs. without Op); shared buy classifier in `nunyaintel/economy.py` (owner: claude)
- [x] O3: `operator_profiler/angles.py`: Operator shots (spot + direction, >100 m dropped) grouped by named region (default) or DBSCAN exact spots (`--precise`); `nunyaintel operator --map <m> --angles [--team --side --player]` (owner: claude)

## Delivery
- [x] D1: CLI commands wired to each feature: `scout`, `utility` (`--lineups --score`), `operator` (`--economy --duels --angles`), `build-cache` (owner: claude)
- [x] D2: Presentation layer = **React web app** (decided 18 Nov): FastAPI JSON API + Vite/React/TypeScript frontend, served together by `nunyaintel serve`
  - [x] W1: FastAPI backend `nunyaintel/api/`: JSON endpoints for meta, maps, scout, operator, angles, utility, lineups; `nunyaintel serve` (owner: claude)
  - [x] W2: React scaffold in `web/` (Vite 8 + React 19 + TS 7, pinned), typed API client (`api.ts`), `useApi` hook, URL-backed selection, team/map/side/since pickers, tabs, first Scouting table end to end (owner: claude)
  - [x] W3: `components/Minimap.tsx` (`<Minimap>`, `<MapDot>`, `<MapArrow>`, callout labels, legend) + `PlantMap` on Scouting when a map is selected; u/v verified against the Lotus image (owner: claude)
  - [x] W4: Pages: Scouting (stats, maps, win types, pistols, buy grid, plant map, sites, setups, opening duels), Operator (profiles, economy, duels, angle arrows), Utility (ability summary, lineup arrows + scores, hover-to-highlight); checked in the browser (owner: claude)
  - [x] W5: `nunyaintel serve [--build] [--open]`: builds web/ (npm) and serves page + API from one process on :4811 (owner: claude)
- [ ] D3: Submission package, complete and submitted by **Wed 6 Jan 2027** (see K1–K7 below)

## M4 + D3 plan (planned 18 Nov)

Assumptions until R1 is done: the previous edition (Dec 2025–Feb 2026) was run on Devpost, used JetBrains IDEs + Junie and GRID data, and had $1,000 bonus prizes for **Best Video**, **Most Valuable JetBrains/Junie Feedback** and **Best Written Blog Post**. Its pre-deadline checklist asked for a **public, runnable repo** and a **linked demo video**. Re-plan K1–K7 once R1 confirms this edition's rules.

### Week by week

| Week | Dates | Focus |
|---|---|---|
| 1 | Thu 19 – Sun 22 Nov | R1 rules, P7 license, P1 judge setup path |
| 2 | Mon 23 – Sun 29 Nov | P2 README, P6 CI (Junie), P8 Junie usage |
| 3 | Mon 30 Nov – Sun 6 Dec | P3 Key findings view, P9 claims check |
| 4 | Mon 7 – Sun 13 Dec | P4 performance, P5 frontend polish (Junie) |
| 5 | Mon 14 – Sun 20 Dec | K1 video script, K4 screenshots, K3 write-up draft |
| 6 | Mon 21 Dec – Sun 3 Jan | **Holiday buffer.** K2 record video, K5 blog draft, K6 Junie feedback |
| 7 | Mon 4 – Wed 6 Jan | K7 final checklist, tag v1.0.0, **submit** |

### Rules
- [ ] R1: Confirm **this edition's** rules on the Devpost page / Competition Plan v4: required materials, video length limit, license requirement, judging criteria, bonus categories, whether JetBrains IDE / Junie use is required or judged, and the exact deadline time and zone. Write them into `docs/submission-rules.md` (owner: user)

### M4: Polish (P)
- [ ] P1: **Judge setup path.** Fresh-clone rehearsal in an empty folder (clone repo + data repo → `pip install -e .` → `build-cache` → `serve --build`) and fix every snag. Add `nunyaintel doctor` to check Python ≥ 3.14, Node, the data repo, the extract and its schema version, `maps.json` and the web build, with a fix hint for each (owner: claude)
- [ ] P2: **README for judges:** what NunyaIntel answers, screenshots, 5-step quickstart, feature tour (Scouting / Operator / Utility), architecture diagram (GRID → extract → analysis → API → React), methods (lineups, shrinkage, economy buckets), data coverage and caveats, license note (owner: claude)
- [ ] P3: **"Key findings" view:** a landing panel that generates the 3–5 strongest insights for the selected team, e.g. anti-eco loss rate vs. league average, weakest defended site, Operator dependence, best-scoring lineup. Each shows sample size and links to the detailed tab. This is the core of the demo story (owner: claude)
- [ ] P4: **Performance:** cache API responses per query (the extract is read-only, so results never go stale) and warm the common Cloud9 / Cloud9 GC queries at startup. Goal: every view under 1 s (lineup scoring is ~2.5 s now) (owner: claude)
- [ ] P5: **Frontend polish:** loading skeletons instead of text, an error boundary, mobile/narrow layout, keyboard focus styles, a "How to read this" help popover per section, and no layout shift while data loads (owner: junie)
- [ ] P6: **CI:** a GitHub Actions workflow running ruff + pytest (synthetic data only, never the licensed data) + `npm run build` on every push, with a status badge in the README (owner: junie)
- [ ] P7: **License:** choose and add a code license (MIT suggested). It covers our code only; the GRID data is not ours to license and is never in the repo (owner: user decides, claude adds)
- [ ] P8: **JetBrains/Junie usage, done for real:** Junie completes P5 and P6 from this board in PyCharm. Keep notes in `docs/junie-notes.md` (what worked, what didn't, prompts used) as raw material for K6 and the write-up (owner: user + junie)
- [ ] P9: **Claims check:** re-verify every number the video and write-up will quote, with sample sizes, against the extract. Mark small-sample claims as such, and keep "Cloud9 VCT data ends Aug 2025; 2026 = Game Changers only" visible (owner: claude)

### D3: Submission kit (K)
- [ ] K1: **Demo video script** (assume ≤ 3 min until R1 confirms): 20 s problem → 60 s Cloud9 story via Key findings → 60 s tour (plant map, Operator angles, lineup hover) → 20 s how it's built (GRID, PyCharm + Junie, FastAPI, React) → 10 s close. Show only small data excerpts on screen, as the data license allows (owner: claude drafts, user approves)
- [ ] K2: **Record and edit the video:** screen capture of `serve --open` with the user's voiceover, captions, uploaded and linked (owner: user, claude helps)
- [ ] K3: **Devpost write-up:** Inspiration / What it does / How we built it / Challenges / Accomplishments / What we learned / What's next, plus "Built with". Drafted from `docs/learning-log.md` (owner: claude drafts, user edits)
- [ ] K4: **Screenshots and GIFs** for the README and Devpost: Key findings, plant map, Operator angles, lineup hover (owner: claude)
- [ ] K5: **Blog post** (bonus category, if R1 confirms it): "Scouting Cloud9 with GRID data: what I learned building NunyaIntel", from the learning log (owner: user writes, claude edits)
- [ ] K6: **JetBrains/Junie feedback** (bonus category, if R1 confirms it): concrete, reproducible feedback from P8's notes (owner: user, claude helps)
- [ ] K7: **Final checklist (Mon 4 – Wed 6 Jan):**
  - repo public; fresh-clone rehearsal (P1) passes; CI green;
  - no data tracked (`git ls-files | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$'` prints nothing);
  - LICENSE present; video linked; tag `v1.0.0` + GitHub release;
  - Devpost form submitted by **Wed 6 Jan**, with a confirmation screenshot saved (owner: user + claude)
