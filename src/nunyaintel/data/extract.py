"""Build the local NunyaIntel extract: the parts of the GRID data the project needs, in SQLite.

Each series feed is replayed once (in parallel). Only compact per-event rows are kept, so
the result is small and fast to query. The output is derived from licensed hackathon data:
it lives in ``data/cache/`` (gitignored) and must never be committed or shared.

Tables
------
meta_* ........... copies of the data repo's meta/*.csv (VALORANT rows) plus series.csv
rounds ........... one row per round: buy-phase end time, attacking/defending team, winner, win type
kills ............ enemy kills: killer/victim, sides, weapon, first blood, both positions
damage ........... every damage instance: source (weapon or ability), hit location, amount
abilities ........ ability casts from GRID + supplement cast position/aim (if quality ok)
objectives ....... spike plants / defuses / detonations with position
loadouts ......... per player per round at buy-phase end: agent, credits, loadout, weapons
"""

from __future__ import annotations

import csv
import sqlite3
import subprocess
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nunyaintel.config import CACHE_DIR
from nunyaintel.data.grid import TITLE, GridRepo, read_jsonl_zst

SCHEMA_VERSION = 2  # v2: rounds.buy_ended_at
DEFAULT_DB = CACHE_DIR / "nunyaintel.sqlite"

SCHEMA = {
    "rounds": "series_id TEXT, game_id TEXT, round_num INT, started_at TEXT, buy_ended_at TEXT, "
    "attack_team_id TEXT, defense_team_id TEXT, winner_team_id TEXT, win_type TEXT",
    "kills": "series_id TEXT, game_id TEXT, round_num INT, occurred_at TEXT, event_id TEXT, "
    "killer_id TEXT, killer_team_id TEXT, killer_side TEXT, victim_id TEXT, victim_team_id TEXT, "
    "victim_side TEXT, weapon TEXT, first_kill INT, killer_x REAL, killer_y REAL, "
    "victim_x REAL, victim_y REAL",
    "damage": "series_id TEXT, game_id TEXT, round_num INT, occurred_at TEXT, event_id TEXT, "
    "attacker_id TEXT, attacker_team_id TEXT, attacker_side TEXT, victim_id TEXT, "
    "victim_team_id TEXT, source TEXT, hit TEXT, amount INT, victim_health_after INT, "
    "attacker_x REAL, attacker_y REAL, victim_x REAL, victim_y REAL",
    "abilities": "series_id TEXT, game_id TEXT, round_num INT, occurred_at TEXT, event_id TEXT, "
    "player_id TEXT, team_id TEXT, side TEXT, ability TEXT, grid_x REAL, grid_y REAL, "
    "slot TEXT, quality TEXT, cast_x REAL, cast_y REAL, cast_z REAL, "
    "view_x REAL, view_y REAL, view_z REAL",
    "objectives": "series_id TEXT, game_id TEXT, round_num INT, occurred_at TEXT, event_id TEXT, "
    "player_id TEXT, team_id TEXT, side TEXT, action TEXT, x REAL, y REAL",
    "loadouts": "series_id TEXT, game_id TEXT, round_num INT, player_id TEXT, team_id TEXT, "
    "side TEXT, agent TEXT, money INT, loadout_value INT, weapons TEXT, has_operator INT",
}

INDEXES = [
    "CREATE INDEX ix_rounds ON rounds(series_id, game_id, round_num)",
    "CREATE INDEX ix_kills_killer ON kills(killer_id)",
    "CREATE INDEX ix_kills_weapon ON kills(weapon)",
    "CREATE INDEX ix_kills_round ON kills(series_id, game_id, round_num)",
    "CREATE INDEX ix_damage_round ON damage(series_id, game_id, round_num)",
    "CREATE INDEX ix_abilities_player ON abilities(player_id, ability)",
    "CREATE INDEX ix_abilities_round ON abilities(series_id, game_id, round_num)",
    "CREATE INDEX ix_objectives_round ON objectives(series_id, game_id, round_num)",
    "CREATE INDEX ix_loadouts_player ON loadouts(player_id)",
    "CREATE INDEX ix_loadouts_round ON loadouts(series_id, game_id, round_num)",
]

