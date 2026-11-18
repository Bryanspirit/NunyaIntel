# NunyaIntel

NunyaIntel is an individual entry for the **Cloud9 × JetBrains: Sky's The Limit Hackathon 2026, Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler**.

- Submission deadline: **12 January 2027**. Target submit date: **11 January 2027**.

## Modules

| Package | Purpose |
|---|---|
| `nunyaintel.data` | Domain models (matches, rounds, players, events) and data source adapters |
| `nunyaintel.scouting` | Opponent tendencies and scouting reports |
| `nunyaintel.utility` | Utility placement analysis (where and when lineups are thrown, and how well they work) |
| `nunyaintel.operator_profiler` | Operator (AWP-class sniper) usage profiles per player and team |

## Setup

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\nunyaintel --help
```

## Working with AI agents

This repo is built with Junie (inside PyCharm) and Claude Code working together:
- `.junie/guidelines.md` holds the project rules that both agents follow.
- `TASKS.md` is the shared backlog. Claim a task before you start it, and tick it off when it's done.

## Data

NunyaIntel reads the hackathon's GRID dataset straight from a separate local clone of the data repo. Nothing is copied into this repo:

```powershell
cd ..; git clone https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git
# or point elsewhere:  $env:STL_DATA_DIR = "D:\path\to\stl-hackathon-2026-grid-starter"
```

The data is licensed for the hackathon only and must never be committed. `scripts/check_no_data.py` blocks it. Install the guard as a git pre-commit hook:

```sh
printf '#!/bin/sh\nexec .venv/Scripts/python.exe scripts/check_no_data.py\n' > .git/hooks/pre-commit
```
