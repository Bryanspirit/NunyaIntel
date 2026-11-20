"""Match story: one map, round by round, from one team's point of view.

For every round: the score after it, the side, both teams' buys, how it ended, kills on each
side, who drew first blood, where the spike went down, and the round's win-chance range from
the round model (winprob). From that range we tag:
  comeback  won a round after their chance had fallen to 15% or less
  thrown    lost a round after their chance had risen to 85% or more
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from nunyaintel import winprob
from nunyaintel.maps import DEFAULT_PATH, MapInfo, get_map
from nunyaintel.scouting.sites import MAX_PLANT_TO_SITE_M
from nunyaintel.scouting.team_rounds import load_team_rounds

COMEBACK, THROWN = 0.15, 0.85  # big swings only: pro rounds swing a lot


def games(con: sqlite3.Connection, team_id: str, limit: int = 200) -> list[dict]:
    """The team's maps, newest first."""
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    out = []
    for g, d, m, t1, t2, s1, s2, w, event in con.execute(
        """SELECT g.game_id, g.started_at, lower(g.map), g.team1_id, g.team2_id, g.team1_score,
                  g.team2_score, g.winner_team_id, s.event
           FROM meta_games g LEFT JOIN rounds x ON x.game_id = g.game_id AND x.round_num = 1
           LEFT JOIN meta_series s ON s.series_id = x.series_id
           WHERE ? IN (g.team1_id, g.team2_id)
           ORDER BY g.started_at DESC LIMIT ?""",
        (team_id, limit),
    ):
        us_first = t1 == team_id
        opp = t2 if us_first else t1
        out.append({
            "game_id": g, "date": (d or "")[:10], "map": m, "event": event or "",
            "opponent": {"id": opp, "name": names.get(opp, opp)},
            "score_us": int((s1 if us_first else s2) or 0),
            "score_them": int((s2 if us_first else s1) or 0),
            "won": w == team_id,
        })  # fmt: skip
    return out


def story(
    con: sqlite3.Connection, team_id: str, game_id: str, maps_path: Path = DEFAULT_PATH
) -> dict:
    head = con.execute(
        "SELECT lower(map), started_at FROM meta_games WHERE game_id = ?", (game_id,)
    ).fetchone()
    if head is None:
        raise KeyError(game_id)
    map_name, started = head
    rounds = [r for r in load_team_rounds(con, team_id, map_name=map_name) if r.game_id == game_id]
    if not rounds:
        raise KeyError(game_id)
    try:
        map_info: MapInfo | None = get_map(map_name, maps_path)
    except KeyError:  # no callout data for this map: the story works without plant sites
        map_info = None
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    opp = rounds[0].opponent_id
    event = con.execute(
        "SELECT event FROM meta_series WHERE series_id = ?", (rounds[0].series_id,)
    ).fetchone()

    kills: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # round -> [ours, theirs]
    first: dict[int, str] = {}
    for n, killer_team, fk in con.execute(
        "SELECT round_num, killer_team_id, first_kill FROM kills WHERE game_id = ?", (game_id,)
    ):
        kills[n][0 if killer_team == team_id else 1] += 1
        if fk:
            first[n] = "us" if killer_team == team_id else "them"
    plants: dict[int, str] = {}
    for n, x, y in con.execute(
        "SELECT round_num, x, y FROM objectives WHERE game_id = ? AND action = 'plantBomb'",
        (game_id,),
    ):
        on_map = map_info is not None and x is not None
        plants[n] = map_info.site_of(x, y, MAX_PLANT_TO_SITE_M) if on_map else "?"

    # win-chance range per round, from this team's side
    model = winprob.model(con)
    swing: dict[int, tuple[float, float]] = {}
    for st in winprob.stories(con, "AND x.game_id = ?", (game_id,)):
        ours_attack = st.attack_team == team_id
        start = [(*winprob.START_STATE, winprob.START_BAND)]
        ps = [model.p_attack(*s) for s in winprob.moments(st)[:-1] or start]
        ps = ps if ours_attack else [1 - p for p in ps]
        swing[st.key[2]] = (min(ps), max(ps))

    out, us, them = [], 0, 0
    for r in rounds:
        us, them = us + r.won, them + (not r.won)
        lo, hi = swing.get(r.round_num, (0.5, 0.5))
        tag = (
            "comeback"
            if r.won and lo <= COMEBACK
            else "thrown"
            if not r.won and hi >= THROWN
            else ""
        )
        out.append({
            "round": r.round_num, "key": f"{game_id}:{r.round_num}", "side": r.side, "won": r.won,
            "win_type": r.win_type, "own_buy": r.own_buy, "opp_buy": r.opp_buy,
            "score_us": us, "score_them": them, "kills_us": kills[r.round_num][0],
            "kills_them": kills[r.round_num][1], "first_blood": first.get(r.round_num),
            "plant": plants.get(r.round_num), "low": round(lo, 3), "high": round(hi, 3), "tag": tag,
        })  # fmt: skip

    def streak(won: bool) -> int:
        best = cur = 0
        for r in out:
            cur = cur + 1 if r["won"] == won else 0
            best = max(best, cur)
        return best

    def side_rec(side: str) -> list[int]:
        rs = [r for r in out if r["side"] == side]
        return [sum(r["won"] for r in rs), len(rs)]

    firsts = [r for r in out if r["first_blood"]]
    return {
        "game_id": game_id, "map": map_name, "date": (started or "")[:10],
        "event": event[0] if event else "",
        "us": {"id": team_id, "name": names.get(team_id, team_id)},
        "them": {"id": opp, "name": names.get(opp, opp)},
        "score_us": us, "score_them": them, "won": us > them,
        "summary": {
            "attack": side_rec("attacker"), "defense": side_rec("defender"),
            "pistols": [sum(r["won"] for r in out if r["round"] in (1, 13)),
                        sum(1 for r in out if r["round"] in (1, 13))],
            "first_bloods": [sum(r["first_blood"] == "us" for r in firsts), len(firsts)],
            "first_blood_conversion": [
                sum(r["won"] for r in firsts if r["first_blood"] == "us"),
                sum(r["first_blood"] == "us" for r in firsts)],
            "longest_win_streak": streak(True), "longest_loss_streak": streak(False),
            "comebacks": sum(r["tag"] == "comeback" for r in out),
            "thrown": sum(r["tag"] == "thrown" for r in out),
        },
        "rounds": out,
    }  # fmt: skip
