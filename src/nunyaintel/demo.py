"""A made-up demo dataset: run the whole app (and its browser tests) without the licensed data.

`nunyaintel make-demo` writes data/cache/nunyaintel.sqlite and data/cache/maps.json with the
same tables as a real extract, filled with invented teams, players and rounds on one invented
map ("Demomap"). Nothing in it comes from the GRID data, so it can be used anywhere, e.g. in
CI. A fixed random seed makes it the same every time.

It refuses to overwrite a real extract unless --force is given.
"""

from __future__ import annotations

import json
import random
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nunyaintel.data.extract import DEFAULT_DB, INDEXES, SCHEMA, SCHEMA_VERSION
from nunyaintel.maps import DEFAULT_PATH as MAPS_PATH

MAP = "Demomap"
SITES = {"A": (2600.0, 1200.0), "B": (-2600.0, -900.0)}
CALLOUTS = [
    ("A", "Site", 2600, 1200), ("A", "Main", 3300, -500), ("A", "Link", 1200, 900),
    ("B", "Site", -2600, -900), ("B", "Main", -3200, 700), ("Mid", "Courtyard", 0, 0),
    ("Attacker Side", "Spawn", 0, -3600), ("Defender Side", "Spawn", 0, 3500),
]  # fmt: skip
TEAMS = {
    "T1": ("Northwind", 0.58, ["Aster", "Brisk", "Cobalt", "Drift", "Ember"]),
    "T2": ("Harbor Lights", 0.50, ["Fable", "Gale", "Halo", "Iris", "Jolt"]),
    "T3": ("Quarry Five", 0.44, ["Kestrel", "Lumen", "Moss", "Nova", "Onyx"]),
}
AGENTS = ["omen", "sova", "killjoy", "jett", "skye"]
ABILITIES = {"omen": "dark-cover", "sova": "recon-bolt", "killjoy": "nanoswarm",
             "jett": "cloudburst", "skye": "guiding-light"}  # fmt: skip
WEAPONS = ["vandal", "phantom", "operator", "sheriff", "spectre"]
START = datetime(2026, 3, 2, 18, 0, tzinfo=UTC)


