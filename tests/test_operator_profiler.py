"""Operator profiler tests on a tiny synthetic extract. Never use real hackathon data in tests."""

import sqlite3

import pytest

from nunyaintel.data.extract import SCHEMA
from nunyaintel.operator_profiler.profiler import (
    OperatorProfile,
    format_table,
    profile_players,
    resolve_team,
)


def _insert(con, table, **row):
    cols = ", ".join(row)
    con.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values())
    )


@pytest.fixture
def con():
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute("CREATE TABLE meta_games (game_id TEXT, map TEXT)")
    con.execute("CREATE TABLE meta_players (player_id TEXT, name TEXT)")
    con.execute("CREATE TABLE meta_teams (team_id TEXT, name TEXT)")
    _insert(con, "meta_games", game_id="g1", map="ascent")
    _insert(con, "meta_players", player_id="op", name="OpGuy")
    _insert(con, "meta_teams", team_id="A", name="Alpha")

    # 4 real rounds (A wins 1, 2, 4) + round 5 with no winner (restarted: must be ignored)
    for n, winner in [(1, "A"), (2, "A"), (3, "B"), (4, "A"), (5, None)]:
        _insert(con, "rounds", series_id="s", game_id="g1", round_num=n, winner_team_id=winner)
    # "op" holds an Operator in rounds 1-3 and 5; "rifler" never does
    for n in (1, 2, 3, 4, 5):
        has_op = int(n != 4)
        _insert(
            con,
            "loadouts",
            series_id="s",
            game_id="g1",
            round_num=n,
            player_id="op",
            team_id="A",
            has_operator=has_op,
        )
        _insert(
            con,
            "loadouts",
            series_id="s",
            game_id="g1",
            round_num=n,
            player_id="rifler",
            team_id="A",
            has_operator=0,
        )

    def kill(n, killer, victim, weapon, first=0):
        _insert(
            con,
            "kills",
            series_id="s",
            game_id="g1",
            round_num=n,
            killer_id=killer,
            victim_id=victim,
            weapon=weapon,
            first_kill=first,
        )

    kill(1, "op", "e1", "operator", first=1)
    kill(1, "op", "e2", "operator")
    kill(2, "op", "e1", "sheriff")  # not an Operator kill
    kill(3, "e1", "op", "vandal")  # died with the Op
    kill(5, "op", "e3", "operator")  # restarted round: ignored
    return con


def test_profile_counts_only_real_rounds(con):
    profiles = {p.player_id: p for p in profile_players(con)}
    p = profiles["op"]
    assert (p.name, p.team_id, p.rounds_played, p.rounds_with_op) == ("OpGuy", "A", 4, 3)
    assert (p.op_kills, p.first_bloods_with_op, p.deaths_with_op) == (2, 1, 1)
    assert p.rounds_won_with_op == 2
    assert p.op_buy_rate == pytest.approx(0.75)
    assert p.kills_per_op_round == pytest.approx(2 / 3)
    assert p.op_kd == 2.0
    assert p.op_round_win_rate == pytest.approx(2 / 3)


def test_min_op_rounds_and_filters(con):
    assert [p.player_id for p in profile_players(con, min_op_rounds=1)] == ["op"]
    assert profile_players(con, map_name="ASCENT", min_op_rounds=1)[0].player_id == "op"
    assert profile_players(con, map_name="bind") == []
    assert profile_players(con, team_id="B") == []


def test_resolve_team(con):
    assert resolve_team(con, "alpha") == "A"
    assert resolve_team(con, "A") == "A"
    with pytest.raises(ValueError):
        resolve_team(con, "nobody")


def test_ratios_handle_zero():
    p = OperatorProfile("x")
    assert (p.op_buy_rate, p.kills_per_op_round, p.op_round_win_rate, p.op_kd) == (0, 0, 0, 0)


def test_format_table(con):
    assert "OpGuy" in format_table(profile_players(con))
