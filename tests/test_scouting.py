"""T1/T2 scouting tests on hand-made rounds and a tiny synthetic extract. No real data."""

import sqlite3

import pytest

from nunyaintel.data.extract import SCHEMA
from nunyaintel.scouting.economy_report import (
    anti_eco,
    buy_matrix,
    eco_upsets,
    format_economy,
    pistol_stats,
)
from nunyaintel.scouting.overview import format_overview, map_records, side_records, win_types
from nunyaintel.scouting.report import build_report
from nunyaintel.scouting.team_rounds import TeamRound, load_team_rounds


def rnd(game, num, side, won, win_type="opponentEliminated", own="full-buy", opp="full-buy",
        map_name="lotus"):  # fmt: skip
    return TeamRound("s1", game, map_name, "2025-05-01", num, "B", side, won, win_type, own, opp)


@pytest.fixture
def rounds():
    return [
        # game g1 on lotus: we win 3-1
        rnd("g1", 1, "attacker", True, own="pistol", opp="pistol"),
        rnd("g1", 2, "attacker", True, "bombExploded", own="semi-buy", opp="eco"),  # converted
        rnd("g1", 3, "attacker", False, "bombDefused", own="full-buy", opp="semi-eco"),  # anti-eco
        rnd("g1", 13, "defender", True, "bombDefused", own="pistol", opp="pistol"),
        # game g2 on haven: we lose 1-2
        rnd("g2", 1, "defender", False, own="pistol", opp="pistol", map_name="haven"),
        rnd("g2", 2, "defender", True, own="eco", opp="full-buy", map_name="haven"),  # break, upset
        rnd("g2", 3, "defender", False, "bombExploded", map_name="haven"),
    ]  # fmt: skip


def test_map_records(rounds):
    by_name = {m.map_name: m for m in map_records(rounds)}
    lo, ha = by_name["lotus"], by_name["haven"]
    assert (lo.games, lo.games_won, lo.rounds_won, lo.rounds_lost) == (1, 1, 3, 1)
    assert (lo.attack.won, lo.attack.played, lo.defense.won, lo.defense.played) == (2, 3, 1, 1)
    assert (ha.games, ha.games_won) == (1, 0)
    assert ha.round_win_rate == pytest.approx(1 / 3)


def test_side_records_and_win_types(rounds):
    sides = side_records(rounds)
    assert (sides["attacker"].won, sides["attacker"].played) == (2, 3)
    assert (sides["defender"].won, sides["defender"].played) == (2, 4)
    wt = win_types(rounds)
    assert wt["attacker"]["won"] == {"opponentEliminated": 1, "bombExploded": 1}
    assert wt["defender"]["lost"] == {"opponentEliminated": 1, "bombExploded": 1}


def test_pistol_stats(rounds):
    ps = pistol_stats(rounds)
    assert (ps.pistols["attacker"].won, ps.pistols["attacker"].played) == (1, 1)
    assert (ps.pistols["defender"].won, ps.pistols["defender"].played) == (1, 2)
    # pistol wins: g1 r1 (next r2 won) and g1 r13 (no r14 in data -> not counted)
    assert (ps.conversions.won, ps.conversions.played) == (1, 1)
    # pistol loss: g2 r1, next r2 won -> a break
    assert (ps.breaks.won, ps.breaks.played) == (1, 1)


def test_buy_matrix(rounds):
    m = buy_matrix(rounds)
    assert (m["eco", "full-buy"].won, m["eco", "full-buy"].played) == (1, 1)
    up, ae = eco_upsets(m), anti_eco(m)
    assert (up.won, up.played) == (1, 1)
    assert (ae.won, ae.played) == (0, 1)  # the full buy vs semi-eco was lost


def test_formatters(rounds):
    assert "lotus" in format_overview(rounds)
    assert "after a pistol win" in format_economy(rounds)


# --- load_team_rounds against a tiny SQLite extract ---------------------------------------


def _insert(con, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


@pytest.fixture
def con():
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute("CREATE TABLE meta_games (game_id TEXT, map TEXT, started_at TEXT)")
    con.execute("CREATE TABLE meta_teams (team_id TEXT, name TEXT)")
    _insert(con, "meta_games", game_id="g1", map="Lotus", started_at="2025-03-01T10:00:00Z")
    _insert(con, "meta_games", game_id="g2", map="Haven", started_at="2026-02-01T10:00:00Z")
    _insert(con, "meta_teams", team_id="A", name="Alpha")
    for game in ("g1", "g2"):
        for num, winner in ((1, "A"), (2, "B"), (3, None)):  # round 3 restarted: no winner
            _insert(con, "rounds", series_id="s", game_id=game, round_num=num,
                    attack_team_id="A", defense_team_id="B", winner_team_id=winner,
                    win_type="opponentEliminated")  # fmt: skip
            for team, value in (("A", 4_000), ("B", 4_500)):  # 2 players each
                for p in (1, 2):
                    _insert(con, "loadouts", series_id="s", game_id=game, round_num=num,
                            team_id=team, player_id=f"{team}{p}",
                            loadout_value=value if num > 1 else 400)  # fmt: skip
    return con


def test_load_team_rounds(con):
    rows = load_team_rounds(con, "A")
    assert [(r.game_id, r.round_num) for r in rows] == [("g1", 1), ("g1", 2), ("g2", 1), ("g2", 2)]
    r1, r2 = rows[0], rows[1]
    assert (r1.side, r1.won, r1.own_buy, r1.opponent_id) == ("attacker", True, "pistol", "B")
    assert (r2.won, r2.own_buy, r2.opp_buy) == (False, "semi-eco", "semi-eco")  # 8k vs 9k
    # B sees the same rounds from the other side
    assert [r.side for r in load_team_rounds(con, "B")] == ["defender"] * 4
    assert len(load_team_rounds(con, "A", since="2026-01-01")) == 2
    assert len(load_team_rounds(con, "A", map_name="lotus")) == 2


def test_build_report(con):
    report = build_report(con, "A")
    assert report.startswith("SCOUTING REPORT: Alpha")
    assert "2 maps, 4 rounds" in report
    assert "No rounds found" in build_report(con, "A", map_name="bind")
