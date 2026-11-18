# NunyaIntel: Shared Task Board

Junie and Claude Code both work from this board. Status: `[ ]` todo, `[~]` in progress, `[x]` done.
Format: `- [status] ID: description (owner: junie|claude|-)`

## Schedule: everything finished by **Wed 6 Jan 2027** (official deadline 12 Jan, so 6 days of buffer)

| Milestone | Due | Scope |
|---|---|---|
| M1 Core analytics | Sun 29 Nov | T1, T2, O1 ✓, O2 ✓, U1 ✓ |
| M2 Feature depth | Sun 13 Dec | T3, U2 ✓, U3, O3, D1 |
| M3 Feature-complete (feature freeze) | Sun 20 Dec | D2 presentation layer working end-to-end |
| M4 Polish + demo | Sun 3 Jan | bug fixes, README, demo video and write-up drafts (holidays are buffer) |
| **Finish** | **Wed 6 Jan** | D3 submission package complete and checked |

If a milestone slips, cut scope (U3/O3 are the first candidates). Don't move the 6 Jan date.

## Setup
- [x] S1: Project skeleton, pyproject, tests, agent guidelines (owner: claude)
- [ ] S2: Add Competition Plan v4 to `docs/` and update the cover name to NunyaIntel (owner: -)
- [x] S3: Data source = GRID starter repo; streaming reader `data/grid.py` + pre-commit data guard (owner: claude)
- [x] S4: Feed replay (handles `!` reversals and rolled-back games) → local SQLite extract `data/cache/nunyaintel.sqlite` via `nunyaintel build-cache` (owner: claude)

## Tactical Scouting
- [ ] T1: Query helpers over the extract (`rounds`/`kills`/`objectives`) for one team: maps played, per-side round win %, win types (owner: -)
- [ ] T2: Per-side round win rates and pistol/eco conversion in `scouting/report.py`. Use `nunyaintel.economy.classify_buy` / `economy.register(con)` for eco/pistol definitions (owner: -)
- [ ] T3: Site attack preferences and default setups per map (owner: -)

## Utility Placement
- [x] U1: `load_utility()` + `nunyaintel utility --team <t> --map <m> [--side]`: casts with supplement position/aim, timing vs. buy-phase end (extract v2 adds `rounds.buy_ended_at`), per-ability summary (owner: claude)
- [x] U2: `find_lineups()` (DBSCAN on cast spot + aim, per team/map/side/agent/ability, recurring in >= 2 matches) + `nunyaintel utility ... --lineups [--radius --angle --min-matches]` (owner: claude)
- [ ] U3: Effectiveness score per lineup (owner: -)

## Operator Profiler
- [x] O1: `profile_players()` + `nunyaintel operator --team <id|name> [--map m]`: rounds with Op, buy rate, Op kills, first bloods, Op K/D, win % with Op (owner: claude)
- [x] O2: `nunyaintel operator --economy` (Op rate per team economy state) and `--duels` (opening duels with vs. without Op); shared buy classifier in `nunyaintel/economy.py` (owner: claude)
- [ ] O3: Common angles held per map/side (owner: -)

## Delivery
- [ ] D1: CLI commands wired to each feature (owner: -)
- [ ] D2: Presentation layer (choose after core analysis works) (owner: -)
- [ ] D3: Demo video and submission write-up, complete by **6 Jan 2027** (owner: -)
