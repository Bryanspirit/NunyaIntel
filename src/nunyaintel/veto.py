"""Map veto simulator: a best-of-3 veto played out, with honest series odds.

Two questions, answered separately:

1. Which maps would each team ban and pick? From their map records: each team's round win rate
   on a map, shrunk toward its overall rate (PRIOR_ROUNDS), so one 13-2 doesn't decide a pick.
   A team bans the map where it's furthest behind the other and picks where it's furthest ahead.
   VCT best-of-3 order: A ban, B ban, A pick, B pick, A ban, B ban, last map = decider.

2. Who wins the series? We tested per-map strength (Elo plus a per-team-per-map offset, learned
   from map wins or from round shares, tuned on earlier maps) on the latest 30% of maps: it was
   *worse* than plain Elo on unseen matches (see evaluate()). So the series odds use overall
   Elo for every map, and the best-of-3 formula
       P(series) = p1*p2 + p1*(1-p2)*p3 + (1-p1)*p2*p3
   which, with the same p on each map, favours the stronger team more than a single map does.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from nunyaintel.predict import START, TEST_FRACTION, K, expected

K_MAP_CHOICES = (0.0, 4.0, 8.0, 12.0, 16.0, 24.0)
POOL_SIZE = 7
POOL_DAYS = 120  # the active map pool = the most-played maps in the data's last 120 days
PRIOR_ROUNDS = 60  # map round win rates are shrunk toward the team's overall rate
STEPS = [("a", "ban"), ("b", "ban"), ("a", "pick"), ("b", "pick"), ("a", "ban"), ("b", "ban")]


def _games(con: sqlite3.Connection) -> list[tuple[str, str, str, str, str]]:
    return con.execute(
        "SELECT started_at, lower(map), team1_id, team2_id, winner_team_id FROM meta_games "
        "WHERE winner_team_id IN (team1_id, team2_id) ORDER BY started_at"
    ).fetchall()


def _replay(games, k_map: float, score_from: int | None = None, min_prior: int = 5):
    """Replay maps in order. Returns (ratings, offsets, played, scored [(p, won)])."""
    rating: dict[str, float] = defaultdict(lambda: START)
    offset: dict[tuple[str, str], float] = defaultdict(float)
    played: Counter[str] = Counter()
    scored = []
    for i, (_, mp, t1, t2, winner) in enumerate(games):
        p = expected(rating[t1] + offset[(t1, mp)], rating[t2] + offset[(t2, mp)])
        won = winner == t1
        if score_from is not None and i >= score_from and min(played[t1], played[t2]) >= min_prior:
            scored.append((p, won))
        err = won - p
        rating[t1] += K * err
        rating[t2] -= K * err
        offset[(t1, mp)] += k_map * err
        offset[(t2, mp)] -= k_map * err
        played[t1] += 1
        played[t2] += 1
    return rating, offset, played, scored


def _brier(scored) -> float:
    return sum((p - w) ** 2 for p, w in scored) / len(scored) if scored else 0.0


def evaluate(con: sqlite3.Connection) -> dict:
    """Choose K_MAP on the earlier maps, then score it and plain Elo on the latest 30%."""
    games = _games(con)
    split = int(len(games) * (1 - TEST_FRACTION))
    train = games[:split]
    # tune on the last 30% of the *training* part, so the test maps are never looked at
    tune_from = int(len(train) * (1 - TEST_FRACTION))
    tuning = {k: _brier(_replay(train, k, tune_from)[3]) for k in K_MAP_CHOICES}
    best = min(tuning, key=tuning.get)
    test_plain = _replay(games, 0.0, split)[3]
    test_map = _replay(games, best, split)[3]

    def acc(s):
        return sum((p >= 0.5) == w for p, w in s) / len(s) if s else 0.0

    return {
        "k_map": best,
        "tuning_brier": tuning,
        "test_maps": len(test_map),
        "brier": _brier(test_map),
        "accuracy": acc(test_map),
        "plain_elo_brier": _brier(test_plain),
        "plain_elo_accuracy": acc(test_plain),
    }


def map_pool(con: sqlite3.Connection) -> list[str]:
    end = con.execute("SELECT MAX(started_at) FROM meta_games").fetchone()[0]
    since = (datetime.fromisoformat(end) - timedelta(days=POOL_DAYS)).isoformat()
    rows = con.execute(
        "SELECT lower(map), COUNT(*) FROM meta_games WHERE started_at >= ? GROUP BY 1 "
        "ORDER BY 2 DESC LIMIT ?",
        (since, POOL_SIZE),
    ).fetchall()
    return sorted(m for m, _ in rows)


def series_chance(p: list[float]) -> float:
    """Best-of-3 from three map chances, in the order they'd be played."""
    p1, p2, p3 = p
    return p1 * p2 + p1 * (1 - p2) * p3 + (1 - p1) * p2 * p3


