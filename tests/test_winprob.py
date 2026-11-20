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
    for i, (attack_won, events, *start) in enumerate(rounds):
        first = start[0] if start else 10  # seconds after the buy phase of the first event
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
            secs = first + k
            at = f"2025-01-01T10:{secs // 60:02d}:{secs % 60:02d}Z"
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


def test_time_bands():
    assert winprob.band(0, None) == "R0" and winprob.band(45, None) == "R2"
    assert winprob.band(500, None) == "R4" and winprob.band(-3, None) == "R0"
    assert winprob.band(70, 5) == "P0" and winprob.band(70, 35) == "P3"  # after the plant
    assert winprob.band(None, None) is None


def test_moments_carry_the_band_each_state_began_in():
    con = _db([(True, ["D", "A", "P", "D"])])  # events 1 s apart, 10 s after the buy phase
    (story,) = winprob.stories(con)
    assert winprob.moments(story) == [
        (5, 5, 0, "R0"), (5, 4, 0, "R0"), (4, 4, 0, "R0"), (4, 4, 1, "P0"), (4, 3, 1, "P0"),
    ]  # fmt: skip
    assert [m[:3] for m in winprob.moments(story)] == winprob.visited(story)


def test_time_band_refines_but_falls_back_when_unseen():
    # the same 5 v 4 early (10 s: attack wins 9 of 10) and late (85 s: attack wins 1 of 10)
    rounds = [(i < 9, ["D"], 10) for i in range(10)] + [(i < 1, ["D"], 85) for i in range(10)]
    m = winprob.Model(winprob.stories(_db(rounds)))
    timeless = m.p_attack(5, 4, 0)
    assert m.p_attack(5, 4, 0, "R0") > timeless > m.p_attack(5, 4, 0, "R4")
    assert m.p_attack(5, 4, 0, "R2") == timeless  # never seen at 40-60 s: same as no time
