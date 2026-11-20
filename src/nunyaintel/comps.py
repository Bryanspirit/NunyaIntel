"""Agent compositions, and what has changed in a team's recent matches.

comps   each map a team played has one composition: its five agents (from the rosters).
        We group identical comps per map and count maps won, next to the league's most
        common comps on that map.

recent  the team's last few matches against everything before them:
        - the league metrics (attack, defense, pistols, ecos…), with a two-proportion z-test
          so only changes bigger than luck are called changes
        - each player's agents (new / dropped), Operator use, and the maps the team plays
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict

from nunyaintel import insights
from nunyaintel.scouting.team_rounds import load_team_rounds

RECENT_SERIES = 5  # "recent" = the team's last five matches
MIN_EARLIER_SERIES = 3  # need a real "before" to compare with
CHANGE_Z = 1.5  # a rate change counts when it's this many standard errors


def _game_comps(con: sqlite3.Connection, team_id: str | None = None):
    """(game, team, map, date, won, comp tuple) for every map with five known agents."""
    rows = con.execute(
        f"""SELECT r.game_id, r.team_id, lower(g.map), g.started_at, g.winner_team_id,
                   group_concat(lower(r.character_name), ',')
            FROM meta_rosters r JOIN meta_games g ON g.game_id = r.game_id
            {"WHERE r.team_id = ?" if team_id else ""}
            GROUP BY r.game_id, r.team_id""",
        (team_id,) if team_id else (),
    ).fetchall()
    for game, team, mp, date, winner, agents in rows:
        names = sorted(a for a in (agents or "").split(",") if a)
        if len(names) == 5:
            yield game, team, mp, (date or "")[:10], winner == team, tuple(names)


def comps(con: sqlite3.Connection, team_id: str, map_name: str | None = None) -> dict:
    team: dict[tuple, list] = defaultdict(lambda: [0, 0, ""])  # (map, comp) -> maps, wins, last
    for _, _, mp, date, won, comp in _game_comps(con, team_id):
        if map_name and mp != map_name.lower():
            continue
        t = team[(mp, comp)]
        t[0] += 1
        t[1] += won
        t[2] = max(t[2], date)
    league: dict[str, Counter] = defaultdict(Counter)
    league_wins: dict[tuple, int] = Counter()
    for _, _, mp, _, won, comp in _game_comps(con):
        if map_name and mp != map_name.lower():
            continue
        league[mp][comp] += 1
        league_wins[(mp, comp)] += won
    out_team = [
        {
            "map": mp,
            "agents": list(comp),
            "maps": n,
            "wins": w,
            "last_played": last,
            "league_maps": league[mp][comp],
        }  # fmt: skip
        for (mp, comp), (n, w, last) in sorted(team.items(), key=lambda kv: (-kv[1][0], kv[0]))
    ]
    out_league = {
        mp: [
            {"agents": list(comp), "maps": n, "wins": league_wins[(mp, comp)]}
            for comp, n in counter.most_common(5)
        ]  # fmt: skip
        for mp, counter in league.items()
        if not map_name or mp == map_name.lower()
    }
    return {"team": out_team, "league": out_league}


def _z_diff(h1: int, n1: int, h2: int, n2: int) -> float:
    """Two-proportion z: how many standard errors apart two rates are."""
    if not n1 or not n2:
        return 0.0
    p = (h1 + h2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (h1 / n1 - h2 / n2) / se if se else 0.0


def recent(con: sqlite3.Connection, team_id: str) -> dict:
    series = [
        s for s, in con.execute(
            """SELECT r.series_id FROM rounds r JOIN meta_games g ON g.game_id = r.game_id
               WHERE ? IN (r.attack_team_id, r.defense_team_id)
               GROUP BY r.series_id ORDER BY MIN(g.started_at)""",
            (team_id,),
        )
    ]  # fmt: skip
    if len(series) < RECENT_SERIES + MIN_EARLIER_SERIES:
        return {"enough": False, "recent_series": len(series), "changes": [], "players": []}
    new, old = series[-RECENT_SERIES:], series[:-RECENT_SERIES]
    rounds_new = load_team_rounds(con, team_id, series_ids=new)
    rounds_old = load_team_rounds(con, team_id, series_ids=old)
    c_new, c_old = insights.team_counts(rounds_new), insights.team_counts(rounds_old)

    changes = []
    for key in c_new.keys() & c_old.keys():
        (h1, n1), (h2, n2) = c_new[key], c_old[key]
        if n1 < 10 or n2 < 10:
            continue
        z = _z_diff(h1, n1, h2, n2)
        metric = insights.METRIC_BY_KEY[key]
        better = (z > 0) == metric.higher_is_better
        changes.append({
            "key": key, "label": metric.label, "recent": [h1, n1], "before": [h2, n2],
            "z": z, "changed": abs(z) >= CHANGE_Z, "direction": "better" if better else "worse",
        })  # fmt: skip
    changes.sort(key=lambda c: -abs(c["z"]))

    def map_counts(rs):
        return Counter(
            r.map_name.lower() for r in {(r.game_id, r.map_name): r for r in rs}.values()
        )

    maps_new, maps_old = map_counts(rounds_new), map_counts(rounds_old)

    # players: agents and Operator use, recent vs before
    names = dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())

    def agents(sids):
        marks = ",".join("?" * len(sids))
        out: dict[str, Counter] = defaultdict(Counter)
        for pid, agent in con.execute(
            f"""SELECT r.player_id, lower(r.character_name) FROM meta_rosters r
                WHERE r.team_id = ? AND r.series_id IN ({marks})""",
            (team_id, *sids),
        ):
            out[pid][agent] += 1
        return out

    def op_share(sids):
        marks = ",".join("?" * len(sids))
        return {
            pid: (int(ops or 0), n)
            for pid, ops, n in con.execute(
                f"""SELECT player_id, SUM(has_operator), COUNT(*) FROM loadouts
                    WHERE team_id = ? AND series_id IN ({marks}) GROUP BY player_id""",
                (team_id, *sids),
            )
        }

    a_new, a_old = agents(new), agents(old)
    o_new, o_old = op_share(new), op_share(old)
    players = []
    for pid in sorted(a_new, key=lambda p: names.get(p, p).lower()):
        on, nn = o_new.get(pid, (0, 0))
        oo, no = o_old.get(pid, (0, 0))
        players.append({
            "player_id": pid, "name": names.get(pid, pid), "new_player": pid not in a_old,
            "agents_recent": dict(a_new[pid].most_common()),
            "new_agents": sorted(set(a_new[pid]) - set(a_old.get(pid, {}))),
            "not_lately": sorted(set(a_old.get(pid, {})) - set(a_new[pid])),
            "op_recent": [on, nn], "op_before": [oo, no],
            "op_z": _z_diff(on, nn, oo, no) if nn >= 20 and no >= 20 and on + oo >= 10 else 0.0,
        })  # fmt: skip
    gone = [names.get(p, p) for p in a_old if p not in a_new]

    dates = dict(
        con.execute(
            f"""SELECT r.series_id, MIN(g.started_at) FROM rounds r
                JOIN meta_games g ON g.game_id = r.game_id
                WHERE r.series_id IN ({",".join("?" * len(series))}) GROUP BY r.series_id""",
            series,
        ).fetchall()
    )
    return {
        "enough": True,
        "recent_series": len(new),
        "earlier_series": len(old),
        "recent_from": (dates.get(new[0]) or "")[:10],
        "recent_to": (dates.get(new[-1]) or "")[:10],
        "rounds": [len(rounds_new), len(rounds_old)],
        "changes": changes,
        "maps_recent": dict(maps_new.most_common()),
        "maps_before": dict(maps_old.most_common()),
        "players": players,
        "players_gone": gone,
    }
