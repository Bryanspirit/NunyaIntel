# NunyaIntel: Agent Guidelines

Junie reads this file automatically, and Claude Code follows it too. Keep it current.

## Project
- **Name:** NunyaIntel. Always use this name. Never use "VALORANT IntelAI", which is an old name.
- **Goal:** Cloud9 × JetBrains Hackathon 2026, Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler.
- **Deadline:** 12 Jan 2027. We aim to submit on **11 Jan 2027**, so scope every task to fit that date.

## Stack
- Python 3.14 in `.venv`, `src/` layout, package `nunyaintel`, configured in `pyproject.toml`.
- Install: `.venv\Scripts\python -m pip install -e ".[dev]"`
- Test: `.venv\Scripts\python -m pytest`. Lint: `.venv\Scripts\python -m ruff check .`
- Python **3.14+** is required (stdlib `compression.zstd` reads the data). No runtime dependencies yet. To add one, put it in `pyproject.toml` and note the reason in your task entry.

## Layout
- `src/nunyaintel/data/`: provider-agnostic models (`models.py`) and the `DataSource` protocol (`sources.py`). Provider adapters go here and map raw feeds onto those models. Analysis code never reads a raw feed directly.
- `src/nunyaintel/scouting/`, `utility/`, `operator_profiler/`: one package per Category 1 feature.
- `src/nunyaintel/__main__.py`: CLI (`nunyaintel scout|utility|operator`).
- `tests/`: pytest. Every new module gets tests.
- `src/nunyaintel/data/grid.py`: `GridRepo` gives streaming access to the hackathon data (series index, `meta/` tables, event feeds, ability supplements).
- `data/raw`, `data/processed`, `data/cache`: local derived data, gitignored. Never commit match data or API keys.
- `scripts/check_no_data.py`: pre-commit guard that blocks data files.
- `docs/`: competition plan and design notes.

## Data: GRID hackathon dataset (licensed)
- Source: https://github.com/cloud9esports/stl-hackathon-2026-grid-starter, cloned **next to** this project at `../stl-hackathon-2026-grid-starter` (override with the `STL_DATA_DIR` env var). Read that repo's `AGENTS.md` and `README.md` before writing data code.
- **Never copy, commit or push any data or extract of it** (`.zst`, `.jsonl`, `meta/*.csv`, `series.csv`, caches, DBs). Never `git add -A`; stage files by name and check `git diff --cached --name-only`. Tests use small synthetic files only.
- Find matches through the index first (`val/series.csv`, `meta/*.csv`), and don't glob the folders. Stream feeds line by line; don't decompress the corpus to disk.
- Join on IDs, never on names. Cloud9 VCT Americas has team ID `79`.
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
