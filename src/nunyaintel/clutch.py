"""Clutches, retakes and post-plant: how a team does when the round gets tight.

Three situations, found by replaying each round's kills and plant (winprob.stories):

  clutch      the first moment in a round the team is down to its last player, against 1-5
              opponents. Who was the last one alive, and did they win the round?
  retake      the team defended and the spike went down while they still had players:
              did they win it back? (per plant site)
  post-plant  the team attacked and planted: did they hold it? (per plant site)

Each one is compared with how often **the league** wins the same situation: same kind, same
numbers (e.g. 1v2), spike down or not, and the same time band (winprob.band). Rare cases
fall back to broader groups, shrunk with K = 10 like the round model:
  (kind, us, them, planted, band) -> (kind, us, them, planted) -> (kind, them) -> kind

Why not the round model's chances? Checked first: summed over the 40 biggest teams, clutches
were won 4,405 times against 3,651 "expected" by the round model. Its 1v2 chance averages
every way a round reaches 1v2, and the first moment a team is down to its last player isn't
an average one. Against the league's own clutch record the gaps add up to about zero.

  won above expected = rounds won - sum of the league's rates for those situations
  beyond luck        when that gap is 1.5+ standard errors (sqrt of sum p(1-p)) and there
                     are at least 10 situations behind it
"""

from __future__ import annotations

import math
import os
import sqlite3
from collections import defaultdict
from collections.abc import Iterator

from nunyaintel import winprob
from nunyaintel.maps import MapInfo
from nunyaintel.scouting.sites import MAX_PLANT_TO_SITE_M

K = 10.0
NOTABLE_Z = 1.5
MIN_N = 10
MIN_PLAYER_CLUTCHES = 3
TOP_PLAYERS = 8
TOP_EXAMPLES = 5

# one situation: (kind, us alive, them alive, planted, time band, step index)
Situation = tuple[str, int, int, int, str | None, int]


def situations(story: winprob.RoundStory, attacking: bool) -> Iterator[Situation]:
    """The clutch and plant moments of one round, seen from one team."""
    in_clutch = planted = False
    for i, ((_, a, d, p, what), band) in enumerate(zip(story.steps, story.bands, strict=True)):
        us, them = (a, d) if attacking else (d, a)
        if not planted and what == "spike planted" and d > 0:
            planted = True
            yield ("post_plant" if attacking else "retake", us, them, 1, band, i)
        if not in_clutch and us == 1 and them >= 1:
            in_clutch = True
            yield ("clutch", us, them, p, band, i)


def _keys(s: Situation) -> list[tuple]:
    kind, us, them, p, band, _ = s
    return [(kind,), (kind, them), (kind, us, them, p), (kind, us, them, p, band)]


class League:
    """How often the league wins each situation, from every round in the data."""

    def __init__(self, stories: list[winprob.RoundStory]):
        self.counts: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        for st in stories:
            for attacking in (True, False):
                won = st.attack_won == attacking
                for s in situations(st, attacking):
                    for key in _keys(s):
                        self.counts[key][0] += won
                        self.counts[key][1] += 1

    def rate(self, s: Situation) -> float:
        p = 0.5
        for key in _keys(s):
            w, n = self.counts.get(key, (0, 0))
            p = (w + K * p) / (n + K)
        return p


_cache: dict[tuple, League] = {}


def league(con: sqlite3.Connection) -> League:
    path = con.execute("PRAGMA database_list").fetchone()[2] or ":memory:"
    key = (path, os.path.getmtime(path) if os.path.exists(path) else id(con))
    if key not in _cache:
        _cache.clear()
        _cache[key] = League(winprob.stories(con))
    return _cache[key]


class _Tally:
    __slots__ = ("n", "won", "expected", "var")

    def __init__(self) -> None:
        self.n = self.won = 0
        self.expected = self.var = 0.0

    def add(self, won: bool, p: float) -> None:
        self.n += 1
        self.won += won
        self.expected += p
        self.var += p * (1 - p)

    def out(self, **extra) -> dict:
        z = (self.won - self.expected) / math.sqrt(self.var) if self.var > 0 else 0.0
        return {
            **extra,
            "n": self.n,
            "won": self.won,
            "expected": round(self.expected, 2),
            "above": round(self.won - self.expected, 2),
            "z": round(z, 2),
            "notable": self.n >= MIN_N and abs(z) >= NOTABLE_Z,
        }


