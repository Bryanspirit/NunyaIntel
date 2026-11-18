"""T3 site preferences / setups / opening duels on a tiny synthetic extract. No real data."""

import sqlite3

import pytest

from nunyaintel.data.extract import SCHEMA
from nunyaintel.maps import Callout, MapInfo
from nunyaintel.scouting.sites import (
    default_setups,
    format_sites,
    opening_duels_by_region,
    site_report,
)
from nunyaintel.scouting.team_rounds import load_team_rounds

MAP = MapInfo(
    name="testmap",
    callouts=(
        Callout("A", "Site", 1000, 0),
        Callout("B", "Site", -1000, 0),
        Callout("A", "Main", 2000, 0),
        Callout("Mid", "Courtyard", 0, 0),
    ),
    x_multiplier=0, y_multiplier=0, x_scalar_to_add=0, y_scalar_to_add=0, minimap_url=None,
)  # fmt: skip

BUY_END = "2025-01-01T10:00:{:02d}.000Z"


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
    con.execute("CREATE TABLE meta_players (player_id TEXT, name TEXT)")
    _insert(con, "meta_games", game_id="g", map="Testmap", started_at="2025-01-01")
    _insert(con, "meta_players", player_id="p1", name="Alice")

    # rounds 1-3: A attacks; round 4: A defends. Buy phase ends at second 0 of each minute.
    def rnd(num, attack, defense, winner):
        _insert(con, "rounds", series_id="s", game_id="g", round_num=num,
                buy_ended_at=f"2025-01-01T10:0{num}:00.000Z", attack_team_id=attack,
                defense_team_id=defense, winner_team_id=winner,
                win_type="opponentEliminated")  # fmt: skip
        _insert(con, "loadouts", series_id="s", game_id="g", round_num=num, player_id="p1",
                team_id="A", agent="sova")  # fmt: skip

    rnd(1, "A", "B", "A")
    rnd(2, "A", "B", "B")
    rnd(3, "A", "B", "B")
    rnd(4, "B", "A", "A")

    def plant(num, team, x, second):
        _insert(con, "objectives", series_id="s", game_id="g", round_num=num,
                occurred_at=f"2025-01-01T10:0{num}:{second:02d}.000Z", team_id=team,
                action="plantBomb", x=x, y=0)  # fmt: skip

    plant(1, "A", 900, 40)  # A plants A site, wins
    plant(2, "A", 950, 50)  # A plants A site, loses
    # round 3: no plant
    plant(4, "B", -900, 30)  # B plants B site against A's defense; A retakes

    # p1's positions: round 1 at 5 s in Mid (first), later A Main; round 4 at 30 s (too late)
    _insert(con, "abilities", series_id="s", game_id="g", round_num=1, player_id="p1",
            team_id="A", occurred_at="2025-01-01T10:01:05.000Z", grid_x=50, grid_y=0)  # fmt: skip
    _insert(con, "abilities", series_id="s", game_id="g", round_num=1, player_id="p1",
            team_id="A", occurred_at="2025-01-01T10:01:08.000Z", grid_x=1900, grid_y=0)  # fmt: skip
    _insert(con, "kills", series_id="s", game_id="g", round_num=4, killer_id="p1",
            killer_team_id="A", victim_id="e1", victim_team_id="B", first_kill=1,
            occurred_at="2025-01-01T10:04:30.000Z", killer_x=-900, killer_y=0,
            victim_x=1950, victim_y=0)  # fmt: skip
    return con


def test_site_report(con):
    rounds = load_team_rounds(con, "A")
    rep = site_report(con, "A", rounds, MAP)
    assert (rep.attack_rounds, rep.defense_rounds) == (3, 1)
    a = rep.attack["A"]
    assert (a.rounds.played, a.rounds.won) == (2, 1)
    assert a.median_plant_time_s == pytest.approx(45.0, abs=0.01)
    assert rep.attack["no plant"].rounds.played == 1
    b = rep.defense["B"]
    assert (b.rounds.played, b.rounds.won) == (1, 1)


def test_default_setups(con):
    setups = {s.side: s for s in default_setups(con, "A", load_team_rounds(con, "A"), MAP)}
    att = setups["attacker"]
    assert (att.name, att.agent, att.rounds_played, att.rounds_seen) == ("Alice", "sova", 3, 1)
    assert att.regions == {"Mid Courtyard": 1}  # first position counts, not the later one
    assert setups["defender"].rounds_seen == 0  # only seen at 30 s: outside the 20 s window


def test_opening_duels_by_region(con):
    duels = opening_duels_by_region(con, "A", load_team_rounds(con, "A"), MAP)
    rec = duels["defender"]["A Main"]  # region of the *victim*
    assert (rec.played, rec.won) == (1, 1)


def test_format_sites(con):
    text = format_sites(con, "A", load_team_rounds(con, "A"), MAP)
    assert "Sites on testmap" in text and "Alice" in text