# Added in P4 after EXPLAIN QUERY PLAN showed full-table scans: Operator queries read all
# ~427k loadout rows (no index on team_id), and every join to meta_games built a temporary
# index. "IF NOT EXISTS" lets ensure_indexes() upgrade an existing extract in seconds,
# without a 7-minute rebuild.
PERF_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_loadouts_team ON loadouts"
    "(team_id, series_id, game_id, round_num)",
    "CREATE INDEX IF NOT EXISTS ix_abilities_team ON abilities(team_id, game_id)",
    "CREATE INDEX IF NOT EXISTS ix_damage_source ON damage(source, game_id)",
    "CREATE INDEX IF NOT EXISTS ix_meta_games ON meta_games(game_id)",
    "CREATE INDEX IF NOT EXISTS ix_meta_teams ON meta_teams(team_id)",
    "CREATE INDEX IF NOT EXISTS ix_meta_players ON meta_players(player_id)",
]

# GRID event type -> table whose last matching row a "!"-reversal of it removes
REVERSIBLE = {
    "player-killed-player": "kills",
    "player-damaged-player": "damage",
    "player-used-ability": "abilities",
    "player-completed-plantBomb": "objectives",
    "player-completed-defuseBomb": "objectives",
    "player-completed-explodeBomb": "objectives",
}
OBJECTIVES = {"plantBomb", "defuseBomb", "explodeBomb"}
NON_WEAPON_ITEMS = {"melee", "spike"}


def _xy(state: dict[str, Any]) -> tuple[float | None, float | None]:
    pos = (state.get("game") or {}).get("position") or {}
    return pos.get("x"), pos.get("y")


def _first_key(d: dict[str, Any] | None) -> str | None:
    return next(iter(d), None) if d else None


def _first_named(items: list[dict[str, Any]] | None, key: str) -> str | None:
    for item in items or []:
        name = (item.get(key) or {}).get("name")
        if name:
            return name
    return None


