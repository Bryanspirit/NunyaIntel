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
- No runtime dependencies yet. To add one, put it in `pyproject.toml` and note the reason in your task entry.

## Layout
- `src/nunyaintel/data/`: provider-agnostic models (`models.py`) and the `DataSource` protocol (`sources.py`). Provider adapters go here and map raw feeds onto those models. Analysis code never reads a raw feed directly.
- `src/nunyaintel/scouting/`, `utility/`, `operator_profiler/`: one package per Category 1 feature.
- `src/nunyaintel/__main__.py`: CLI (`nunyaintel scout|utility|operator`).
- `tests/`: pytest. Every new module gets tests.
- `data/raw`, `data/processed`: local data, gitignored. Never commit match data or API keys.
- `docs/`: competition plan and design notes.

## Rules
1. Before you start a task, claim it in `TASKS.md` by setting its owner to `junie` or `claude`. Only work on tasks you've claimed. Don't edit files another agent's in-progress task is changing.
2. Keep changes small and focused, with one task per change. When you finish a task, run the tests and lint, then tick the task off.
3. Use type hints everywhere. Use dataclasses for models. Write pure functions for analysis (data in, results out).
4. Secrets come from environment variables only (`nunyaintel.config.get_env`).
5. If a requirement is unclear, add a `QUESTION:` line under the task in `TASKS.md` and don't guess.
