# NunyaIntel: Shared Task Board

Junie and Claude Code both work from this board. Status: `[ ]` todo, `[~]` in progress, `[x]` done.
Format: `- [status] ID: description (owner: junie|claude|-)`

## Setup
- [x] S1: Project skeleton, pyproject, tests, agent guidelines (owner: claude)
- [ ] S2: Add Competition Plan v4 to `docs/` and update the cover name to NunyaIntel (owner: -)
- [x] S3: Data source = GRID starter repo; streaming reader `data/grid.py` + pre-commit data guard (owner: claude)
- [ ] S4: Feed parser: replay one series into `Match`/`Round` models, handling `!` reversals and rolled-back games (owner: -)

## Tactical Scouting
- [ ] T1: Typed round events (kills + weapon, plants, defuses, ability casts, winType), replacing `Round.events: list[dict]` (owner: -)
- [ ] T2: Per-side round win rates and pistol/eco conversion in `scouting/report.py` (owner: -)
- [ ] T3: Site attack preferences and default setups per map (owner: -)

## Utility Placement
- [ ] U1: Build `UtilityUsage` from ability supplement `interpolated` position/view (quality ok), joined to GRID events (owner: -)
- [ ] U2: Cluster placements per map/side to find common lineups (owner: -)
- [ ] U3: Effectiveness score per lineup (owner: -)

## Operator Profiler
- [ ] O1: Fill `OperatorProfile` from kills where weaponKills has `operator` (owner: -)
- [ ] O2: Op buy rate by economy state, plus opening-duel success (owner: -)
- [ ] O3: Common angles held per map/side (owner: -)

## Delivery
- [ ] D1: CLI commands wired to each feature (owner: -)
- [ ] D2: Presentation layer (choose after core analysis works) (owner: -)
- [ ] D3: Demo video and submission write-up, ready by 11 Jan 2027 (owner: -)