def parse_series(root: Path, series_id: str) -> dict[str, Any]:
    """Replay one series feed and return its rows per table (plus parse stats)."""
    root = Path(root)
    supplement: dict[str, dict[str, Any]] = {}
    sup_path = root / "val-ability-supplements" / f"{series_id}.jsonl.zst"
    if sup_path.exists():
        for cast in read_jsonl_zst(sup_path):
            if cast.get("in_grid") and cast.get("grid_event_id"):
                supplement[cast["grid_event_id"]] = cast

    rows: dict[str, list[dict[str, Any]]] = {t: [] for t in SCHEMA}
    rolled_back: set[str] = set()
    stats: Counter[str] = Counter()
    game_id: str | None = None
    round_num = 0

    def add(table: str, event_type: str | None = None, **row: Any) -> None:
        row.update(series_id=series_id, game_id=game_id, round_num=round_num)
        row["_type"] = event_type
        rows[table].append(row)

    feed = root / TITLE / f"events_{series_id}_grid.jsonl.zst"
    for env in read_jsonl_zst(feed):
        at = env["occurredAt"]
        for e in env["events"]:
            t, actor, target = e["type"], e.get("actor") or {}, e.get("target") or {}
            a_state, t_state = actor.get("state") or {}, target.get("state") or {}

            if "-!" in t:
                stats["reversals"] += 1
                original = t.replace("-!", "-", 1)
                if original == "series-started-game":
                    rolled_back.add(target.get("id"))
                elif original == "team-won-round":
                    for r in reversed(rows["rounds"]):
                        if r["game_id"] == game_id and r["winner_team_id"] == actor.get("id"):
                            r["winner_team_id"] = r["win_type"] = None
                            break
                elif original in REVERSIBLE:
                    table = rows[REVERSIBLE[original]]
                    for i in range(len(table) - 1, -1, -1):
                        row = table[i]
                        if row["_type"] == original and row.get("_actor") == actor.get("id"):
                            del table[i]
                            break
                continue

            if t == "series-started-game":
                game_id, round_num = target.get("id"), 0
            elif t == "game-started-round":
                round_num = t_state.get("sequenceNumber") or round_num + 1
                add(
                    "rounds",
                    t,
                    _actor=None,
                    started_at=at,
                    attack_team_id=None,
                    defense_team_id=None,
                    winner_team_id=None,
                    win_type=None,
                )
            elif t == "round-ended-freezetime":
                _record_buy_phase(e, at, game_id, add, rows["rounds"])
            elif t == "team-won-round":
                num = t_state.get("sequenceNumber") or round_num
                for r in reversed(rows["rounds"]):
                    if r["game_id"] == game_id and r["round_num"] == num:
                        r["winner_team_id"] = actor.get("id")
                        r["win_type"] = ((actor.get("stateDelta") or {}).get("round") or {}).get(
                            "winType"
                        )
                        break
            elif t == "player-killed-player":
                (kx, ky), (vx, vy) = _xy(a_state), _xy(t_state)
                delta_round = (actor.get("stateDelta") or {}).get("round") or {}
                add(
                    "kills",
                    t,
                    _actor=actor.get("id"),
                    occurred_at=at,
                    event_id=e["id"],
                    killer_id=actor.get("id"),
                    killer_team_id=a_state.get("teamId"),
                    killer_side=a_state.get("side"),
                    victim_id=target.get("id"),
                    victim_team_id=t_state.get("teamId"),
                    victim_side=t_state.get("side"),
                    weapon=_first_key(delta_round.get("weaponKills")),
                    first_kill=int(bool(delta_round.get("firstKill"))),
                    killer_x=kx,
                    killer_y=ky,
                    victim_x=vx,
                    victim_y=vy,
                )
            elif t == "player-damaged-player":
                (ax, ay), (vx, vy) = _xy(a_state), _xy(t_state)
                d = (actor.get("stateDelta") or {}).get("round") or {}
                add(
                    "damage",
                    t,
                    _actor=actor.get("id"),
                    occurred_at=at,
                    event_id=e["id"],
                    attacker_id=actor.get("id"),
                    attacker_team_id=a_state.get("teamId"),
                    attacker_side=a_state.get("side"),
                    victim_id=target.get("id"),
                    victim_team_id=t_state.get("teamId"),
                    source=_first_named(d.get("damageDealtSources"), "source"),
                    hit=_first_named(d.get("damageDealtTargets"), "target"),
                    amount=d.get("damageDealt"),
                    victim_health_after=(t_state.get("round") or {}).get("currentHealth"),
                    attacker_x=ax,
                    attacker_y=ay,
                    victim_x=vx,
                    victim_y=vy,
                )
            elif t == "player-used-ability":
                gx, gy = _xy(a_state)
                cast = supplement.get(e["id"]) or {}
                interp = cast.get("interpolated") or {}
                ok = cast.get("quality") == "ok"
                pos = (interp.get("position") or {}) if ok else {}
                view = (interp.get("view") or {}) if ok else {}
                add(
                    "abilities",
                    t,
                    _actor=actor.get("id"),
                    occurred_at=at,
                    event_id=e["id"],
                    player_id=actor.get("id"),
                    team_id=a_state.get("teamId"),
                    side=a_state.get("side"),
                    ability=target.get("id"),
                    grid_x=gx,
                    grid_y=gy,
                    slot=cast.get("slot"),
                    quality=cast.get("quality"),
                    cast_x=pos.get("x"),
                    cast_y=pos.get("y"),
                    cast_z=pos.get("z"),
                    view_x=view.get("x"),
                    view_y=view.get("y"),
                    view_z=view.get("z"),
                )
            elif t.startswith("player-completed-") and target.get("type") in OBJECTIVES:
                x, y = _xy(a_state)
                add(
                    "objectives",
                    t,
                    _actor=actor.get("id"),
                    occurred_at=at,
                    event_id=e["id"],
                    player_id=actor.get("id"),
                    team_id=a_state.get("teamId"),
                    side=a_state.get("side"),
                    action=target.get("type"),
                    x=x,
                    y=y,
                )

    for table in rows.values():
        table[:] = [r for r in table if r["game_id"] not in rolled_back]
    stats["rolled_back_games"] = len(rolled_back)
    return {"series_id": series_id, "rows": rows, "stats": dict(stats)}


