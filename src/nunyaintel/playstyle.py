"""Playstyle fingerprint: how fast a team hits, how it opens rounds, and how often it fakes.

On one map (maps differ a lot in pace), for every round the team attacked:
  plant time    seconds from the end of the buy phase to the plant
                fast < 35 s · default 35-70 s · late > 70 s · or no plant
  first contact when the round's first kill happens, and which side got it
  fake          most of their pre-plant site utility went to one site, but they planted
                another (needs 2+ casts near that other site; casts within 20 m of a site count)
and for every round they defended: how often the first fight starts in the first 15 s
(early aggression, or being rushed).

Every number is shown next to the league's on the same map.
"""

from __future__ import annotations

import os
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime

from nunyaintel import insights
from nunyaintel.maps import MapInfo

FAST_S, LATE_S = 35.0, 70.0
EARLY_FIGHT_S = 15.0
SITE_UTILITY_M = 20.0
MIN_FAKE_CASTS = 2
NOTABLE_Z = 1.5  # beyond luck (z vs the league on the map)
MIN_N = 20
_cache: dict[tuple, dict] = {}


def _t(at: str, ref: str) -> float:
    return (datetime.fromisoformat(at) - datetime.fromisoformat(ref)).total_seconds()


def pace(t: float | None) -> str:
    if t is None:
        return "no plant"
    return "fast" if t < FAST_S else "default" if t <= LATE_S else "late"


def _rounds(con: sqlite3.Connection, map_info: MapInfo) -> list[dict]:
    """Every round on the map with plant / first-contact / fake facts (all teams), cached."""
    path = con.execute("PRAGMA database_list").fetchone()[2] or ":memory:"
    key = (path, os.path.getmtime(path) if os.path.exists(path) else 0, map_info.name)
    if key in _cache:
        return _cache[key]
    m = map_info.name
    rounds = {}
    for s, g, n, buy_end, att, dfn, winner in con.execute(
        """SELECT x.series_id, x.game_id, x.round_num, x.buy_ended_at, x.attack_team_id,
                  x.defense_team_id, x.winner_team_id
           FROM rounds x JOIN meta_games g ON g.game_id = x.game_id
           WHERE lower(g.map) = ? AND x.buy_ended_at IS NOT NULL
             AND x.winner_team_id IS NOT NULL AND x.attack_team_id IS NOT NULL""",
        (m,),
    ):
        rounds[(s, g, n)] = {"attack": att, "defense": dfn, "attack_won": winner == att,
                             "buy_end": buy_end, "plant_t": None, "plant_site": None,
                             "first_t": None, "first_by_attack": None,
                             "fake": None}  # fmt: skip

    for s, g, n, at, x, y in con.execute(
        """SELECT o.series_id, o.game_id, o.round_num, MIN(o.occurred_at), o.x, o.y
           FROM objectives o JOIN meta_games g ON g.game_id = o.game_id
           WHERE lower(g.map) = ? AND o.action = 'plantBomb' GROUP BY 1, 2, 3""",
        (m,),
    ):
        r = rounds.get((s, g, n))
        if r and at:
            r["plant_t"] = _t(at, r["buy_end"])
            if x is not None:
                r["plant_site"] = map_info.site_of(x, y, 50.0)

    for s, g, n, at, side in con.execute(
        """SELECT k.series_id, k.game_id, k.round_num, MIN(k.occurred_at), k.killer_side
           FROM kills k JOIN meta_games g ON g.game_id = k.game_id
           WHERE lower(g.map) = ? GROUP BY 1, 2, 3""",
        (m,),
    ):
        r = rounds.get((s, g, n))
        if r and at:
            r["first_t"] = _t(at, r["buy_end"])
            r["first_by_attack"] = side == "attacker"

    # site utility thrown by the attackers before their plant
    casts: dict[tuple, Counter] = defaultdict(Counter)
    for s, g, n, at, cx, cy, gx, gy in con.execute(
        """SELECT a.series_id, a.game_id, a.round_num, a.occurred_at, a.cast_x, a.cast_y,
                  a.grid_x, a.grid_y
           FROM abilities a JOIN meta_games g ON g.game_id = a.game_id
           WHERE lower(g.map) = ? AND a.side = 'attacker'
             AND COALESCE(a.slot, '') != 'PASSIVE'""",
        (m,),
    ):
        r = rounds.get((s, g, n))
        if not r or r["plant_t"] is None or not at:
            continue
        x, y = (cx, cy) if cx is not None else (gx, gy)
        if x is None:
            continue
        t = _t(at, r["buy_end"])
        if 0 <= t <= r["plant_t"]:
            site = map_info.site_of(x, y, SITE_UTILITY_M)
            if site != "unknown":
                casts[(s, g, n)][site] += 1
    for k, r in rounds.items():
        if r["plant_site"] in (None, "unknown"):
            continue
        c = casts.get(k)
        if not c:
            r["fake"] = False
            continue
        other, n_other = max(((s, v) for s, v in c.items() if s != r["plant_site"]),
                             key=lambda sv: sv[1], default=(None, 0))  # fmt: skip
        r["fake"] = n_other >= MIN_FAKE_CASTS and n_other > c.get(r["plant_site"], 0)

    out = list(rounds.values())
    _cache.clear()
    _cache[key] = out
    return out


