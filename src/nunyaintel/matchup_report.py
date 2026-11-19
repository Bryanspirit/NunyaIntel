"""Matchup report: two teams side by side, and where their habits collide.

Everything here reuses analyses that are already tested and claim-checked: the Elo matchup
(predict), the league-compared metrics (insights), map records (scouting.overview) and site
holds (scouting.sites). This module only lines them up against each other.

"Collisions" pair one team's tendency with the other team's matching tendency, e.g. A's losses
on a full buy against ecos vs. B's eco-upset rate. Each side is shown with its league rate,
and the edge goes to whichever side is further in its own favour (z-scores, as in Key findings).
"""

from __future__ import annotations

import sqlite3

from nunyaintel import insights, predict
from nunyaintel.maps import MapInfo
from nunyaintel.scouting import overview
from nunyaintel.scouting.sites import site_report
from nunyaintel.scouting.team_rounds import load_team_rounds

# (A's metric, B's metric, how to read it). For each metric, insights.METRICS says whether
# higher is better for the team that owns it.
COLLISIONS = [
    ("anti_eco_loss", "eco_upset", "A's full buys vs. B's ecos"),
    ("eco_upset", "anti_eco_loss", "A's ecos vs. B's full buys"),
    ("attack_win", "defense_win", "A attacking vs. B defending"),
    ("defense_win", "attack_win", "A defending vs. B attacking"),
    ("pistol_win", "pistol_win", "Pistol rounds"),
    ("op_duel_win", "op_duel_win", "Operator opening duels"),
]
MIN_MAP_ROUNDS = 20  # a map counts in the pick/ban suggestion only with this many rounds each


def _metric_side(counts: dict, baselines: dict, key: str) -> dict | None:
    if key not in counts:
        return None
    hits, n = counts[key]
    metric = insights.METRIC_BY_KEY[key]
    if n < metric.min_n:
        return {
            "key": key,
            "label": metric.label,
            "hits": hits,
            "n": n,
            "rate": hits / n if n else 0,
            "league_rate": None,
            "z": 0.0,
            "good_z": 0.0,
            "enough": False,
        }
    lh, ln = baselines["league"].get(key, (0, 0))
    p0 = lh / ln if ln else 0.0
    z = insights.z_score(hits, n, p0)
    good = z if metric.higher_is_better else -z  # positive = in this team's favour
    return {
        "key": key,
        "label": metric.label,
        "hits": hits,
        "n": n,
        "rate": hits / n,
        "league_rate": p0,
        "z": z,
        "good_z": good,
        "enough": True,
    }


def _counts(con: sqlite3.Connection, team_id: str, since: str | None) -> dict:
    counts = insights.team_counts(load_team_rounds(con, team_id, since=since))
    duels = insights._op_duel_counts(con, team_id=team_id).get(team_id)
    if duels:
        counts["op_duel_win"] = (duels[0], duels[1])
    return counts


def report(
    con: sqlite3.Connection,
    team_a: str,
    team_b: str,
    map_info: MapInfo | None = None,
    since: str | None = None,
) -> dict:
    baselines = insights.load_baselines(con)
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    ca, cb = _counts(con, team_a, since), _counts(con, team_b, since)

    collisions = []
    for ka, kb, label in COLLISIONS:
        a, b = _metric_side(ca, baselines, ka), _metric_side(cb, baselines, kb)
        if not a or not b:
            continue
        edge = None
        if a["enough"] and b["enough"]:
            diff = a["good_z"] - b["good_z"]
            edge = "a" if diff > 0.5 else "b" if diff < -0.5 else "even"
        collisions.append({"label": label, "a": a, "b": b, "edge": edge})

    # map pool: both teams' records on every map either plays
    rec_a = {
        m.map_name.lower(): m
        for m in overview.map_records(load_team_rounds(con, team_a, since=since))
    }
    rec_b = {
        m.map_name.lower(): m
        for m in overview.map_records(load_team_rounds(con, team_b, since=since))
    }

    def side(rec):
        if rec is None:
            return None
        n = rec.rounds_won + rec.rounds_lost
        return {
            "games": rec.games,
            "games_won": rec.games_won,
            "rounds": n,
            "round_win_rate": rec.round_win_rate,
            "attack": rec.attack.win_rate,
            "defense": rec.defense.win_rate,
        }

    pool = []
    for name in sorted(set(rec_a) | set(rec_b)):
        a, b = side(rec_a.get(name)), side(rec_b.get(name))
        both = a and b and a["rounds"] >= MIN_MAP_ROUNDS and b["rounds"] >= MIN_MAP_ROUNDS
        pool.append(
            {
                "map": name,
                "a": a,
                "b": b,
                "gap": (a["round_win_rate"] - b["round_win_rate"]) if both else None,
            }
        )
    rated = [p for p in pool if p["gap"] is not None]
    pick = max(rated, key=lambda p: p["gap"])["map"] if rated else None
    ban = min(rated, key=lambda p: p["gap"])["map"] if rated else None

    # site battle on the chosen map: A's attack plan vs B's defense, and the reverse
    sites = None
    if map_info is not None:
        ra = load_team_rounds(con, team_a, map_name=map_info.name, since=since)
        rb = load_team_rounds(con, team_b, map_name=map_info.name, since=since)
        if ra and rb:
            rep_a, rep_b = (
                site_report(con, team_a, ra, map_info),
                site_report(con, team_b, rb, map_info),
            )

            def battle(att, att_total, dfn):
                rows = []
                for s in sorted(k for k in att if k not in ("no plant", "unknown")):
                    held = dfn.get(s)
                    rows.append(
                        {
                            "site": s,
                            "attack_share": att[s].rounds.played / max(1, att_total),
                            "attack_win": att[s].rounds.win_rate,
                            "attack_n": att[s].rounds.played,
                            "hold_win": held.rounds.win_rate if held else None,
                            "hold_n": held.rounds.played if held else 0,
                        }
                    )
                return rows

            sites = {
                "a_attacks": battle(rep_a.attack, rep_a.attack_rounds, rep_b.defense),
                "b_attacks": battle(rep_b.attack, rep_b.attack_rounds, rep_a.defense),
            }

    h2h = [
        {
            "game_id": g,
            "date": d[:10],
            "map": m,
            "winner": "a" if w == team_a else "b",
            "score_a": int(s1 if t1 == team_a else s2),
            "score_b": int(s2 if t1 == team_a else s1),
            "first_round": f"{g}:1",
        }
        for g, d, m, w, t1, s1, s2 in con.execute(
            """SELECT game_id, started_at, lower(map), winner_team_id, team1_id, team1_score,
                      team2_score FROM meta_games
               WHERE (team1_id = ? AND team2_id = ?) OR (team1_id = ? AND team2_id = ?)
               ORDER BY started_at DESC""",
            (team_a, team_b, team_b, team_a),
        )
    ]

    return {
        "a": {"id": team_a, "name": names.get(team_a, team_a)},
        "b": {"id": team_b, "name": names.get(team_b, team_b)},
        "elo": predict.matchup(con, team_a, team_b),
        "collisions": collisions,
        "map_pool": pool,
        "pick": pick,
        "ban": ban,
        "sites": sites,
        "head_to_head": h2h,
    }
