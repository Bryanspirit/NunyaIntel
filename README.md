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
