# NunyaIntel: Agent Guidelines

Junie reads this file automatically, and Claude Code follows it too. Keep it current.

## Project
- **Name:** NunyaIntel. Always use this name. Never use "VALORANT IntelAI", which is an old name.
- **Goal:** Cloud9 × JetBrains Hackathon 2026, Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler.
- **Deadline:** 12 Jan 2027. **Everything must be finished by 6 Jan 2027.** Milestones are in `TASKS.md`, so scope every task to fit them.

## Stack
- Python 3.14 in `.venv`, `src/` layout, package `nunyaintel`, configured in `pyproject.toml`.
- Install: `.venv\Scripts\python -m pip install -e ".[dev]"`
- Test: `.venv\Scripts\python -m pytest`. Lint: `.venv\Scripts\python -m ruff check .`
- Python **3.14+** is required (stdlib `compression.zstd` reads the data). No runtime dependencies yet. To add one, put it in `pyproject.toml` and note the reason in your task entry.

## Layout
- `src/nunyaintel/data/`: provider-agnostic models (`models.py`) and the `DataSource` protocol (`sources.py`). Provider adapters go here and map raw feeds onto those models. Analysis code never reads a raw feed directly.
- `src/nunyaintel/scouting/`, `utility/`, `operator_profiler/`: one package per Category 1 feature.
- `src/nunyaintel/economy.py`: shared buy-type classifier (pistol / eco / semi-eco / semi-buy / full-buy). Use it for any economy analysis; `economy.register(con)` exposes `classify_buy()` in SQL.
- `docs/learning-log.md`: the user is learning as we build. After finishing a task, add an entry (what, key ideas, how to run, what to read).
- `src/nunyaintel/__main__.py`: CLI (`nunyaintel scout|utility|operator`).
- `tests/`: pytest. Every new module gets tests.
- `src/nunyaintel/data/grid.py`: `GridRepo` gives streaming access to the hackathon data (series index, `meta/` tables, event feeds, ability supplements).
- `src/nunyaintel/data/extract.py`: builds the **local extract** `data/cache/nunyaintel.sqlite` (`nunyaintel build-cache`, ~5 min, all 857 VALORANT series). **Analysis code queries this extract via `extract.connect()`, not the raw feeds.** Tables:
  - `rounds` (buy_ended_at = start of action, attack/defense team, winner, win_type), `kills` (weapon, first_kill, killer/victim x,y), `damage` (source = weapon or ability, hit, amount), `abilities` (GRID x,y + supplement cast_x/y/z & view_x/y/z when quality ok), `objectives` (plant/defuse/explode x,y), `loadouts` (per player per round after buy phase: agent, money, loadout_value, weapons, has_operator)
  - `meta_series`, `meta_games` (map, scores), `meta_rosters`, `meta_teams`, `meta_players`, `meta_characters`, `meta_tournaments`; `build_info`
  - Keys: `(series_id, game_id, round_num)`; player/team IDs are GRID IDs (strings).
  - Full build: 857 series, 2,078 maps, 42.6k rounds, 298k kills, 1.4M ability casts, ~930 MB.
  - Caveats: (1) `kills.weapon` is NULL for ability kills (~3.7%, e.g. tour-de-force, blade-storm). The ability is the `damage.source` of the same victim at the same `occurred_at`. (2) To count real rounds, use `rounds.winner_team_id IS NOT NULL` and join `meta_games` on `game_id`. This drops 3 stray game fragments and 109 restarted rounds. Winner counts then match final scores exactly.
- `data/raw`, `data/processed`, `data/cache`: local derived data, gitignored. Never commit match data or API keys.
- `scripts/check_no_data.py`: pre-commit guard that blocks data files.
- `docs/`: competition plan and design notes.

## Data: GRID hackathon dataset (licensed)
- Source: https://github.com/cloud9esports/stl-hackathon-2026-grid-starter, cloned **next to** this project at `../stl-hackathon-2026-grid-starter` (override with the `STL_DATA_DIR` env var). Read that repo's `AGENTS.md` and `README.md` before writing data code.
- **Never copy, commit or push any data or extract of it** (`.zst`, `.jsonl`, `meta/*.csv`, `series.csv`, caches, DBs). Never `git add -A`; stage files by name and check `git diff --cached --name-only`. Tests use small synthetic files only.
- Find matches through the index first (`val/series.csv`, `meta/*.csv`), and don't glob the folders. Stream feeds line by line; don't decompress the corpus to disk.
- Join on IDs, never on names. **Cloud9** (VCT Americas) = team `79`: 19 matches, Jan–Aug 2025. **Cloud9 GC** (Game Changers) = team `3429`: 9 matches, Jul–Sep 2026.
- **Coverage:** there are no VCT (main-team) matches in 2026. All 2026 data is Game Changers. Keep this in mind for "recent form" claims.
- Feed basics: event `type` = `{actor}-{action}-{target}`. A `!` before the action reverses an earlier event. Drop games rolled back by `series-!started-game`. The final box score is the last `seriesState`.
- Kill weapon: in `player-killed-player`, it's `actor.stateDelta.round.weaponKills` (e.g. `{"operator": 1}`). Round result: `team-won-round` → `actor.stateDelta.round.winType`.
- Ability positions: use the supplement's `interpolated.position`/`view`, joined on `grid_event_id` == event `id`, when `quality == "ok"`. VCT Americas 2025 is 1 Hz, so it's less precise.
- The license ends with the hackathon. Use the data for this project only.

## Rules
1. Before you start a task, claim it in `TASKS.md` by setting its owner to `junie` or `claude`. Only work on tasks you've claimed. Don't edit files another agent's in-progress task is changing.
2. Keep changes small and focused, with one task per change. When you finish a task, run the tests and lint, then tick the task off.
3. Use type hints everywhere. Use dataclasses for models. Write pure functions for analysis (data in, results out).
4. Secrets come from environment variables only (`nunyaintel.config.get_env`).
5. If a requirement is unclear, add a `QUESTION:` line under the task in `TASKS.md` and don't guess.
