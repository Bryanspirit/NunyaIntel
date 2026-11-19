"""Predictions (branch predictive-analytics): who wins a map, and what a team buys next round.

Both models were chosen by the feasibility study (docs/predictive-feasibility.md): each is
evaluated on the latest 30% of maps using only earlier ones, against a baseline, and that
evaluation is shown next to every prediction so nobody has to take it on faith.

A. Elo ratings (the chess system): every team starts at 1500. After each map, both ratings move
   by K x (result - expected). Expected = 1 / (1 + 10^((R_opp - R_team) / 400)).
B. Next-round buy: from the whole league, what teams bought after the same situation
   (last buy, won/lost the last round, loss streak), plus the team's own record when it has one.
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from nunyaintel import economy

K = 32.0
START = 1500.0
TEST_FRACTION = 0.3  # evaluation: the latest 30% of maps
MIN_MAPS_TO_RANK = 10
STALE_DAYS = 120  # a rating last updated this long before the data ends is flagged
BUY_STATES = ("eco", "semi-eco", "semi-buy", "full-buy")


def expected(r_team: float, r_opp: float) -> float:
    """Elo's probability that the team wins one map against the opponent."""
    return 1 / (1 + 10 ** ((r_opp - r_team) / 400))


# --- A. Elo ---------------------------------------------------------------------------------


@dataclass(slots=True)
class Rating:
    team_id: str
    rating: float = START
    maps: int = 0
    first_played: str = ""
    last_played: str = ""
    history: list[tuple[str, float]] = field(default_factory=list)  # (date, rating after map)