def demo_maps() -> dict:
    """A valorant-api.com style maps.json with one invented map."""
    return {"data": [{
        "displayName": MAP, "displayIcon": None,
        "xMultiplier": 0.00009, "yMultiplier": -0.00009, "xScalarToAdd": 0.5, "yScalarToAdd": 0.5,
        "callouts": [{"regionName": r, "superRegionName": s, "location": {"x": x, "y": y}}
                     for s, r, x, y in CALLOUTS],
    }]}  # fmt: skip


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build(db_path: Path = DEFAULT_DB, maps_path: Path = MAPS_PATH, force: bool = False) -> dict:
    db_path, maps_path = Path(db_path), Path(maps_path)
    if db_path.exists() and not force:
        # closing(): `with sqlite3.connect()` alone only commits, it doesn't close the file,
        # and Windows can't delete a file that is still open
        try:
            with closing(sqlite3.connect(db_path)) as con:
                row = con.execute("SELECT value FROM build_info WHERE key = 'data_repo'").fetchone()
        except sqlite3.Error:
            row = None
        if not row or row[0] != "demo":
            raise FileExistsError(f"{db_path} is a real extract: use --force to replace it")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    maps_path.write_text(json.dumps(demo_maps()), encoding="utf-8")

    rng = random.Random(7)
    con = sqlite3.connect(db_path)
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    meta = {
        "meta_teams": "team_id, name, other_names, series_count, events, first_seen, last_seen",
        "meta_players": "player_id, name, other_names, latest_team_id, latest_team_name, team_ids, "
        "series_count, first_seen, last_seen",
        "meta_games": "series_id, game_id, game_number, map, patch, started_at, finished, "
        "winner_team_id, team1_id, team1_name, team1_side, team1_score, team2_id, team2_name, "
        "team2_side, team2_score",
        "meta_series": "series_id, event, stage, scheduled_start, teams, file, ability_supplement",
        "meta_rosters": "series_id, game_id, game_number, team_id, team_name, side, player_id, "
        "player_name, character_id, character_name, participation_status",
    }
    for table, cols in meta.items():
        con.execute(f"CREATE TABLE {table} ({', '.join(c + ' TEXT' for c in cols.split(', '))})")

    def ins(table: str, **row):
        con.execute(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                    list(row.values()))  # fmt: skip

    players = {tid: [f"{tid}P{i}" for i in range(5)] for tid in TEAMS}
    pairs = [("T1", "T2"), ("T1", "T3"), ("T2", "T3")] * 4
    series_count = {t: 0 for t in TEAMS}
    ev = 0
    for si, (a, b) in enumerate(pairs):
        sid = f"S{si:02d}"
        day = START + timedelta(days=4 * si)
        series_count[a] += 1
        series_count[b] += 1
        ins(
            "meta_series",
            series_id=sid,
            event="Demo Invitational 2026",
            stage="Groups",
            scheduled_start=_iso(day),
            teams=f"{a},{b}",
            file="demo",
            ability_supplement="",
        )
        gid = f"G{si:02d}"
        rounds_a = rounds_b = 0
        t = day
        rn = 0
        while max(rounds_a, rounds_b) < 13:
            rn += 1
            att, dfn = (a, b) if rn <= 12 else (b, a)
            p_att = 0.5 + (TEAMS[att][1] - TEAMS[dfn][1]) + (0.03 if att == "T1" else 0)
            # each team has a habit: T1 hits late at A, T2 fast at B, T3 splits
            site = (
                "A"
                if (att == "T1" and rng.random() < 0.7) or (att == "T3" and rng.random() < 0.5)
                else "B"
            )
            hit_t = {"T1": 72, "T2": 30, "T3": 50}[att] + rng.uniform(-12, 12)
            buy_end = t + timedelta(seconds=30)
            ins(
                "rounds",
                series_id=sid,
                game_id=gid,
                round_num=rn,
                started_at=_iso(t),
                buy_ended_at=_iso(buy_end),
                attack_team_id=att,
                defense_team_id=dfn,
                winner_team_id=None,
                win_type=None,
            )
            alive = {att: list(players[att]), dfn: list(players[dfn])}
            # loadouts: pistol rounds cheap, otherwise mostly full buys, sometimes ecos
            for team, side in ((att, "attacker"), (dfn, "defender")):
                eco = rn not in (1, 13) and rng.random() < 0.15
                for i, pid in enumerate(players[team]):
                    value = 800 if rn in (1, 13) else (1200 if eco else rng.randint(3600, 4600))
                    ins(
                        "loadouts",
                        series_id=sid,
                        game_id=gid,
                        round_num=rn,
                        player_id=pid,
                        team_id=team,
                        side=side,
                        agent=AGENTS[i],
                        money=value + 300,
                        loadout_value=value,
                        weapons="",
                        has_operator=int(i == 3 and value > 3500),
                    )
                    if rn == 1:
                        ins(
                            "meta_rosters",
                            series_id=sid,
                            game_id=gid,
                            game_number="1",
                            team_id=team,
                            team_name=TEAMS[team][0],
                            side=side,
                            player_id=pid,
                            player_name=TEAMS[team][2][i],
                            character_id=AGENTS[i],
                            character_name=AGENTS[i],
                            participation_status="active",
                        )
            # utility near the target site before the hit
            for i, pid in enumerate(players[att][:3]):
                sx, sy = SITES[site]
                ev += 1
                at = buy_end + timedelta(seconds=max(2, hit_t - 20 + i * 3))
                ins("abilities", series_id=sid, game_id=gid, round_num=rn, occurred_at=_iso(at),
                    event_id=f"e{ev}", player_id=pid, team_id=att, side="attacker",
                    ability=ABILITIES[AGENTS[i]], grid_x=sx + rng.uniform(-400, 400),
                    grid_y=sy + rng.uniform(-400, 400), slot="ABILITY_1", quality="ok",
                    cast_x=sx + rng.uniform(-300, 300), cast_y=sy + rng.uniform(-300, 300),
                    cast_z=0, view_x=1, view_y=0, view_z=0)  # fmt: skip
            # fights until one side is out, or the spike decides it
            won_att = rng.random() < p_att
            planted = rng.random() < 0.7
            clock = 12.0
            first = True
            while alive[att] and alive[dfn]:
                clock += rng.uniform(4, 14)
                attacker_wins_fight = rng.random() < (0.62 if won_att else 0.38)
                killer_team, victim_team = (att, dfn) if attacker_wins_fight else (dfn, att)
                killer = rng.choice(alive[killer_team])
                victim = alive[victim_team].pop(rng.randrange(len(alive[victim_team])))
                sx, sy = SITES[site]
                ev += 1
                at = buy_end + timedelta(seconds=clock)
                weapon = (
                    "operator"
                    if killer.endswith("P3") and rng.random() < 0.4
                    else rng.choice(WEAPONS[:2] + WEAPONS[3:])
                )
                ins("kills", series_id=sid, game_id=gid, round_num=rn, occurred_at=_iso(at),
                    event_id=f"e{ev}", killer_id=killer, killer_team_id=killer_team,
                    killer_side="attacker" if killer_team == att else "defender", victim_id=victim,
                    victim_team_id=victim_team, victim_side="attacker" if victim_team == att else "defender",
                    weapon=weapon, first_kill=int(first), killer_x=sx + rng.uniform(-900, 900),
                    killer_y=sy + rng.uniform(-1500, 300), victim_x=sx + rng.uniform(-600, 600),
                    victim_y=sy + rng.uniform(-600, 600))  # fmt: skip
                ins("damage", series_id=sid, game_id=gid, round_num=rn, occurred_at=_iso(at),
                    event_id=f"d{ev}", attacker_id=killer, attacker_team_id=killer_team,
                    attacker_side="attacker" if killer_team == att else "defender", victim_id=victim,
                    victim_team_id=victim_team, source=weapon, hit="body", amount=150,
                    victim_health_after=0, attacker_x=sx, attacker_y=sy - 800, victim_x=sx, victim_y=sy)  # fmt: skip
                first = False
                if planted and clock >= hit_t and alive[att]:
                    ev += 1
                    sx, sy = SITES[site]
                    ins("objectives", series_id=sid, game_id=gid, round_num=rn,
                        occurred_at=_iso(buy_end + timedelta(seconds=hit_t)), event_id=f"e{ev}",
                        player_id=alive[att][0], team_id=att, side="attacker", action="plantBomb",
                        x=sx + rng.uniform(-200, 200), y=sy + rng.uniform(-200, 200))  # fmt: skip
                    planted = False  # one plant
            winner = att if alive[att] else dfn
            win_type = "opponentEliminated"
            con.execute("UPDATE rounds SET winner_team_id = ?, win_type = ? WHERE game_id = ? AND round_num = ?",
                        (winner, win_type, gid, rn))  # fmt: skip
            if winner == a:
                rounds_a += 1
            else:
                rounds_b += 1
            t = buy_end + timedelta(seconds=clock + 15)
        ins(
            "meta_games",
            series_id=sid,
            game_id=gid,
            game_number="1",
            map=MAP,
            patch="1.0",
            started_at=_iso(day),
            finished="true",
            winner_team_id=a if rounds_a > rounds_b else b,
            team1_id=a,
            team1_name=TEAMS[a][0],
            team1_side="attacker",
            team1_score=str(rounds_a),
            team2_id=b,
            team2_name=TEAMS[b][0],
            team2_side="defender",
            team2_score=str(rounds_b),
        )

    last = _iso(START + timedelta(days=4 * len(pairs)))
    for tid, (name, _, names) in TEAMS.items():
        ins(
            "meta_teams",
            team_id=tid,
            name=name,
            other_names="",
            series_count=str(series_count[tid]),
            events="Demo Invitational 2026",
            first_seen=_iso(START),
            last_seen=last,
        )
        for i, pid in enumerate(players[tid]):
            ins(
                "meta_players",
                player_id=pid,
                name=names[i],
                other_names="",
                latest_team_id=tid,
                latest_team_name=name,
                team_ids=tid,
                series_count=str(series_count[tid]),
                first_seen=_iso(START),
                last_seen=last,
            )
    for ddl in INDEXES:
        con.execute(ddl)
    con.execute("CREATE TABLE build_info (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO build_info VALUES (?, ?)", [
        ("schema_version", str(SCHEMA_VERSION)), ("built_at", _iso(datetime.now(UTC))),
        ("data_repo", "demo"), ("data_repo_commit", "demo"),
    ])  # fmt: skip
    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in SCHEMA}
    con.close()
    return counts
