"""Clutches, retakes and post-plant: finding the moments and comparing with the league."""

import pytest

from nunyaintel import clutch
from nunyaintel.winprob import RoundStory


def _story(events, attack_won, attack="A"):
    """events: 'a' = an attacker dies, 'd' = a defender dies, 'p' = plant (one second apart)."""
    st = RoundStory(("s", "g", 1), "2026", attack, attack_won, None)
    a, d, planted = 5, 5, 0
    for i, e in enumerate(events):
        if e == "a":
            a -= 1
        elif e == "d":
            d -= 1
        else:
            planted = 1
        what = {"a": "attacker died", "d": "defender died", "p": "spike planted"}[e]
        st.steps.append((f"2026-01-01T00:00:{i:02d}", a, d, planted, what))
        st.bands.append(None)
    return st


def test_situations_from_each_side():
    # attack loses 4 players (1v5), kills one, plants, then defense loses 3 more
    st = _story("aaaadpddd", attack_won=True)
    att = list(clutch.situations(st, attacking=True))
    dfn = list(clutch.situations(st, attacking=False))
    assert [s[:4] for s in att] == [("clutch", 1, 5, 0), ("post_plant", 1, 4, 1)]
    # defense: a retake 4v1 after the plant, then its own clutch once it is down to 1v1
    assert [s[:4] for s in dfn] == [("retake", 4, 1, 1), ("clutch", 1, 1, 1)]
    assert att[0][5] == 3  # the 4th death (step index 3) started the clutch


def test_no_retake_when_no_defender_is_left():
    st = _story("dddddp", attack_won=True)
    assert [s[0] for s in clutch.situations(st, attacking=False)] == ["clutch"]  # no retake


def test_league_rates_shrink_toward_broader_groups():
    won = [_story("aaaa", attack_won=True) for _ in range(30)]  # 1v5 clutches all won
    lost = [_story("daaaa", attack_won=False) for _ in range(30)]  # 1v4 clutches all lost
    lg = clutch.League(won + lost)
    p_1v5 = lg.rate(("clutch", 1, 5, 0, None, 0))
    p_1v4 = lg.rate(("clutch", 1, 4, 0, None, 0))
    assert p_1v5 > 0.8 and p_1v4 < 0.2
    unseen = lg.rate(("clutch", 1, 2, 1, "P0", 0))  # never happened: the clutch average
    assert unseen == pytest.approx(0.5, abs=0.05)


def test_tally_z_and_notable():
    t = clutch._Tally()
    for _ in range(20):
        t.add(True, 0.3)
    out = t.out(site="A")
    assert out["site"] == "A" and out["won"] == 20 and out["expected"] == pytest.approx(6)
    assert out["above"] == pytest.approx(14) and out["z"] > 1.5 and out["notable"]
    few = clutch._Tally()
    for _ in range(5):
        few.add(True, 0.3)
    assert not few.out()["notable"]  # under 10 cases is never called beyond luck
