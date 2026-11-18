"""O3 Operator angle tests on synthetic shots and a tiny extract. Never use real data."""

import sqlite3

import pytest

from nunyaintel.data.extract import SCHEMA
from nunyaintel.maps import Callout, MapInfo
from nunyaintel.operator_profiler.angles import (
    OpShot,
    find_angles,
    format_angles,
    load_op_shots,
    region_angles,
)

MAP = MapInfo(
    name="testmap",
    callouts=(
        Callout("A", "Site", 0, 0),
        Callout("A", "Main", 3000, 0),
        Callout("B", "Site", 0, 5000),
    ),
    x_multiplier=0, y_multiplier=0, x_scalar_to_add=0, y_scalar_to_add=0, minimap_url=None,
)  # fmt: skip


def shot(series, x, y, tx, ty, lethal=True, player="p1"):
    return OpShot(series, f"g-{series}", 1, player, "A", "defender", 20.0, x, y, tx, ty, lethal)


def test_opshot_geometry():
    s = shot("s1", 0, 0, 3000, 4000)
    assert s.distance_m == 50.0
    assert s.direction == pytest.approx((0.6, 0.8))


@pytest.fixture
def shots():
    return [
        # the held angle: from A Site toward A Main, in 3 matches
        shot("s1", 0, 0, 2800, 100),
        shot("s2", 100, 50, 2900, -50),
        shot("s3", -50, 0, 3100, 0, lethal=False),
        # same spot, but shooting toward B Site: a different angle (only once)
        shot("s4", 0, 0, 0, 4800),
    ]


def test_find_angles(shots):
    (angle,) = find_angles(shots, MAP)
    assert (angle.from_region, angle.to_region) == ("A Site", "A Main")
    assert (len(angle.shots), angle.kills, angle.series) == (3, 2, 3)
    assert angle.median_time_s == 20.0


def test_region_angles(shots):
    angles = region_angles(shots, MAP, min_shots=1)
    assert [(a.from_region, a.to_region, len(a.shots)) for a in angles] == [
        ("A Site", "A Main", 3),
        ("A Site", "B Site", 1),
    ]
    assert len(region_angles(shots, MAP)) == 1  # default min_shots=2
    assert "A Site -> A Main" in format_angles(angles, {"p1": "Alice"})


def _insert(con, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


def test_load_op_shots_filters():
    con = sqlite3.connect(":memory:")
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute("CREATE TABLE meta_games (game_id TEXT, map TEXT)")
    _insert(con, "meta_games", game_id="g", map="Testmap")
    _insert(con, "rounds", series_id="s", game_id="g", round_num=1, winner_team_id="A",
            buy_ended_at="2025-01-01T10:00:00.000Z")  # fmt: skip

    def dmg(source, attacker_x, victim_x, team="A", health_after=0):
        _insert(con, "damage", series_id="s", game_id="g", round_num=1,
                occurred_at="2025-01-01T10:00:30.000Z", attacker_id="p1",
                attacker_team_id=team, attacker_side="defender", source=source,
                victim_health_after=health_after, attacker_x=attacker_x, attacker_y=0,
                victim_x=victim_x, victim_y=0)  # fmt: skip

    dmg("operator", 0, 2500)  # 25 m: kept
    dmg("operator", 0, 57300)  # 573 m: impossible, dropped
    dmg("vandal", 0, 2000)  # not an Operator hit
    dmg("operator", 0, 1000, team="B")  # other team
    dmg("operator", 0, 1500, health_after=40)  # non-lethal hit

    shots = load_op_shots(con, "TESTMAP", team_id="A")
    assert [(s.distance_m, s.lethal) for s in shots] == [(25.0, True), (15.0, False)]
    assert shots[0].time_s == pytest.approx(30.0, abs=0.01)
    assert load_op_shots(con, "testmap", side="attacker") == []
