"""Player impact: how much each player moves their team's chance of winning the round.

Every kill changes the round's win chance (winprob). The change, from the killer's team's side,
is credited to the killer and charged to the victim. A plant credits the planter; a defuse
credits the defuser with the attack's remaining chance (the round ends there).

Summed over a player's rounds and scaled per 100 rounds played, this is "round wins added":
+5 means the player's actions are worth about five extra round wins every hundred rounds
compared with an average player in the same spots. It rewards *when* a kill happens: an
opening kill or a clutch kill moves the chance much more than a kill in a 5 v 1.

The model is fitted on all rounds, so this describes what happened; it isn't a forecast.
Rounds played come from loadouts (one row per player per round).
"""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict

from nunyaintel import winprob

MIN_ROUNDS = 200  # ranked only with this many rounds behind the number

# per (player, team, map): rounds, total, from kills / deaths / plants+defuses, kills, deaths
FIELDS = ("rounds", "total", "kills_part", "deaths_part", "objective_part", "kills", "deaths")
_cache: dict[tuple, dict] = {}


def table(con: sqlite3.Connection) -> dict[tuple[str, str, str], list[float]]:
    """Impact sums for every (player, team, map), rebuilt only when the extract changes."""
    path = con.execute("PRAGMA database_list").fetchone()[2] or ":memory:"
    key = (path, os.path.getmtime(path) if os.path.exists(path) else 0)
    if key not in _cache:
        _cache.clear()
        _cache[key] = _build(con)
    return _cache[key]


def _build(con: sqlite3.Connection) -> dict[tuple[str, str, str], list[float]]:
    model = winprob.model(con)
    out: dict[tuple, list[float]] = defaultdict(lambda: [0.0] * len(FIELDS))
    rounds: dict[tuple, tuple] = {}
    for s, g, n, buy_end, mp in con.execute(
        """SELECT x.series_id, x.game_id, x.round_num, x.buy_ended_at, lower(m.map)
           FROM rounds x JOIN meta_games m ON m.game_id = x.game_id
           WHERE x.attack_team_id IS NOT NULL AND x.winner_team_id IS NOT NULL"""
    ):
        rounds[(s, g, n)] = (buy_end, mp)

    events: dict[tuple, list[tuple]] = defaultdict(list)
    for s, g, n, at, killer, kteam, victim, vteam, vside in con.execute(
        """SELECT series_id, game_id, round_num, occurred_at, killer_id, killer_team_id,
                  victim_id, victim_team_id, victim_side FROM kills WHERE occurred_at IS NOT NULL"""
    ):
        events[(s, g, n)].append((at, "kill", killer, kteam, victim, vteam, vside))
    for s, g, n, at, pid, team, action in con.execute(
        """SELECT series_id, game_id, round_num, occurred_at, player_id, team_id, action
           FROM objectives
           WHERE action IN ('plantBomb', 'defuseBomb') AND occurred_at IS NOT NULL"""
    ):
        events[(s, g, n)].append((at, action, pid, team, None, None, None))

    for key, evs in events.items():
        if key not in rounds:
            continue
        buy_end, mp = rounds[key]
        a, d, planted, plant_at = 5, 5, 0, None
        prev = model.p_attack(a, d, planted, winprob.START_BAND)
        for at, kind, pid, team, victim, vteam, vside in sorted(evs, key=lambda e: e[0]):
            if kind == "defuseBomb":
                if planted:  # the defenders win: they gain the attack's remaining chance
                    out[(pid, team, mp)][1] += prev
                    out[(pid, team, mp)][4] += prev
                break
            if kind == "kill":
                if vside == "attacker":
                    a = max(0, a - 1)
                else:
                    d = max(0, d - 1)
            elif not planted:
                planted, plant_at = 1, at
            else:
                continue  # a second plant record: nothing changes
            try:
                t_round = winprob._secs(at, buy_end) if buy_end else None
                t_plant = winprob._secs(at, plant_at) if plant_at else None
            except ValueError:
                t_round = t_plant = None
            now = model.p_attack(a, d, planted, winprob.band(t_round, t_plant))
            delta = now - prev  # change in the attack's chance
            prev = now
            if kind == "plantBomb":
                out[(pid, team, mp)][1] += delta
                out[(pid, team, mp)][4] += delta
                continue
            gain = -delta if vside == "attacker" else delta  # for the killer's team
            k, v = out[(pid, team, mp)], out[(victim, vteam, mp)]
            k[1] += gain
            k[2] += gain
            k[5] += 1
            v[1] -= gain
            v[3] -= gain
            v[6] += 1

    for pid, team, mp, n in con.execute(
        """SELECT l.player_id, l.team_id, lower(m.map), COUNT(*) FROM loadouts l
           JOIN meta_games m ON m.game_id = l.game_id GROUP BY 1, 2, 3"""
    ):
        out[(pid, team, mp)][0] += n
    return dict(out)


def _sum(rows) -> list[float]:
    acc = [0.0] * len(FIELDS)
    for r in rows:
        for i, v in enumerate(r):
            acc[i] += v
    return acc


def per_player(
    con: sqlite3.Connection, map_name: str | None = None, team_id: str | None = None
) -> dict[str, dict]:
    """Impact per player (optionally on one map / for one team), with league ranks."""
    t = table(con)
    groups: dict[str, list] = defaultdict(list)
    for (pid, team, mp), row in t.items():
        if (map_name is None or mp == map_name.lower()) and (team_id is None or team == team_id):
            groups[pid].append(row)
    out = {}
    for pid, rows in groups.items():
        r = _sum(rows)
        if not r[0]:
            continue
        per = 100 / r[0]
        out[pid] = {
            "player_id": pid, "rounds": int(r[0]), "per_100": r[1] * per,
            "kills_per_100": r[2] * per, "deaths_per_100": r[3] * per,
            "objectives_per_100": r[4] * per, "kills": int(r[5]), "deaths": int(r[6]),
            "per_kill": r[2] / r[5] if r[5] else 0.0,
        }  # fmt: skip
    ranked = sorted(
        (p for p in out.values() if p["rounds"] >= MIN_ROUNDS), key=lambda p: -p["per_100"]
    )
    for i, p in enumerate(ranked, 1):
        p["rank"], p["ranked"] = i, len(ranked)
    return out


def team_players(con: sqlite3.Connection, team_id: str, map_name: str | None = None) -> list[dict]:
    """The team's players, highest impact first, ranked against the whole league."""
    league = per_player(con, map_name=map_name)  # league ranks (all teams)
    mine = per_player(con, map_name=map_name, team_id=team_id)  # only rounds for this team
    names = dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())
    rows = []
    for pid, p in mine.items():
        rank = league.get(pid, {})
        rows.append({**p, "name": names.get(pid, pid),
                     "rank": rank.get("rank"), "ranked": rank.get("ranked")})  # fmt: skip
    return sorted(rows, key=lambda p: -p["per_100"])
