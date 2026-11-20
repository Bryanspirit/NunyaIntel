"""Next-round buy from money: the credit estimate and the model (synthetic data only)."""

import sqlite3

import pytest

from nunyaintel import nextbuy
from nunyaintel.predict import BUY_STATES


def _db(tmp_path):
    con = sqlite3.connect(tmp_path / "t.sqlite")
    con.executescript(
        """
        CREATE TABLE rounds (series_id, game_id, round_num, started_at, buy_ended_at,
                             attack_team_id, defense_team_id, winner_team_id, win_type);
        CREATE TABLE loadouts (series_id, game_id, round_num, player_id, team_id, side, agent,
                               money, loadout_value, weapons, has_operator);
        CREATE TABLE kills (series_id, game_id, round_num, occurred_at, event_id, killer_id,
                            killer_team_id, killer_side, victim_id, victim_team_id, victim_side,
                            weapon, first_kill, killer_x, killer_y, victim_x, victim_y);
        CREATE TABLE objectives (series_id, game_id, round_num, occurred_at, event_id, player_id,
                                 team_id, side, action, x, y);
        CREATE TABLE meta_games (series_id, game_id, game_number, map, patch, started_at,
                                 finished, winner_team_id, team1_id, team1_name, team1_side,
                                 team1_score, team2_id, team2_name, team2_side, team2_score);
        """
    )
    return con


def _round(con, g, n, winner, money, value, att="A", dfn="D"):
    con.execute(
        "INSERT INTO rounds VALUES ('s', ?, ?, '', '', ?, ?, ?, 'x')", (g, n, att, dfn, winner)
    )
    for team in (att, dfn):
        for i in range(5):
            con.execute(
                "INSERT INTO loadouts VALUES ('s', ?, ?, ?, ?, '', '', ?, ?, '', 0)",
                (g, n, f"{team}{i}", team, money[team], value[team]),
            )


def test_rewards_and_bands():
    assert nextbuy.reward(True, 0) == 3000
    assert [nextbuy.reward(False, k) for k in (1, 2, 3, 7)] == [1900, 2400, 2900, 2900]
    assert nextbuy.band(0) == 0 and nextbuy.band(2499) == 0 and nextbuy.band(2500) == 1
    assert nextbuy.band(10**6) == nextbuy.TOP_BAND


def test_credit_estimate_follows_the_game_rules(tmp_path):
    con = _db(tmp_path)
    con.row_factory = sqlite3.Row  # as the app's connection does (rows aren't plain tuples)
    con.execute("INSERT INTO meta_games (game_id, started_at) VALUES ('g', '2026-01-01')")
    # round 2: A (attack) spends to 4000 each with 500 left and wins; D saves (1000 value, 100 left)
    _round(con, "g", 2, "A", {"A": 500, "D": 100}, {"A": 4000, "D": 1000})
    _round(con, "g", 3, "A", {"A": 0, "D": 0}, {"A": 4500, "D": 4000})
    # A0 kills D0 and D1; D2 kills A4; A plants
    deaths = [("A0", "A", "D0", "D"), ("A0", "A", "D1", "D"), ("D2", "D", "A4", "A")]
    for killer, kteam, victim, vteam in deaths:
        con.execute(
            "INSERT INTO kills (game_id, round_num, killer_id, killer_team_id, victim_id, "
            "victim_team_id) VALUES ('g', 2, ?, ?, ?, ?)",
            (killer, kteam, victim, vteam),
        )
    con.execute("INSERT INTO objectives (game_id, round_num, action) VALUES ('g', 2, 'plantBomb')")
    con.commit()
    turns = {t.team_id: t for t in nextbuy.turns(con)}
    a, d = turns["A"], turns["D"]
    # A: 5 x (500 left + 3000 win + 300 plant) + 2 kills x 200; 4 survivors keep 4000 each
    assert a.credits == 5 * 3800 + 400 and a.kept == 4 * 4000
    # D: lost round 2 after (in this tiny map) no earlier loss: 1900 each; 3 survivors keep 1000
    assert d.credits == 5 * (100 + 1900) + 200 and d.kept == 3 * 1000
    assert (a.won, a.loss_streak, d.won, d.loss_streak) == (True, 0, False, 1)
    assert a.next_buy == "full-buy" and d.next_buy == "full-buy"
    assert a.round_num == 2


def test_credits_cap_at_9000_per_player_and_pistols_overtime_skipped(tmp_path):
    con = _db(tmp_path)
    con.execute("INSERT INTO meta_games (game_id, started_at) VALUES ('g', '2026-01-01')")
    rich = {"A": 8500, "D": 8500}
    for n in (12, 13, 24, 25):
        _round(con, "g", n, "A", rich, {"A": 4000, "D": 4000})
    con.commit()
    turns = nextbuy.turns(con)
    assert {t.round_num for t in turns} == set()  # 13 is a pistol round, 25 is overtime
    con.execute("DELETE FROM rounds WHERE round_num = 25")
    _round(con, "g", 14, "A", rich, {"A": 4000, "D": 4000})
    con.commit()
    nextbuy._cache.clear()
    (t13,) = [t for t in nextbuy.turns(con) if t.team_id == "A"]
    assert t13.round_num == 13 and t13.credits == 5 * 9000


def _turn(credits, kept, nxt, won=False, streak=1, game="g"):
    return nextbuy.Turn(game, "T", 5, "2026", "full-buy", won, streak, credits, kept, nxt, 0)


def test_model_learns_money_and_falls_back_when_rare():
    train = [_turn(5000, 0, "eco") for _ in range(30)]
    train += [_turn(30000, 0, "full-buy") for _ in range(30)]
    m = nextbuy.Model(train)
    poor = m.chances(("full-buy", False, 1), 5000, 0)
    rich = m.chances(("full-buy", False, 1), 30000, 0)
    assert nextbuy.likeliest(poor) == "eco" and nextbuy.likeliest(rich) == "full-buy"
    for p in (poor, rich):
        assert set(p) == set(BUY_STATES) and sum(p.values()) == pytest.approx(1)
    # a situation never seen: falls back to the league mix (half eco, half full buy)
    unseen = m.chances(("eco", True, 0), 15000, 0)
    assert unseen["eco"] == pytest.approx(unseen["full-buy"])
    assert m.support(("full-buy", False, 1), 5000, 0) == (30, 3)  # money-level evidence
    assert m.support(("full-buy", False, 1), 15000, 0) == (60, 1)  # this money: never seen
    assert m.support(("eco", True, 0), 15000, 0) == (60, 0)
