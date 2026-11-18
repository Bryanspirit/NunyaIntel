# NunyaIntel: Shared Task Board

Junie and Claude Code both work from this board. Status: `[ ]` todo, `[~]` in progress, `[x]` done.
Format: `- [status] ID: description (owner: junie|claude|-)`

## Setup
- [x] S1: Project skeleton, pyproject, tests, agent guidelines (owner: claude)
- [ ] S2: Add Competition Plan v4 to `docs/` and update the cover name to NunyaIntel (owner: -)
- [x] S3: Data source = GRID starter repo; streaming reader `data/grid.py` + pre-commit data guard (owner: claude)
- [x] S4: Feed replay (handles `!` reversals and rolled-back games) → local SQLite extract `data/cache/nunyaintel.sqlite` via `nunyaintel build-cache` (owner: claude)

## Tactical Scouting
- [ ] T1: Query helpers over the extract (`rounds`/`kills`/`objectives`) for one team: maps played, per-side round win %, win types (owner: -)
- [ ] T2: Per-side round win rates and pistol/eco conversion in `scouting/report.py` (owner: -)
- [ ] T3: Site attack preferences and default setups per map (owner: -)

## Utility Placement
- [ ] U1: Load `UtilityUsage` from the `abilities` table (cast_x/y + view; quality ok) per map/side (owner: -)
- [ ] U2: Cluster placements per map/side to find common lineups (owner: -)
- [ ] U3: Effectiveness score per lineup (owner: -)

## Operator Profiler
- [x] O1: `profile_players()` + `nunyaintel operator --team <id|name> [--map m]`: rounds with Op, buy rate, Op kills, first bloods, Op K/D, win % with Op (owner: claude)
- [ ] O2: Op buy rate by economy state, plus opening-duel success (owner: -)
- [ ] O3: Common angles held per map/side (owner: -)

## Delivery
- [ ] D1: CLI commands wired to each feature (owner: -)
- [ ] D2: Presentation layer (choose after core analysis works) (owner: -)
- [ ] D3: Demo video and submission write-up, ready by 11 Jan 2027 (owner: -)