def _games(con: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    return con.execute(
        "SELECT started_at, team1_id, team2_id, winner_team_id FROM meta_games "
        "WHERE winner_team_id IN (team1_id, team2_id) ORDER BY started_at"
    ).fetchall()


def elo_ratings(con: sqlite3.Connection, k: float = K) -> dict[str, Rating]:
    """Ratings after replaying every map in date order."""
    ratings: dict[str, Rating] = {}
    for started, t1, t2, winner in _games(con):
        a = ratings.setdefault(t1, Rating(t1, first_played=started))
        b = ratings.setdefault(t2, Rating(t2, first_played=started))
        shift = k * ((winner == t1) - expected(a.rating, b.rating))
        a.rating += shift
        b.rating -= shift
        for r in (a, b):
            r.maps += 1
            r.last_played = started
            r.history.append((started[:10], round(r.rating, 1)))
    return ratings


def _components(con: sqlite3.Connection) -> dict[str, str]:
    """team -> representative of its group of teams linked through any chain of games.

    Elo ratings are only comparable inside one group: Game Changers and VCT teams never play
    each other, so their ratings live on separate scales (union-find over the match graph).
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, t1, t2, _ in _games(con):
        parent[find(t1)] = find(t2)
    return {t: find(t) for t in parent}


def evaluate_elo(con: sqlite3.Connection, k: float = K, min_prior: int = 5) -> dict:
    """Score Elo on the latest maps, using only earlier ones (as in the feasibility study)."""
    games = _games(con)
    split = int(len(games) * (1 - TEST_FRACTION))
    rating: dict[str, float] = defaultdict(lambda: START)
    played: Counter[str] = Counter()
    n = hits = 0
    brier = 0.0
    bins: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for i, (_, t1, t2, winner) in enumerate(games):
        p = expected(rating[t1], rating[t2])
        won = winner == t1
        if i >= split and played[t1] >= min_prior and played[t2] >= min_prior:
            n += 1
            hits += (p >= 0.5) == won
            brier += (p - won) ** 2
            fav_p, fav_won = (p, won) if p >= 0.5 else (1 - p, not won)
            b = min(int(fav_p * 10), 9)
            bins[b][0] += fav_won
            bins[b][1] += 1
        shift = k * (won - p)
        rating[t1] += shift
        rating[t2] -= shift
        played[t1] += 1
        played[t2] += 1
    return {
        "test_maps": n,
        "accuracy": hits / n if n else 0.0,
        "brier": brier / n if n else 0.0,
        "baseline_accuracy": 0.5,
        "baseline_brier": 0.25,
        "calibration": [
            {"from": b / 10, "to": (b + 1) / 10, "won": w, "n": m}
            for b, (w, m) in sorted(bins.items())
        ],
    }


def _days_between(a: str, b: str) -> int:
    fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return abs((fmt(b) - fmt(a)).days)


def matchup(con: sqlite3.Connection, team_a: str, team_b: str) -> dict:
    """Map-win probability for team_a vs team_b, with the context needed to trust it."""
    ratings = elo_ratings(con)
    comp = _components(con)
    data_end = con.execute("SELECT MAX(started_at) FROM meta_games").fetchone()[0]
    ranked = sorted(
        (r for r in ratings.values() if r.maps >= MIN_MAPS_TO_RANK), key=lambda r: -r.rating
    )
    rank = {r.team_id: i for i, r in enumerate(ranked, 1)}

    def side(team_id: str) -> dict:
        r = ratings.get(team_id, Rating(team_id))
        return {
            "team_id": team_id,
            "rating": round(r.rating, 1),
            "maps": r.maps,
            "last_played": r.last_played or None,
            "rank": rank.get(team_id),
            "ranked_teams": len(ranked),
            "history": r.history[-60:],
        }

    a, b = side(team_a), side(team_b)
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    for s in (a, b):
        s["name"] = names.get(s["team_id"], s["team_id"])
    warnings = []
    if comp.get(team_a) is None or comp.get(team_a) != comp.get(team_b):
        warnings.append(
            "These teams were never linked by any chain of matches (e.g. VCT vs Game Changers), "
            "so their ratings are on different scales: treat the probability as meaningless."
        )
    for s in (a, b):
        if s["maps"] < MIN_MAPS_TO_RANK:
            warnings.append(f"{s['name']} has only {s['maps']} maps: rating still settling.")
        elif s["last_played"] and _days_between(s["last_played"], data_end) > STALE_DAYS:
            warnings.append(
                f"{s['name']}'s rating is from {s['last_played'][:10]} "
                f"(data ends {data_end[:10]}): it may be out of date."
            )
    h2h = con.execute(
        "SELECT SUM(winner_team_id = ?), COUNT(*) FROM meta_games "
        "WHERE (team1_id = ? AND team2_id = ?) OR (team1_id = ? AND team2_id = ?)",
        (team_a, team_a, team_b, team_b, team_a),
    ).fetchone()
    return {
        "a": a,
        "b": b,
        "p_a_wins_map": expected(a["rating"], b["rating"]),
        "head_to_head": {"a_won": h2h[0] or 0, "maps": h2h[1] or 0},
        "warnings": warnings,
        "model": evaluate_elo(con),
    }


def frequent_opponent(con: sqlite3.Connection, team_id: str) -> str | None:
    row = con.execute(
        """SELECT CASE WHEN team1_id = ? THEN team2_id ELSE team1_id END AS opp, COUNT(*)
           FROM meta_games WHERE ? IN (team1_id, team2_id) GROUP BY opp ORDER BY 2 DESC LIMIT 1""",
        (team_id, team_id),
    ).fetchone()
    return row[0] if row else None


# --- B. next-round buy ----------------------------------------------------------------------


_SEQ_CACHE: dict[str, tuple] = {}


def team_round_sequences(con: sqlite3.Connection):
    """{(game_id, team_id): [(round_num, buy, won), ...]} in round order, plus game dates.
    Cached per extract build (one pass over every loadout takes a second or two)."""
    try:
        built = con.execute("SELECT value FROM build_info WHERE key = 'built_at'").fetchone()
    except sqlite3.OperationalError:  # no build_info (e.g. a hand-made test database)
        built = None
    key = f"{id(con)}:{built[0] if built else ''}"
    if key in _SEQ_CACHE:
        return _SEQ_CACHE[key]
    economy.register(con)
    rows = con.execute(
        """
        WITH team_buy AS (
            SELECT series_id, game_id, round_num, team_id, SUM(lv) AS loadout
            FROM (SELECT series_id, game_id, round_num, team_id, player_id,
                         MAX(loadout_value) AS lv FROM loadouts
                  GROUP BY series_id, game_id, round_num, team_id, player_id)
            GROUP BY series_id, game_id, round_num, team_id
        )
        SELECT r.game_id, b.team_id, r.round_num, classify_buy(r.round_num, b.loadout),
               r.winner_team_id = b.team_id, g.started_at
        FROM rounds r
        JOIN meta_games g ON g.game_id = r.game_id
        JOIN team_buy b ON b.series_id = r.series_id AND b.game_id = r.game_id
                       AND b.round_num = r.round_num
        WHERE r.winner_team_id IS NOT NULL
        ORDER BY r.game_id, b.team_id, r.round_num
        """
    ).fetchall()
    seqs: dict[tuple[str, str], list[tuple[int, str, bool]]] = defaultdict(list)
    dates: dict[str, str] = {}
    for game, team, num, buy, won, started in rows:
        seqs[game, team].append((num, buy, bool(won)))
        dates[game] = started
    _SEQ_CACHE.clear()
    _SEQ_CACHE[key] = (seqs, dates)
    return seqs, dates


def situations(seq):
    """(situation, next buy) pairs. Situation = (last buy, won last round, loss streak cap 3)."""
    streak = 0
    for (num, buy, won), (next_num, next_buy, _) in zip(seq, seq[1:], strict=False):
        streak = 0 if won else streak + 1
        if next_num != num + 1 or next_num in economy.PISTOL_ROUNDS:
            continue  # gaps (restarted rounds) and pistol rounds aren't predictions
        yield (buy, won, min(streak, 3)), next_buy


def evaluate_next_buy(con: sqlite3.Connection) -> dict:
    seqs, dates = team_round_sequences(con)
    ordered = sorted(dates, key=dates.get)
    test = set(ordered[int(len(ordered) * (1 - TEST_FRACTION)) :])
    table: dict[tuple, Counter[str]] = defaultdict(Counter)
    overall: Counter[str] = Counter()
    for (game, _), seq in seqs.items():
        if game not in test:
            for sit, nxt in situations(seq):
                table[sit][nxt] += 1
                overall[nxt] += 1
    majority = overall.most_common(1)[0][0]
    n = hits = base = 0
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (game, _), seq in seqs.items():
        if game in test:
            for sit, nxt in situations(seq):
                guess = table[sit].most_common(1)[0][0] if sit in table else majority
                n += 1
                hits += guess == nxt
                base += majority == nxt
                per_class[nxt][0] += guess == nxt
                per_class[nxt][1] += 1
    return {
        "test_rounds": n,
        "accuracy": hits / n if n else 0.0,
        "baseline": majority,
        "baseline_accuracy": base / n if n else 0.0,
        "per_class": {c: {"right": r, "n": m} for c, (r, m) in per_class.items()},
    }


def next_buy(con: sqlite3.Connection, team_id: str, min_team_n: int = 10) -> dict:
    """For every situation: the league's next-buy distribution, and the team's own if it has
    at least ``min_team_n`` examples (otherwise the league one is the better guess)."""
    seqs, _ = team_round_sequences(con)
    league: dict[tuple, Counter[str]] = defaultdict(Counter)
    team: dict[tuple, Counter[str]] = defaultdict(Counter)
    for (_, tid), seq in seqs.items():
        for sit, nxt in situations(seq):
            league[sit][nxt] += 1
            if tid == team_id:
                team[sit][nxt] += 1

    def dist(c: Counter[str]) -> dict[str, float]:
        total = sum(c.values())
        return {s: c[s] / total for s in BUY_STATES} if total else {}

    rows = []
    for (last, won, streak), counts in sorted(league.items(), key=lambda kv: -sum(kv[1].values())):
        t = team.get((last, won, streak), Counter())
        rows.append(
            {
                "last_buy": last,
                "won_last": won,
                "loss_streak": streak,
                "league": dist(counts),
                "league_n": sum(counts.values()),
                "team": dist(t) if sum(t.values()) >= min_team_n else None,
                "team_n": sum(t.values()),
            }
        )
    return {"team_id": team_id, "situations": rows, "model": evaluate_next_buy(con)}


def log_loss(p: float) -> float:
    return -math.log(max(p, 1e-9))
