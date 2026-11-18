"""U2 lineup clustering tests on synthetic casts. Never use real hackathon data."""

import pytest

from nunyaintel.utility.lineups import NOISE, dbscan, find_lineups, format_lineups
from nunyaintel.utility.placement import UtilityUsage


def cast(series, rnd, x, y, view=(1.0, 0.0, 0.0), ability="toxic-screen", won=True, t=5.0):
    return UtilityUsage(
        series_id=series, game_id=f"g-{series}", map_name="Ascent", round_num=rnd,
        player_id="p1", team_id="A", side="attacker", agent="viper", ability=ability,
        slot="ABILITY_2", time_s=t, x=x, y=y, z=0.0,
        view_x=view[0], view_y=view[1], view_z=view[2], precise=True, round_won=won,
    )  # fmt: skip


def test_dbscan_on_a_line():
    points = [0, 1, 2, 10, 11, 12, 50]  # two tight groups + one outlier

    def near(i, j):
        return abs(points[i] - points[j]) <= 1

    labels = dbscan(len(points), near, min_samples=2)
    assert labels[0] == labels[1] == labels[2] != labels[3] == labels[4] == labels[5]
    assert labels[6] == NOISE


def test_find_lineups():
    casts = [
        # the lineup: same spot (+-50 cm), same aim, in 3 different matches
        cast("s1", 1, 1000, 2000, won=True, t=4),
        cast("s1", 5, 1040, 2010, won=False, t=6),
        cast("s2", 3, 990, 1980, won=True, t=5),
        cast("s3", 2, 1020, 2030, won=True, t=5),
        # same spot but aimed 90 degrees away: a different throw, not part of the lineup
        cast("s4", 1, 1000, 2000, view=(0.0, 1.0, 0.0)),
        # a repeated spot, but only ever in one match: not a habit
        cast("s5", 1, 5000, 5000),
        cast("s5", 2, 5010, 5000),
        cast("s5", 3, 5000, 5010),
    ]
    (lineup,) = find_lineups(casts)
    assert (lineup.agent, lineup.ability, lineup.side) == ("viper", "toxic-screen", "attacker")
    assert (lineup.casts, lineup.series, lineup.rounds, lineup.rounds_won) == (4, 3, 4, 3)
    assert lineup.round_win_rate == 0.75
    assert lineup.x == pytest.approx(1012.5)
    assert lineup.median_time_s == 5.0
    assert lineup.yaw_deg == pytest.approx(0.0)

    # with min_series=1, the single-match habit appears too
    assert len(find_lineups(casts, min_series=1)) == 2


def test_different_abilities_never_merge():
    casts = [cast(f"s{i}", 1, 0, 0, ability="toxic-screen") for i in range(3)]
    casts += [cast(f"s{i}", 2, 0, 0, ability="poison-cloud") for i in range(3)]
    assert sorted(lu.ability for lu in find_lineups(casts)) == ["poison-cloud", "toxic-screen"]


def test_format_lineups():
    casts = [cast(f"s{i}", 1, 0, 0) for i in range(3)]
    assert "toxic-screen" in format_lineups(find_lineups(casts))
