"""Round replay data: every event of a team's rounds on one map, timed from the buy-phase end.

We only know where a player is when something happens (a cast, a shot, a death), so a replay
shows *events*, not moving players:

  kill    the team killed an enemy: target = victim's position, source = killer's position
  death   a team member died:        target = victim's position, source = killer's position
  util    the team cast an ability:  target = cast position (supplement when precise)
  plant   a spike plant (by the team or against it)
  defuse  a spike defuse

Events are sent compactly as arrays, since a map can have ~7,000 of them:
  [round_index, t_seconds, kind, u, v, u_source, v_source, label]
with u, v already converted to minimap coordinates (0..1).
"""

from __future__ import annotations

import sqlite3

from nunyaintel.maps import MapInfo
from nunyaintel.scouting.team_rounds import load_team_rounds

T_MIN, T_MAX = -45.0, 140.0  # buy phase (setup) through the longest rounds


def replay(
    con: sqlite3.Connection,
    team_id: str,
    map_info: MapInfo,
    side: str | None = None,
    since: str | None = None,
) -> dict:
    rounds = [
        r
        for r in load_team_rounds(con, team_id, map_name=map_info.name, since=since)
        if side is None or r.side == side
    ]
    index = {(r.series_id, r.game_id, r.round_num): i for i, r in enumerate(rounds)}
    if not rounds:
        return {"rounds": [], "events": [], "t_min": T_MIN, "t_max": T_MAX}
    series = sorted({r.series_id for r in rounds})
    games = sorted({r.game_id for r in rounds})
    where = (
        f"x.series_id IN ({', '.join('?' * len(series))}) "
        f"AND x.game_id IN ({', '.join('?' * len(games))})"
    )
    params = [*series, *games]
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    players = dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())

    def t_of(at: str, buy_end: str) -> float:
        from datetime import datetime

        f = lambda s: datetime.fromisoformat(s)  # noqa: E731
        return (f(at) - f(buy_end)).total_seconds()

    def uv(x, y):
        if x is None or y is None:
            return None, None
        u, v = map_info.to_minimap(x, y)
        return round(u, 4), round(v, 4)

    buy_end = {
        (s, g, n): b
        for s, g, n, b in con.execute(
            f"SELECT series_id, game_id, round_num, buy_ended_at FROM rounds x WHERE {where}",
            params,
        )
    }
    events: list[list] = []

    def add(key, at, kind, xy, src, label):
        i = index.get(key)
        b = buy_end.get(key)
        if i is None or not b or not at:
            return
        t = t_of(at, b)
        if not T_MIN <= t <= T_MAX:
            return
        u, v = uv(*xy)
        if u is None:
            return
        us, vs = uv(*src) if src else (None, None)
        events.append([i, round(t, 2), kind, u, v, us, vs, label])

    for s, g, n, at, killer, kteam, victim, weapon, kx, ky, vx, vy in con.execute(
        f"""SELECT series_id, game_id, round_num, occurred_at, killer_id, killer_team_id,
                   victim_id, weapon, killer_x, killer_y, victim_x, victim_y
            FROM kills x WHERE {where} AND ? IN (killer_team_id, victim_team_id)""",
        [*params, team_id],
    ):
        kind = "kill" if kteam == team_id else "death"
        label = f"{players.get(killer, killer)} → {players.get(victim, victim)}"
        if weapon:
            label += f" ({weapon})"
        add((s, g, n), at, kind, (vx, vy), (kx, ky), label)

    for s, g, n, at, pid, ability, cx, cy, gx, gy in con.execute(
        f"""SELECT series_id, game_id, round_num, occurred_at, player_id, ability,
                   cast_x, cast_y, grid_x, grid_y
            FROM abilities x WHERE {where} AND team_id = ?
              AND COALESCE(slot, '') != 'PASSIVE'""",
        [*params, team_id],
    ):
        xy = (cx, cy) if cx is not None else (gx, gy)
        add((s, g, n), at, "util", xy, None, f"{players.get(pid, pid)}: {ability}")

    for s, g, n, at, team, action, x, y in con.execute(
        f"""SELECT series_id, game_id, round_num, occurred_at, team_id, action, x, y
            FROM objectives x WHERE {where} AND action IN ('plantBomb', 'defuseBomb')""",
        params,
    ):
        kind = "plant" if action == "plantBomb" else "defuse"
        who = "us" if team == team_id else "them"
        add((s, g, n), at, kind, (x, y), None, f"{names.get(team, team)} ({who})")

    events.sort(key=lambda e: (e[1], e[0]))
    return {
        "rounds": [
            {
                "i": i,
                "date": r.game_started_at[:10],
                "opponent": names.get(r.opponent_id, r.opponent_id),
                "round": r.round_num,
                "side": r.side,
                "won": r.won,
                "win_type": r.win_type,
                "own_buy": r.own_buy,
            }
            for i, r in enumerate(rounds)
        ],
        "events": events,
        "t_min": T_MIN,
        "t_max": T_MAX,
    }
