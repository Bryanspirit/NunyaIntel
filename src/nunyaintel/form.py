"""Form over time: how a team's results move from match to match, and how fresh the data is.

Per match (series), in date order: maps won, rounds won (attack / defense), the opponent and
the team's Elo after it. Then a rolling window of the last 5 matches: round win rate with a
"luck band" of +-1 standard error (sqrt(p(1-p)/n)), so a dip inside the band isn't read as a
slump. Elo gives the same story weighted by opponent strength (from ``predict``).

With new data this page tracks current form; with this data it shows when the team was in
form, and how far its last match is from today.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict

from nunyaintel import insights, predict

WINDOW = 5  # matches in the rolling window
CHANGE_Z = 1.5  # last window vs the matches before: called a change at this many SE


def form(con: sqlite3.Connection, team_id: str) -> dict:
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    rows = con.execute(
        """SELECT x.series_id, MIN(g.started_at), s.event,
                  CASE WHEN g.team1_id = ? THEN g.team2_id ELSE g.team1_id END,
                  x.game_id, x.winner_team_id = ?, x.attack_team_id = ?
           FROM rounds x
           JOIN meta_games g ON g.game_id = x.game_id
           LEFT JOIN meta_series s ON s.series_id = x.series_id
           WHERE ? IN (g.team1_id, g.team2_id) AND x.winner_team_id IS NOT NULL
             AND x.attack_team_id IS NOT NULL
           GROUP BY x.series_id, x.game_id, x.round_num""",
        (team_id, team_id, team_id, team_id),
    ).fetchall()
    series: dict[str, dict] = {}
    for sid, started, event, opp, game, won, attacking in rows:
        s = series.setdefault(sid, {
            "series_id": sid, "date": started or "", "event": event or "",
            "opponent": {"id": opp, "name": names.get(opp, opp)},
            "rounds": [0, 0], "attack": [0, 0], "defense": [0, 0],
            "_games": defaultdict(lambda: [0, 0]),
        })  # fmt: skip
        s["date"] = min(s["date"], started or s["date"])
        s["rounds"][0] += won
        s["rounds"][1] += 1
        side = s["attack"] if attacking else s["defense"]
        side[0] += won
        side[1] += 1
        s["_games"][game][0] += won
        s["_games"][game][1] += 1

    elo = predict.elo_ratings(con).get(team_id)
    history = elo.history if elo else []
    out = []
    for s in sorted(series.values(), key=lambda s: s["date"]):
        games = s.pop("_games")
        s["maps"] = [sum(w * 2 > n for w, n in games.values()), len(games)]
        day = s["date"][:10]
        after = [r for d, r in history if d <= day] if history else []
        s["elo"] = after[-1] if after else None  # rating after the last map of that day
        s["date"] = day
        out.append(s)

    rolling = []
    for i in range(len(out)):
        window = out[max(0, i - WINDOW + 1) : i + 1]
        w = sum(s["rounds"][0] for s in window)
        n = sum(s["rounds"][1] for s in window)
        p = w / n if n else 0.0
        rolling.append({
            "date": out[i]["date"], "matches": len(window), "won": w, "rounds": n,
            "rate": p, "se": math.sqrt(p * (1 - p) / n) if n else 0.0,
        })  # fmt: skip

    change = None
    if len(out) > WINDOW + 2:
        last, before = out[-WINDOW:], out[:-WINDOW]
        lw, ln = sum(s["rounds"][0] for s in last), sum(s["rounds"][1] for s in last)
        bw, bn = sum(s["rounds"][0] for s in before), sum(s["rounds"][1] for s in before)
        z = insights.z_score(lw, ln, bw / bn) if bn and 0 < bw < bn else 0.0
        change = {"last": [lw, ln], "before": [bw, bn], "z": round(z, 2),
                  "changed": abs(z) >= CHANGE_Z}  # fmt: skip

    data_end = con.execute("SELECT MAX(started_at) FROM meta_games").fetchone()[0] or ""
    return {
        "team_id": team_id,
        "name": names.get(team_id, team_id),
        "window": WINDOW,
        "matches": out,
        "rolling": rolling,
        "change": change,
        "last_match": out[-1]["date"] if out else None,
        "data_end": data_end[:10],
    }
