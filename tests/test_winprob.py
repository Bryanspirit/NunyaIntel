"""Round win-chance model on a tiny synthetic database (no real data)."""

import sqlite3

import pytest

from nunyaintel import winprob
from nunyaintel.data.extract import SCHEMA


def _db(rounds):
    """rounds: list of (attack_won, [events]) where an event is 'A' (attacker died),
    'D' (defender died) or 'P' (spike planted), in order."""
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute("CREATE TABLE meta_games (game_id TEXT, map TEXT, started_at TEXT)")
    for i, (attack_won, events) in enumerate(rounds):
        game = f"g{i:03d}"
        con.execute(
            "INSERT INTO meta_games VALUES (?, 'testmap', ?)", (game, f"2025-01-01T{i % 24:02d}:00")
        )
        con.execute(
            "INSERT INTO rounds (series_id, game_id, round_num, buy_ended_at, attack_team_id, "
            "defense_team_id, winner_team_id) VALUES ('s', ?, 1, '2025-01-01T10:00:00Z', 'A', 'B', ?)",  # noqa: E501
            (game, "A" if attack_won else "B"),
        )
        for k, e in enumerate(events):
            at = f"2025-01-01T10:00:{10 + k:02d}Z"
            if e == "P":
                con.execute(
                    "INSERT INTO objectives (series_id, game_id, round_num, occurred_at, action) "
                    "VALUES ('s', ?, 1, ?, 'plantBomb')",
                    (game, at),
                )
            else:
                con.execute(
                    "INSERT INTO kills (series_id, game_id, round_num, occurred_at, victim_side) "
                    "VALUES ('s', ?, 1, ?, ?)",
                    (game, at, "attacker" if e == "A" else "defender"),
                )
    return con


def test_stories_track_players_alive_and_the_plant():
    con = _db([(True, ["D", "A", "P", "D", "D", "D", "D", "D"])])  # 6 defender deaths: a revive
    (story,) = winprob.stories(con)
    assert story.attack_won
    states = winprob.visited(story)
    assert states[:4] == [(5, 5, 0), (5, 4, 0), (4, 4, 0), (4, 4, 1)]
    assert states[-1] == (4, 0, 1)  # alive counts stop at 0


def test_first_kill_moves_the_chance_and_shrinkage_keeps_rare_states_sane():
    # attack wins 8 of 10 rounds after getting the first kill, 2 of 10 after losing it
    rounds = [(i < 8, ["D"]) for i in range(10)] + [(i < 2, ["A"]) for i in range(10)]
    m = winprob.Model(winprob.stories(_db(rounds)))
    start = m.p_attack(5, 5, 0)
    assert start == pytest.approx(0.5)
    assert m.p_attack(5, 4, 0) > 0.6 > 0.4 > m.p_attack(4, 5, 0)
    assert m.p_attack(5, 4, 0) < 0.8  # 10 rounds: pulled part of the way back toward 50%
    assert m.p_attack(2, 4, 1) == pytest.approx(0.5)  # never seen: falls back to broader groups
    assert m.p_attack(0, 3, 0) == 0.0 and m.p_attack(3, 0, 0) == 1.0  # decided states
    assert m.p_attack(0, 3, 1) < 1.0  # spike down with no attackers: defenders can still defuse


def test_grid_covers_every_state():
    m = winprob.Model(winprob.stories(_db([(True, ["D"]), (False, ["A"])])))
    grid = m.grid(0)
    assert len(grid) == 36 and {(c["a"], c["d"]) for c in grid} == {
        (a, d) for a in range(6) for d in range(6)
    }
    assert all(0.0 <= c["p"] <= 1.0 for c in grid)


def test_evaluate_scores_only_later_maps():
    rounds = [(i % 3 != 0, ["D"] if i % 3 else ["A"]) for i in range(30)]
    e = winprob.evaluate(_db(rounds))
    assert e["train_rounds"] == 21 and e["test_rounds"] == 9
    assert e["test_states"] == 9  # the final state is the result itself, so only 5 v 5 is scored
    assert 0.0 <= e["brier"] <= 1.0 and sum(b["n"] for b in e["calibration"]) == 9