def _map_rates(con: sqlite3.Connection, team_id: str) -> tuple[dict[str, tuple], float]:
    """Round wins / rounds per map, and the team's overall round win rate."""
    rows = con.execute(
        """SELECT lower(g.map), SUM(r.winner_team_id = :t), COUNT(*) FROM rounds r
           JOIN meta_games g ON g.game_id = r.game_id
           WHERE :t IN (r.attack_team_id, r.defense_team_id) AND r.winner_team_id IS NOT NULL
           GROUP BY 1""",
        {"t": team_id},
    ).fetchall()
    per = {m: (int(w), int(n)) for m, w, n in rows}
    won = sum(w for w, _ in per.values())
    total = sum(n for _, n in per.values())
    return per, (won / total if total else 0.5)


def simulate(con: sqlite3.Connection, team_a: str, team_b: str) -> dict:
    ev = evaluate(con)
    rating = _replay(_games(con), 0.0)[0]
    p_map = expected(rating[team_a], rating[team_b])
    pool = map_pool(con)
    rates_a, base_a = _map_rates(con, team_a)
    rates_b, base_b = _map_rates(con, team_b)

    def shrunk(per, base, m):
        w, n = per.get(m, (0, 0))
        return (w + PRIOR_ROUNDS * base) / (n + PRIOR_ROUNDS), n

    table = {}
    for m in pool:
        ra, na = shrunk(rates_a, base_a, m)
        rb, nb = shrunk(rates_b, base_b, m)
        # how much better than usual each team is here: the veto compares these
        table[m] = {"map": m, "a_rate": ra, "a_rounds": na, "b_rate": rb, "b_rounds": nb,
                    "edge_a": (ra - base_a) - (rb - base_b)}  # fmt: skip

    left = list(pool)
    steps = []
    picks: list[str] = []
    for who, action in STEPS:
        if len(left) <= 1:  # a small pool (few maps in the data): stop, keep a decider
            break
        mine = (lambda m: table[m]["edge_a"]) if who == "a" else (lambda m: -table[m]["edge_a"])
        choice = (min if action == "ban" else max)(left, key=mine)
        left.remove(choice)
        steps.append(
            {"team": who, "action": action, "map": choice, "edge_a": table[choice]["edge_a"]}
        )
        if action == "pick":
            picks.append(choice)
    decider = left[0] if left else None
    names = dict(con.execute("SELECT team_id, name FROM meta_teams").fetchall())
    return {
        "a": {"id": team_a, "name": names.get(team_a, team_a), "rating": rating[team_a]},
        "b": {"id": team_b, "name": names.get(team_b, team_b), "rating": rating[team_b]},
        "pool": [table[m] for m in pool],
        "steps": steps,
        "decider": decider,
        "order": [*picks, *([decider] if decider else [])],
        "p_map": p_map,
        "series_p_a": series_chance([p_map] * 3),
        "model": ev,
    }
