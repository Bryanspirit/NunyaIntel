import sqlite3

import pytest

from nunyaintel import economy


@pytest.mark.parametrize(
    ("round_num", "value", "expected"),
    [
        (1, 30_000, "pistol"),  # round 1 and 13 are pistol whatever the value
        (13, 0, "pistol"),
        (2, None, "eco"),
        (2, 4_999, "eco"),
        (2, 5_000, "semi-eco"),
        (2, 9_999, "semi-eco"),
        (2, 10_000, "semi-buy"),
        (2, 19_999, "semi-buy"),
        (2, 20_000, "full-buy"),
        (25, 28_000, "full-buy"),  # overtime rounds are classified by value
    ],
)
def test_classify_buy(round_num, value, expected):
    assert economy.classify_buy(round_num, value) == expected


def test_register_makes_function_available_in_sql():
    con = economy.register(sqlite3.connect(":memory:"))
    assert con.execute("SELECT classify_buy(5, 21000)").fetchone()[0] == "full-buy"
