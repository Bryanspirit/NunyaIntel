# NunyaIntel: Shared Task Board

Junie and Claude Code both work from this board. Status: `[ ]` todo, `[~]` in progress, `[x]` done.
Format: `- [status] ID: description (owner: junie|claude|-)`

## Setup
- [x] S1: Project skeleton, pyproject, tests, agent guidelines (owner: claude)
- [ ] S2: Add Competition Plan v4 to `docs/` and update the cover name to NunyaIntel (owner: -)
- [ ] S3: Choose the match data source and write its adapter in `nunyaintel/data/` (owner: -)
  - QUESTION: Which data feed does the hackathon provide, and how do we access it?

## Tactical Scouting
- [ ] T1: Typed round events (kills, plants, defuses, ability casts), replacing `Round.events: list[dict]` (owner: -)
- [ ] T2: Per-side round win rates and pistol/eco conversion in `scouting/report.py` (owner: -)
- [ ] T3: Site attack preferences and default setups per map (owner: -)

## Utility Placement
- [ ] U1: Extract `UtilityUsage` records from round events (owner: -)
- [ ] U2: Cluster placements per map/side to find common lineups (owner: -)
- [ ] U3: Effectiveness score per lineup (owner: -)

## Operator Profiler
- [ ] O1: Fill `OperatorProfile` from round events (owner: -)
- [ ] O2: Op buy rate by economy state, plus opening-duel success (owner: -)
- [ ] O3: Common angles held per map/side (owner: -)

## Delivery
- [ ] D1: CLI commands wired to each feature (owner: -)
- [ ] D2: Presentation layer (choose after core analysis works) (owner: -)
- [ ] D3: Demo video and submission write-up, ready by 11 Jan 2027 (owner: -)
