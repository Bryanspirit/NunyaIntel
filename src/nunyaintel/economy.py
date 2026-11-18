"""Round economy: classify each team-round by how much the team spent.

Thresholds are on the team's total ``loadout_value`` at the end of the buy phase (all 5
players): the usual eco / half-buy / full-buy split, with cutoffs placed by our data: a dip
around 5-7.5k, a force-buy hump at 7.5-15k, and the big full-buy peak above 20k.

Shared by the Operator profiler (O2) and scouting (T2) so both use identical definitions.
"""

from __future__ import annotations

import sqlite3

PISTOL_ROUNDS = (1, 13)  # first round of each half; everyone starts with 800 credits

ECO_MAX = 5_000  # below this: saving
SEMI_ECO_MAX = 10_000  # cheap guns
SEMI_BUY_MAX = 20_000  # partial / force buy; at or above this is a full buy

# Ordered from poorest to richest, for display
ECONOMY_STATES = ("pistol", "eco", "semi-eco", "semi-buy", "full-buy")


def classify_buy(round_num: int, team_loadout_value: int | None) -> str:
    """Return the economy state of one team in one round."""
    if round_num in PISTOL_ROUNDS:
        return "pistol"
    value = team_loadout_value or 0
    if value < ECO_MAX:
        return "eco"
    if value < SEMI_ECO_MAX:
        return "semi-eco"
    if value < SEMI_BUY_MAX:
        return "semi-buy"
    return "full-buy"


def register(con: sqlite3.Connection) -> sqlite3.Connection:
    """Make ``classify_buy(round_num, team_loadout)`` callable inside SQL on this connection.

    SQLite lets Python register its own functions. That way the thresholds above stay the
    single source of truth, instead of being copied into every query as a CASE expression.

    Registers once per connection: SQLite refuses to add a function while another query on
    the same connection is still open ("Error creating function"), e.g. inside a loop over
    the rows of another query. ``extract.connect()`` registers up front, so later calls are
    no-ops.
    """
    try:  # already there? (asking needs no bookkeeping; connections can't be weak-referenced)
        con.execute("SELECT classify_buy(1, 0)").fetchone()
    except sqlite3.OperationalError:  # "no such function"
        con.create_function("classify_buy", 2, classify_buy, deterministic=True)
    return con
