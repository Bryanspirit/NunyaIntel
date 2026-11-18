"""U1 utility placement tests on a tiny synthetic extract. Never use real hackathon data."""

import sqlite3

import pytest

from nunyaintel.data.extract import SCHEMA
from nunyaintel.utility.placement import format_summary, load_utility, summarize


def _insert(con, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


def _cast(con, event_id, round_num, at, ability, slot="ABILITY_1", quality="ok", **extra):
    row = dict(
        series_id="s1", game_id="g1", round_num=round_num, occurred_at=at, event_id=event_id,
        player_id="p1", team_id="A", side="defender", ability=ability, slot=slot,
        quality=quality, cast_x=100.0, cast_y=200.0, cast_z=0.0,
        view_x=1.0, view_y=0.0, view_z=0.0,
    )  # fmt: skip
    row.update(extra)
    _insert(con, "abilities", **row)


@pytest.fixture
def con():
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute("CREATE TABLE meta_games (game_id TEXT, map TEXT)")
    con.execute("CREATE TABLE meta_series (series_id TEXT, event TEXT)")
    _insert(con, "meta_games", game_id="g1", map="Ascent")
    _insert(con, "meta_series", series_id="s1", event="VCT Americas - Stage 1 2025")  # 1 Hz

    # round 1: buy phase ends at 10:00:30; A wins. Round 2: restarted, no winner.
    _insert(con, "rounds", series_id="s1", game_id="g1", round_num=1,
            buy_ended_at="2025-01-01T10:00:30.000Z", winner_team_id="A")  # fmt: skip
    _insert(con, "rounds", series_id="s1", game_id="g1", round_num=2,
            buy_ended_at="2025-01-01T10:03:00.000Z", winner_team_id=None)  # fmt: skip
    for n in (1, 2):
        _insert(con, "loadouts", series_id="s1", game_id="g1", round_num=n, player_id="p1",
                team_id="A", agent="cypher")  # fmt: skip

    _cast(con, "e1", 1, "2025-01-01T10:00:20.000Z", "trapwire")  # 10 s before buy end
    _cast(con, "e2", 1, "2025-01-01T10:00:45.000Z", "cyber-cage", slot="ABILITY_2")  # +15 s
    _cast(con, "e3", 1, "2025-01-01T10:00:50.000Z", "cyber-cage", quality="gap_exceeded")
    _cast(con, "e4", 1, "2025-01-01T10:00:55.000Z", "passive-thing", slot="PASSIVE")
    _cast(con, "e5", 2, "2025-01-01T10:03:05.000Z", "trapwire")  # restarted round
    return con


def test_load_utility_filters_and_timing(con):
    usages = load_utility(con, map_name="ascent")
    assert [u.ability for u in usages] == ["trapwire", "cyber-cage"]  # e3, e4, e5 dropped

    trap, cage = usages
    assert trap.time_s == pytest.approx(-10.0, abs=0.01)
    assert trap.in_buy_phase and not cage.in_buy_phase
    assert cage.time_s == pytest.approx(15.0, abs=0.01)
    assert (trap.agent, trap.map_name, trap.side, trap.x, trap.view_x) == (
        "cypher", "Ascent", "defender", 100.0, 1.0,
    )  # fmt: skip
    assert trap.round_won and not trap.precise  # VCT Americas 2025 = 1 Hz


def test_load_utility_options(con):
    assert len(load_utility(con, include_passive=True)) == 3
    assert load_utility(con, precise_only=True) == []
    assert load_utility(con, side="attacker") == []
    assert [u.ability for u in load_utility(con, ability="trapwire")] == ["trapwire"]
    assert load_utility(con, map_name="bind") == []


def test_summarize(con):
    (cage, trap) = sorted(summarize(load_utility(con)), key=lambda s: s.ability)
    assert (trap.agent, trap.casts, trap.rounds, trap.buy_phase_casts) == ("cypher", 1, 1, 1)
    assert trap.per_round == 1.0 and trap.buy_phase_share == 1.0
    assert cage.median_time_s == pytest.approx(15.0, abs=0.01)
    assert "trapwire" in format_summary([trap, cage])
