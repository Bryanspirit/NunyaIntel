"""U3 lineup effectiveness tests on a tiny synthetic extract. Never use real hackathon data."""

import sqlite3

import pytest

from nunyaintel.data.extract import SCHEMA
from nunyaintel.utility.effectiveness import format_scores, score_lineups, shrunk_rate
from nunyaintel.utility.lineups import find_lineups
from nunyaintel.utility.placement import UtilityUsage

T0 = "2025-01-01T10:00:{:06.3f}Z"  # T0.format(12.5) -> 2025-01-01T10:00:12.500Z


def _insert(con, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


def test_shrunk_rate():
    assert shrunk_rate(3, 3, 0.25, prior=10) == pytest.approx(5.5 / 13)
    assert shrunk_rate(0, 0, 0.4) == pytest.approx(0.4)  # no data -> baseline
    # lots of data -> close to the raw rate
    assert shrunk_rate(900, 1000, 0.5) == pytest.approx(0.8955, abs=1e-3)


def usage(game, event_id, second, time_s):
    return UtilityUsage(
        series_id=f"s-{game}", game_id=game, map_name="lotus", round_num=1,
        player_id="p1", team_id="A", side="attacker", agent="sova", ability="shock-bolt",
        slot="ABILITY_1", time_s=time_s, x=0.0, y=0.0, z=0.0,
        view_x=1.0, view_y=0.0, view_z=0.0, precise=True, round_won=True,
        event_id=event_id, occurred_at=T0.format(second),
    )  # fmt: skip


@pytest.fixture
def setup():
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute("CREATE TABLE meta_games (game_id TEXT, map TEXT, started_at TEXT)")
    for game in ("g1", "g2", "g3"):
        _insert(con, "meta_games", game_id=game, map="Lotus", started_at="2025-01-01")
        # A attacks in rounds 1-4 and wins only round 1: baseline attack win rate = 25%
        for num, winner in ((1, "A"), (2, "B"), (3, "B"), (4, "B")):
            _insert(con, "rounds", series_id=f"s-{game}", game_id=game, round_num=num,
                    attack_team_id="A", defense_team_id="B", winner_team_id=winner,
                    win_type="opponentEliminated")  # fmt: skip

    lineup_casts = [
        usage("g1", "e1", 10.0, time_s=5.0),  # in round
        usage("g2", "e2", 10.0, time_s=-8.0),  # buy-phase setup: no impact window
        usage("g3", "e3", 10.0, time_s=5.0),
    ]
    for u in lineup_casts:
        _insert(con, "abilities", series_id=u.series_id, game_id=u.game_id, round_num=1,
                occurred_at=u.occurred_at, event_id=u.event_id, player_id="p1",
                team_id="A", ability="shock-bolt")  # fmt: skip
    # a later, non-lineup shock-bolt by the same player in g1: damage after it is NOT ours
    _insert(con, "abilities", series_id="s-g1", game_id="g1", round_num=1,
            occurred_at=T0.format(30.0), event_id="e4", player_id="p1", team_id="A",
            ability="shock-bolt")  # fmt: skip

    def dmg(second, amount):
        _insert(con, "damage", series_id="s-g1", game_id="g1", round_num=1,
                occurred_at=T0.format(second), attacker_id="p1", source="shock-bolt",
                amount=amount)  # fmt: skip

    dmg(11.0, 30)  # after e1 -> credited to the lineup
    dmg(31.0, 50)  # after e4 -> credited to e4, not the lineup

    def kill(second, killer_team, victim_team):
        _insert(con, "kills", series_id="s-g1", game_id="g1", round_num=1,
                occurred_at=T0.format(second), killer_team_id=killer_team,
                victim_team_id=victim_team)  # fmt: skip

    kill(13.0, "A", "B")  # +3 s: our kill, in the window
    kill(15.0, "B", "A")  # +5 s: our death, in the window
    kill(25.0, "A", "B")  # +15 s: outside the 10 s window

    (lineup,) = find_lineups(lineup_casts)
    return con, lineup


def test_score_lineups(setup):
    con, lineup = setup
    (s,) = score_lineups(con, [lineup])
    assert (lineup.rounds, lineup.rounds_won) == (3, 3)
    assert s.baseline == pytest.approx(0.25)
    assert s.adjusted_win_rate == pytest.approx(5.5 / 13)
    assert s.score == pytest.approx(5.5 / 13 - 0.25)
    assert s.ability_damage == 30
    assert s.damage_per_cast == pytest.approx(10.0)
    assert (s.in_round_casts, s.window_kills, s.window_deaths) == (2, 1, 1)
    assert s.net_window_per_cast == 0.0
    assert "shock-bolt" in format_scores([s])


def test_score_lineups_empty(setup):
    con, _ = setup
    assert score_lineups(con, []) == []