def _record_buy_phase(e: dict[str, Any], at: str, game_id: str | None, add, rounds: list) -> None:
    """At the end of the buy phase, snapshot every player's agent, credits and weapons."""
    games = (e.get("seriesState") or {}).get("games") or []
    game = next((g for g in games if g.get("id") == game_id), None)
    if not game:
        return
    sides: dict[str, str] = {}
    for team in game.get("teams") or []:
        side = team.get("side")
        sides[side] = team.get("id")
        for p in team.get("players") or []:
            items = [i.get("id") for i in (p.get("inventory") or {}).get("items") or []]
            weapons = [i for i in items if i and i not in NON_WEAPON_ITEMS]
            add(
                "loadouts",
                None,
                _actor=None,
                player_id=p.get("id"),
                team_id=team.get("id"),
                side=side,
                agent=(p.get("character") or {}).get("id"),
                money=p.get("money"),
                loadout_value=p.get("loadoutValue"),
                weapons=",".join(weapons),
                has_operator=int("operator" in weapons),
            )
    if rounds and rounds[-1]["game_id"] == game_id:
        rounds[-1]["attack_team_id"] = sides.get("attacker")
        rounds[-1]["defense_team_id"] = sides.get("defender")
        rounds[-1]["buy_ended_at"] = at  # end of buy phase = start of action


def _parse_worker(args: tuple[str, str]) -> dict[str, Any]:
    root, series_id = args
    try:
        return parse_series(Path(root), series_id)
    except Exception as exc:  # keep going; report at the end
        return {"series_id": series_id, "error": f"{type(exc).__name__}: {exc}"}


def _insert(con: sqlite3.Connection, table: str, rows: Iterable[dict[str, Any]]) -> None:
    cols = [c.split()[0] for c in SCHEMA[table].split(", ")]
    con.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        ([r.get(c) for c in cols] for r in rows),
    )


def _copy_csv(con: sqlite3.Connection, name: str, path: Path, title_filter: bool) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = [c for c in reader.fieldnames or [] if not (title_filter and c == "title")]
        con.execute(f"CREATE TABLE {name} ({', '.join(f'{c} TEXT' for c in cols)})")
        con.executemany(
            f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})",
            ([r[c] for c in cols] for r in reader if not title_filter or r["title"] == TITLE),
        )