BIN_S, MAX_S = 5, 110  # plant-time histogram: 5 s bins, the last one is 110 s+


def _hist(times: list[float]) -> list[float]:
    """Share of plants in each 5 s bin (so a team and the league can be drawn together)."""
    bins = [0] * (MAX_S // BIN_S + 1)
    for t in times:
        bins[min(max(int(t // BIN_S), 0), len(bins) - 1)] += 1
    total = sum(bins) or 1
    return [round(b / total, 4) for b in bins]


def _share(rows: list[dict], test) -> list[int]:
    """[hits, n] for a yes/no question over rows (rows where it's undefined are skipped)."""
    vals = [test(r) for r in rows]
    vals = [v for v in vals if v is not None]
    return [sum(vals), len(vals)]


def _summary(rows_att: list[dict], rows_def: list[dict]) -> dict:
    n = len(rows_att)
    paces = Counter(pace(r["plant_t"]) for r in rows_att)
    won = Counter(pace(r["plant_t"]) for r in rows_att if r["attack_won"])
    plants = [r["plant_t"] for r in rows_att if r["plant_t"] is not None]
    firsts = [r["first_t"] for r in rows_att if r["first_t"] is not None]
    fakes = [r for r in rows_att if r["fake"]]
    rates = {
        "fast": [paces["fast"], n],
        "late": [paces["late"], n],
        "no_plant": [paces["no plant"], n],
        "first_kill": _share(rows_att, lambda r: r["first_by_attack"]),
        "fake": _share(rows_att, lambda r: r["fake"]),
        "early_fight": _share(
            rows_def, lambda r: None if r["first_t"] is None else r["first_t"] < EARLY_FIGHT_S
        ),
    }
    return {
        "attack_rounds": n,
        "defense_rounds": len(rows_def),
        "pace": {
            p: {
                "share": paces[p] / n if n else 0,
                "n": paces[p],
                "won": won[p],
                "win_rate": won[p] / paces[p] if paces[p] else None,
            }
            for p in ("fast", "default", "late", "no plant")
        },  # fmt: skip
        "median_plant_s": statistics.median(plants) if plants else None,
        "plant_hist": _hist(plants),
        "median_first_contact_s": statistics.median(firsts) if firsts else None,
        "rates": {
            k: {"hits": h, "n": m, "rate": h / m if m else None} for k, (h, m) in rates.items()
        },
        "fake_win_rate": sum(r["attack_won"] for r in fakes) / len(fakes) if fakes else None,
    }


def fingerprint(con: sqlite3.Connection, team_id: str, map_info: MapInfo) -> dict:
    rows = _rounds(con, map_info)
    team = _summary(
        [r for r in rows if r["attack"] == team_id], [r for r in rows if r["defense"] == team_id]
    )
    league = _summary(rows, rows)  # every round is one team's attack and the other's defense
    # how unusual each rate is (z vs the league on this map, as in Key findings)
    for key, t in team["rates"].items():
        p0 = league["rates"][key]["rate"]
        t["league_rate"] = p0
        t["z"] = insights.z_score(t["hits"], t["n"], p0) if t["n"] and p0 else 0.0
        t["notable"] = abs(t["z"]) >= NOTABLE_Z and t["n"] >= MIN_N
    return {
        "team_id": team_id,
        "map": map_info.name,
        "team": team,
        "league": league,
        "thresholds": {"fast": FAST_S, "late": LATE_S, "early_fight": EARLY_FIGHT_S},
    }