def analyse(con: sqlite3.Connection, team_id: str, map_info: MapInfo | None = None) -> dict:
    """Clutch, retake and post-plant records for one team, on one map or all of them."""
    where = "AND (x.attack_team_id = ? OR x.defense_team_id = ?)"
    params: tuple = (team_id, team_id)
    if map_info is not None:
        where += " AND x.game_id IN (SELECT game_id FROM meta_games WHERE lower(map) = ?)"
        params += (map_info.name,)
    stories = winprob.stories(con, where, params)
    base = league(con)

    roster: dict[tuple, set[str]] = defaultdict(set)
    for s, g, n, p in con.execute(
        f"""SELECT l.series_id, l.game_id, l.round_num, l.player_id
            FROM loadouts l JOIN rounds x USING (series_id, game_id, round_num)
            WHERE l.team_id = ? {where}""",
        (team_id, *params),
    ):
        roster[s, g, n].add(p)
    deaths: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    for s, g, n, at, victim in con.execute(
        f"""SELECT k.series_id, k.game_id, k.round_num, k.occurred_at, k.victim_id
            FROM kills k JOIN rounds x USING (series_id, game_id, round_num)
            WHERE k.victim_team_id = ? AND k.occurred_at IS NOT NULL {where}""",
        (team_id, *params),
    ):
        deaths[s, g, n].append((at, victim))
    maps = dict(con.execute(
        f"""SELECT DISTINCT g.game_id, lower(g.map) FROM meta_games g
            JOIN rounds x ON x.game_id = g.game_id WHERE 1 = 1 {where}""",
        params,
    ).fetchall())  # fmt: skip
    site: dict[tuple, str] = {}
    if map_info is not None:
        for s, g, n, x, y in con.execute(
            f"""SELECT o.series_id, o.game_id, o.round_num, o.x, o.y
                FROM objectives o JOIN rounds x USING (series_id, game_id, round_num)
                WHERE o.action = 'plantBomb' {where} ORDER BY o.occurred_at DESC""",
            params,
        ):
            if x is not None:  # newest first, so the round's first plant is written last
                site[s, g, n] = map_info.site_of(x, y, MAX_PLANT_TO_SITE_M)
    names = dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())

    total: dict[str, _Tally] = defaultdict(_Tally)
    by_vs: dict[int, _Tally] = defaultdict(_Tally)
    by_player: dict[str, _Tally] = defaultdict(_Tally)
    by_site: dict[tuple[str, str], _Tally] = defaultdict(_Tally)
    examples: list[dict] = []

    for st in stories:
        attacking = st.attack_team == team_id
        won = st.attack_won == attacking
        for s in situations(st, attacking):
            kind, _, them, planted, _, i = s
            p = base.rate(s)
            total[kind].add(won, p)
            if kind != "clutch":
                if map_info is not None:
                    by_site[kind, site.get(st.key, "?")].add(won, p)
                continue
            by_vs[them].add(won, p)
            at = st.steps[i][0]
            left = roster.get(st.key, set()) - {v for t, v in deaths.get(st.key, []) if t <= at}
            if len(left) != 1:
                continue  # roster or deaths incomplete for this round: don't guess who
            (player,) = left
            by_player[player].add(won, p)
            if won:
                examples.append({
                    "key": f"{st.key[1]}:{st.key[2]}", "map": maps.get(st.key[1], ""),
                    "player": {"id": player, "name": names.get(player, player)},
                    "vs": them, "p": round(p, 3), "planted": bool(planted),
                })  # fmt: skip

    players = [
        t.out(id=pid, name=names.get(pid, pid))
        for pid, t in by_player.items()
        if t.n >= MIN_PLAYER_CLUTCHES
    ]
    players.sort(key=lambda r: (-r["above"], -r["n"]))

    def sites(kind: str) -> list[dict]:
        known = [
            (k[1], t) for k, t in by_site.items() if k[0] == kind and k[1] not in ("?", "unknown")
        ]
        return [t.out(site=name) for name, t in sorted(known)]

    return {
        "team_id": team_id,
        "map": map_info.name if map_info else None,
        "clutch": {
            **total["clutch"].out(),
            "by_vs": [by_vs[k].out(vs=k) for k in sorted(by_vs)],
            "players": players[:TOP_PLAYERS],
            "best": sorted(examples, key=lambda e: e["p"])[:TOP_EXAMPLES],
        },
        "retake": {**total["retake"].out(), "sites": sites("retake")},
        "post_plant": {**total["post_plant"].out(), "sites": sites("post_plant")},
    }
