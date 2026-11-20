"""Player profile: one player's agents, fights, weapons, Operator use, utility and positions.

Built from the same tables and functions as the team views, filtered to one player_id.
Positions (for the heatmap) are where the player shot, died or cast, converted to minimap u, v.
"""

from __future__ import annotations

import sqlite3
from collections import Counter

from nunyaintel import impact
from nunyaintel.maps import MapInfo
from nunyaintel.operator_profiler import profiler as op
from nunyaintel.utility import placement

MAX_POINTS = 6000  # heatmap points sent to the browser


def profile(con: sqlite3.Connection, player_id: str, map_info: MapInfo | None = None) -> dict:
    row = con.execute(
        "SELECT name, latest_team_id, latest_team_name, series_count, first_seen, last_seen "
        "FROM meta_players WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    if row is None:
        raise KeyError(player_id)
    name, team_id, team_name, series, first, last = row
    map_filter = "AND lower(g.map) = lower(?)" if map_info else ""
    mp = [map_info.name] if map_info else []

    agents = Counter(
        dict(
            con.execute(
                f"""SELECT r.character_name, COUNT(*) FROM meta_rosters r
                    JOIN meta_games g ON g.game_id = r.game_id
                    WHERE r.player_id = ? {map_filter} GROUP BY 1""",
                [player_id, *mp],
            ).fetchall()
        )
    )
    maps = dict(
        con.execute(
            """SELECT lower(g.map), COUNT(*) FROM meta_rosters r
               JOIN meta_games g ON g.game_id = r.game_id
               WHERE r.player_id = ? GROUP BY 1 ORDER BY 2 DESC""",
            (player_id,),
        ).fetchall()
    )

    def one(sql: str) -> int:
        return con.execute(sql.format(f=map_filter), [player_id, *mp]).fetchone()[0] or 0

    base = "FROM kills k JOIN meta_games g ON g.game_id = k.game_id WHERE {who} = ? {f}"
    kills = one("SELECT COUNT(*) " + base.replace("{who}", "k.killer_id"))
    deaths = one("SELECT COUNT(*) " + base.replace("{who}", "k.victim_id"))
    first_kills = one(
        "SELECT COUNT(*) " + base.replace("{who}", "k.killer_id") + " AND k.first_kill = 1"
    )
    first_deaths = one(
        "SELECT COUNT(*) " + base.replace("{who}", "k.victim_id") + " AND k.first_kill = 1"
    )
    weapons = con.execute(
        f"""SELECT COALESCE(k.weapon, 'ability'), COUNT(*) FROM kills k
            JOIN meta_games g ON g.game_id = k.game_id
            WHERE k.killer_id = ? {map_filter} GROUP BY 1 ORDER BY 2 DESC LIMIT 8""",
        [player_id, *mp],
    ).fetchall()

    op_row = next(
        (
            p
            for p in op.profile_players(
                con, team_id=team_id, map_name=map_info.name if map_info else None
            )
            if p.player_id == player_id
        ),
        None,
    )

    utility = []
    points: list[list] = []
    if map_info is not None:
        usages = placement.load_utility(con, map_name=map_info.name, player_id=player_id)
        utility = [
            {"agent": s.agent, "ability": s.ability, "casts": s.casts, "per_round": s.per_round,
             "buy_phase_share": s.buy_phase_share, "median_time_s": s.median_time_s}
            for s in placement.summarize(usages)
        ]  # fmt: skip
        for x, y, kind in con.execute(
            """SELECT killer_x, killer_y, 'kill' FROM kills k JOIN meta_games g USING (game_id)
                 WHERE k.killer_id = ? AND lower(g.map) = ? AND killer_x IS NOT NULL
               UNION ALL
               SELECT victim_x, victim_y, 'death' FROM kills k JOIN meta_games g USING (game_id)
                 WHERE k.victim_id = ? AND lower(g.map) = ? AND victim_x IS NOT NULL""",
            (player_id, map_info.name, player_id, map_info.name),
        ):
            u, v = map_info.to_minimap(x, y)
            points.append([round(u, 4), round(v, 4), kind])
        for u in usages:
            uu, vv = map_info.to_minimap(u.x, u.y)
            points.append([round(uu, 4), round(vv, 4), "util"])
        points = points[:MAX_POINTS]

    return {
        "player_id": player_id,
        "name": name,
        "team": {"id": team_id, "name": team_name},
        "series": int(series or 0),
        "first_seen": first,
        "last_seen": last,
        "map": map_info.name if map_info else None,
        "maps": maps,
        "agents": dict(agents.most_common()),
        "kills": kills,
        "deaths": deaths,
        "first_kills": first_kills,
        "first_deaths": first_deaths,
        "weapons": [{"weapon": w, "kills": n} for w, n in weapons],
        "operator": (
            {
                "rounds_with_op": op_row.rounds_with_op,
                "rounds_played": op_row.rounds_played,
                "op_kills": op_row.op_kills,
                "op_round_win_rate": op_row.op_round_win_rate,
            }
            if op_row
            else None
        ),  # fmt: skip
        "utility": utility,
        "points": points,
        "impact": impact.per_player(con, map_name=map_info.name if map_info else None).get(
            player_id
        ),
    }