def _data_repo_commit(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return ""


def build_cache(
    db_path: Path = DEFAULT_DB,
    series_ids: Sequence[str] | None = None,
    workers: int | None = None,
    repo: GridRepo | None = None,
    progress: bool = True,
) -> dict[str, Any]:
    """(Re)build the SQLite extract. Returns a summary with row counts and any failures."""
    repo = repo or GridRepo()
    ids = list(series_ids) if series_ids else [s.series_id for s in repo.series()]
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".building.sqlite")
    tmp.unlink(missing_ok=True)

    started = time.time()
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    for name in ("teams", "players", "characters", "games", "rosters", "tournaments"):
        _copy_csv(con, f"meta_{name}", repo.root / "meta" / f"{name}.csv", title_filter=True)
    _copy_csv(con, "meta_series", repo.root / TITLE / "series.csv", title_filter=False)

    failures: dict[str, str] = {}
    stats: Counter[str] = Counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_parse_worker, (str(repo.root), sid)) for sid in ids]
        for n, fut in enumerate(as_completed(futures), 1):
            result = fut.result()
            if "error" in result:
                failures[result["series_id"]] = result["error"]
            else:
                for table, rows in result["rows"].items():
                    _insert(con, table, rows)
                stats.update(result["stats"])
            if progress and (n % 25 == 0 or n == len(ids)):
                print(f"  {n}/{len(ids)} series  ({time.time() - started:.0f}s)", flush=True)

    for ddl in INDEXES:
        con.execute(ddl)
    _create_optional_indexes(con)
    con.execute("ANALYZE")  # table statistics help SQLite's query planner pick indexes
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in SCHEMA}
    con.execute("CREATE TABLE build_info (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany(
        "INSERT INTO build_info VALUES (?, ?)",
        [
            ("schema_version", str(SCHEMA_VERSION)),
            ("built_at", datetime.now(UTC).isoformat(timespec="seconds")),
            ("data_repo", str(repo.root)),
            ("data_repo_commit", _data_repo_commit(repo.root)),
            ("series_parsed", str(len(ids) - len(failures))),
            ("series_failed", ",".join(sorted(failures))),
        ],
    )
    con.commit()
    con.close()
    tmp.replace(db_path)
    return {
        "db": str(db_path),
        "seconds": round(time.time() - started, 1),
        "series": len(ids) - len(failures),
        "failures": failures,
        "rows": counts,
        "stats": dict(stats),
        "size_mb": round(db_path.stat().st_size / 1e6, 1),
    }


def _create_optional_indexes(con: sqlite3.Connection) -> list[str]:
    """Create PERF_INDEXES that are missing; skip one whose column doesn't exist.

    They only speed things up, so an unusual table (e.g. a minimal test fixture) must not
    break an otherwise good build.
    """
    have = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    added = []
    for ddl in PERF_INDEXES:
        name = ddl.split()[5]
        if name in have:
            continue
        try:
            con.execute(ddl)
            added.append(name)
        except sqlite3.OperationalError:  # e.g. "no such column"
            pass
    return added


def ensure_indexes(db_path: Path = DEFAULT_DB) -> list[str]:
    """Add any missing performance indexes to an existing extract. Returns the ones it added.

    Opens the file read-write just for this. Safe to run repeatedly: existing indexes are
    skipped. Takes a few seconds the first time on a full extract, then ~nothing.
    """
    if not Path(db_path).exists():
        return []
    con = sqlite3.connect(db_path)
    try:
        added = _create_optional_indexes(con)
        if added:
            con.execute("ANALYZE")
        con.commit()
        return added
    finally:
        con.close()


def connect(db_path: Path = DEFAULT_DB, check_same_thread: bool = True) -> sqlite3.Connection:
    """Open the extract read-only, with rows accessible by column name.

    ``check_same_thread=False`` lets a connection be used from a different thread than the one
    that opened it. The web API needs this: FastAPI may run a request's setup (opening the
    connection) and its endpoint on different worker threads. It's safe there because each
    request still has its own connection, never shared between requests.
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"{db_path} not found. Build it with: nunyaintel build-cache")
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, check_same_thread=check_same_thread)
    con.row_factory = sqlite3.Row
    from nunyaintel import economy  # registered up front: see economy.register()

    economy.register(con)
    return con


def resolve_team(con: sqlite3.Connection, team: str) -> str:
    """Accept a team ID or an exact team name (case-insensitive) and return the team ID."""
    row = con.execute(
        "SELECT team_id FROM meta_teams WHERE team_id = ? OR lower(name) = lower(?) "
        "ORDER BY team_id = ? DESC LIMIT 1",
        (team, team, team),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown team: {team!r}")
    return row[0]
