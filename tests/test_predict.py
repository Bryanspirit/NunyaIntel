"""Predictions (Elo matchups, next-round buy) on tiny synthetic data. No real data."""

import sqlite3

import pytest

from nunyaintel import predict
from nunyaintel.data.extract import SCHEMA


def test_expected_is_symmetric_and_fair():
    assert predict.expected(1500, 1500) == pytest.approx(0.5)
    assert predict.expected(1600, 1400) == pytest.approx(1 - predict.expected(1400, 1600))
    assert predict.expected(1900, 1500) == pytest.approx(10 / 11)  # 400 points = 10:1 odds


def _insert(con, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


@pytest.fixture
def con():
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute(
        "CREATE TABLE meta_games (game_id TEXT, started_at TEXT, map TEXT, "
        "team1_id TEXT, team2_id TEXT, winner_team_id TEXT)"
    )
    con.execute("CREATE TABLE meta_teams (team_id TEXT, name TEXT)")
    for tid, name in (("A", "Alpha"), ("B", "Bravo"), ("X", "Xray"), ("Y", "Yankee")):
        _insert(con, "meta_teams", team_id=tid, name=name)
    # A beats B in 12 maps; X and Y only ever play each other (a separate circuit)
    for i in range(12):
        _insert(con, "meta_games", game_id=f"ab{i}", started_at=f"2025-01-{i + 1:02d}T00:00:00Z",
                map="lotus", team1_id="A", team2_id="B", winner_team_id="A")  # fmt: skip
    for i in range(3):
        _insert(con, "meta_games", game_id=f"xy{i}", started_at=f"2025-06-{i + 1:02d}T00:00:00Z",
                map="lotus", team1_id="X", team2_id="Y", winner_team_id="Y")  # fmt: skip
    return con


def test_elo_ratings_move_toward_results(con):
    r = predict.elo_ratings(con)
    assert r["A"].rating > 1500 > r["B"].rating
    assert r["A"].rating + r["B"].rating == pytest.approx(3000)  # Elo is zero-sum
    assert (r["A"].maps, r["A"].last_played[:10]) == (12, "2025-01-12")
    assert len(r["A"].history) == 12


def test_matchup_and_warnings(con):
    m = predict.matchup(con, "A", "B")
    assert m["p_a_wins_map"] > 0.5
    assert m["head_to_head"] == {"a_won": 12, "maps": 12}
    assert (m["a"]["name"], m["a"]["rank"]) == ("Alpha", 1)
    # A last played in January; the data ends in June: flagged as possibly stale
    assert any("Alpha's rating is from 2025-01-12" in w for w in m["warnings"])
    # different circuits: never linked by any chain of matches
    x = predict.matchup(con, "A", "X")
    assert any("never linked" in w for w in x["warnings"])
    # few maps: rating still settling
    assert any("Xray has only 3 maps" in w for w in x["warnings"])


def test_frequent_opponent(con):
    assert predict.frequent_opponent(con, "A") == "B"
    assert predict.frequent_opponent(con, "nobody") is None


def test_situations_skip_pistols_and_gaps():
    seq = [
        (1, "pistol", False),  # lost pistol
        (2, "eco", False),  # lost again: streak 2
        (3, "full-buy", True),
        (5, "full-buy", True),  # gap: round 4 missing (restarted) -> no prediction for 5
        (12, "full-buy", False),
        (13, "pistol", True),  # pistol round: never predicted
        (14, "full-buy", True),
    ]
    pairs = list(predict.situations(seq))
    assert pairs == [
        (("pistol", False, 1), "eco"),
        (("eco", False, 2), "full-buy"),
        (("pistol", True, 0), "full-buy"),
    ]
