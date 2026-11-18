"""Operator profiler: who buys the Operator, how often, and how much impact they get from it.

Reads the local extract (``nunyaintel build-cache``). Only real rounds are counted: rounds with
a winner whose game is in ``meta_games``, which drops restarted rounds and stray game fragments.

"Rounds with Op" means the player held an Operator at the end of the buy phase. ``op_kills``
counts every Operator kill, including with an Operator picked up mid-round, so a player can have
Op kills in rounds they didn't buy one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from nunyaintel import economy

OPERATOR = "operator"


@dataclass(slots=True)
class OperatorProfile:
    player_id: str
    name: str = ""
    team_id: str = ""
    rounds_played: int = 0
    rounds_with_op: int = 0
    op_kills: int = 0
    first_bloods_with_op: int = 0
    deaths_with_op: int = 0
    rounds_won_with_op: int = 0

    @property
    def op_buy_rate(self) -> float:
        """Share of the player's rounds where they ended the buy phase holding an Operator."""
        return self.rounds_with_op / self.rounds_played if self.rounds_played else 0.0

    @property
    def kills_per_op_round(self) -> float:
        return self.op_kills / self.rounds_with_op if self.rounds_with_op else 0.0

    @property
    def op_kd(self) -> float:
        """Operator kills per death in rounds where the player had an Operator."""
        return self.op_kills / self.deaths_with_op if self.deaths_with_op else float(self.op_kills)

    @property
    def op_round_win_rate(self) -> float:
        return self.rounds_won_with_op / self.rounds_with_op if self.rounds_with_op else 0.0


def _filters(
    team_id: str | None, map_name: str | None, series_ids: Sequence[str] | None
) -> tuple[str, list[str]]:
    clauses, params = [], []
    if team_id:
        clauses.append("l.team_id = ?")
        params.append(team_id)
    if map_name:
        clauses.append("lower(g.map) = lower(?)")
        params.append(map_name)
    if series_ids:
        clauses.append(f"l.series_id IN ({', '.join('?' * len(series_ids))})")
        params.extend(series_ids)
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _player_rounds_cte(where: str) -> str:
    """SQL for the ``player_rounds`` CTE: one row per player per *real* round.

    A CTE (``WITH name AS (...)``) is a named sub-query that later parts of the same query can
    use like a table. Every analysis here starts from this one, so they all count rounds alike.
    Columns: player_id, team_id, series_id, game_id, round_num, has_op, won, economy.
    """
    return f"""
    player_rounds_raw AS (
        -- MAX() collapses any duplicate buy snapshot of the same round into one row
        SELECT l.player_id, l.team_id, l.series_id, l.game_id, l.round_num,
               MAX(l.has_operator) AS has_op,
               MAX(r.winner_team_id = l.team_id) AS won,
               MAX(l.loadout_value) AS loadout_value
        FROM loadouts l
        JOIN rounds r ON r.series_id = l.series_id AND r.game_id = l.game_id
                     AND r.round_num = l.round_num AND r.winner_team_id IS NOT NULL
        JOIN meta_games g ON g.game_id = l.game_id
        WHERE 1 = 1 {where}
        GROUP BY l.player_id, l.team_id, l.series_id, l.game_id, l.round_num
    ),
    player_rounds AS (
        -- SUM(...) OVER (PARTITION BY ...) is a window function: it adds up the loadout of all
        -- teammates in the same round *without* collapsing rows, so each player row gets its
        -- team's total. classify_buy() is our Python function from nunyaintel.economy.
        SELECT *, classify_buy(round_num, SUM(loadout_value) OVER (
                      PARTITION BY series_id, game_id, round_num, team_id)) AS economy
        FROM player_rounds_raw
    )"""


def profile_players(
    con: sqlite3.Connection,
    team_id: str | None = None,
    map_name: str | None = None,
    series_ids: Sequence[str] | None = None,
    min_op_rounds: int = 0,
) -> list[OperatorProfile]:
    """Operator profiles for every player matching the filters, most Operator rounds first.

    ``team_id`` restricts to rounds the player played *for* that team. ``map_name`` matches
    ``meta_games.map`` case-insensitively (e.g. "ascent").
    """
    where, params = _filters(team_id, map_name, series_ids)
    economy.register(con)
    sql = f"""
    WITH {_player_rounds_cte(where)},
    kill_stats AS (
        SELECT pr.player_id, pr.team_id,
               SUM(k.weapon = '{OPERATOR}') AS op_kills,
               SUM(k.weapon = '{OPERATOR}' AND k.first_kill = 1) AS op_first
        FROM player_rounds pr
        JOIN kills k ON k.series_id = pr.series_id AND k.game_id = pr.game_id
                    AND k.round_num = pr.round_num AND k.killer_id = pr.player_id
        GROUP BY pr.player_id, pr.team_id
    ),
    death_stats AS (
        SELECT pr.player_id, pr.team_id, COUNT(*) AS op_deaths
        FROM player_rounds pr
        JOIN kills k ON k.series_id = pr.series_id AND k.game_id = pr.game_id
                    AND k.round_num = pr.round_num AND k.victim_id = pr.player_id
        WHERE pr.has_op = 1
        GROUP BY pr.player_id, pr.team_id
    )
    SELECT pr.player_id, pr.team_id, COALESCE(p.name, pr.player_id) AS name,
           COUNT(*) AS rounds_played,
           SUM(pr.has_op) AS rounds_with_op,
           SUM(pr.has_op AND pr.won) AS rounds_won_with_op,
           COALESCE(ks.op_kills, 0) AS op_kills,
           COALESCE(ks.op_first, 0) AS op_first,
           COALESCE(ds.op_deaths, 0) AS op_deaths
    FROM player_rounds pr
    LEFT JOIN kill_stats ks ON ks.player_id = pr.player_id AND ks.team_id = pr.team_id
    LEFT JOIN death_stats ds ON ds.player_id = pr.player_id AND ds.team_id = pr.team_id
    LEFT JOIN meta_players p ON p.player_id = pr.player_id
    GROUP BY pr.player_id, pr.team_id
    HAVING SUM(pr.has_op) >= ?
    ORDER BY rounds_with_op DESC, op_kills DESC
    """
    rows = con.execute(sql, [*params, min_op_rounds]).fetchall()
    return [
        OperatorProfile(
            player_id=r[0],
            team_id=r[1],
            name=r[2],
            rounds_played=r[3],
            rounds_with_op=r[4],
            rounds_won_with_op=r[5],
            op_kills=r[6],
            first_bloods_with_op=r[7],
            deaths_with_op=r[8],
        )
        for r in rows
    ]


@dataclass(slots=True)
class EconomyOpRate:
    """How often one player holds an Operator in one team economy state."""

    player_id: str
    name: str
    team_id: str
    economy: str
    rounds: int
    rounds_with_op: int

    @property
    def op_rate(self) -> float:
        return self.rounds_with_op / self.rounds if self.rounds else 0.0


def op_rate_by_economy(
    con: sqlite3.Connection,
    team_id: str | None = None,
    map_name: str | None = None,
    series_ids: Sequence[str] | None = None,
    min_op_rounds: int = 0,
) -> list[EconomyOpRate]:
    """Operator rate per player per team economy state (pistol, eco, ..., full-buy).

    Shows *when* a player gets the Op: only on full buys, or also when the team is forcing or
    saving (a "hero Op" on an eco).
    """
    where, params = _filters(team_id, map_name, series_ids)
    economy.register(con)
    sql = f"""
    WITH {_player_rounds_cte(where)},
    eligible AS (
        SELECT player_id, team_id FROM player_rounds
        GROUP BY player_id, team_id HAVING SUM(has_op) >= ?
    )
    SELECT pr.player_id, COALESCE(p.name, pr.player_id), pr.team_id, pr.economy,
           COUNT(*), SUM(pr.has_op)
    FROM player_rounds pr
    JOIN eligible e ON e.player_id = pr.player_id AND e.team_id = pr.team_id
    LEFT JOIN meta_players p ON p.player_id = pr.player_id
    GROUP BY pr.player_id, pr.team_id, pr.economy
    """
    rows = [EconomyOpRate(*r) for r in con.execute(sql, [*params, min_op_rounds])]
    # Sort: players with the most Op rounds first, then economy states poorest -> richest
    totals: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r.player_id, r.team_id)
        totals[key] = totals.get(key, 0) + r.rounds_with_op
    order = {state: i for i, state in enumerate(economy.ECONOMY_STATES)}
    rows.sort(key=lambda r: (-totals[r.player_id, r.team_id], r.player_id, order[r.economy]))
    return rows


@dataclass(slots=True)
class OpeningDuels:
    """Opening duels (the round's first kill) a player was in, with and without an Op."""

    player_id: str
    name: str
    team_id: str
    op_rounds: int
    op_duels: int
    op_duels_won: int
    other_rounds: int
    other_duels: int
    other_duels_won: int

    @property
    def op_duel_rate(self) -> float:
        """Share of Op rounds where the player was in the opening duel (how aggressive)."""
        return self.op_duels / self.op_rounds if self.op_rounds else 0.0

    @property
    def op_duel_win_rate(self) -> float:
        return self.op_duels_won / self.op_duels if self.op_duels else 0.0

    @property
    def other_duel_rate(self) -> float:
        return self.other_duels / self.other_rounds if self.other_rounds else 0.0

    @property
    def other_duel_win_rate(self) -> float:
        return self.other_duels_won / self.other_duels if self.other_duels else 0.0


def opening_duels(
    con: sqlite3.Connection,
    team_id: str | None = None,
    map_name: str | None = None,
    series_ids: Sequence[str] | None = None,
    min_op_rounds: int = 0,
) -> list[OpeningDuels]:
    """Opening-duel involvement and win rate, in rounds with an Op vs. all other rounds.

    A player was "in" the opening duel if they made or suffered the round's first kill
    (``kills.first_kill = 1``; every real round has exactly one, except ~0.1% with no kills).
    """
    where, params = _filters(team_id, map_name, series_ids)
    economy.register(con)
    sql = f"""
    WITH {_player_rounds_cte(where)},
    first_kills AS (
        SELECT series_id, game_id, round_num, killer_id, victim_id
        FROM kills WHERE first_kill = 1
    ),
    duel AS (
        -- LEFT JOIN keeps rounds where the player wasn't in the opening duel (fk.* is NULL)
        SELECT pr.player_id, pr.team_id, pr.has_op,
               fk.killer_id IS NOT NULL AS took,
               COALESCE(fk.killer_id = pr.player_id, 0) AS won
        FROM player_rounds pr
        LEFT JOIN first_kills fk
               ON fk.series_id = pr.series_id AND fk.game_id = pr.game_id
              AND fk.round_num = pr.round_num
              AND pr.player_id IN (fk.killer_id, fk.victim_id)
    )
    SELECT d.player_id, COALESCE(p.name, d.player_id), d.team_id,
           SUM(d.has_op), SUM(d.has_op AND d.took), SUM(d.has_op AND d.won),
           SUM(NOT d.has_op), SUM(NOT d.has_op AND d.took), SUM(NOT d.has_op AND d.won)
    FROM duel d
    LEFT JOIN meta_players p ON p.player_id = d.player_id
    GROUP BY d.player_id, d.team_id
    HAVING SUM(d.has_op) >= ?
    ORDER BY SUM(d.has_op) DESC
    """
    return [OpeningDuels(*r) for r in con.execute(sql, [*params, min_op_rounds])]


def resolve_team(con: sqlite3.Connection, team: str) -> str:
    """Accept a team ID or an exact team name (case-insensitive) and return the team ID."""
    row = con.execute(
        "SELECT team_id FROM meta_teams WHERE team_id = ? OR lower(name) = lower(?) "
        "ORDER BY team_id = ? DESC LIMIT 1",
        (team, team, team),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown team: {team!r}")
    return row[0]


def format_table(profiles: Sequence[OperatorProfile]) -> str:
    header = (
        f"{'player':<16}{'rounds':>7}{'op rnds':>8}{'buy %':>7}{'op K':>6}"
        f"{'K/op rnd':>9}{'op FB':>6}{'op K/D':>7}{'win %':>7}"
    )
    lines = [header, "-" * len(header)]
    for p in profiles:
        lines.append(
            f"{p.name[:15]:<16}{p.rounds_played:>7}{p.rounds_with_op:>8}"
            f"{p.op_buy_rate:>7.0%}{p.op_kills:>6}{p.kills_per_op_round:>9.2f}"
            f"{p.first_bloods_with_op:>6}{p.op_kd:>7.2f}{p.op_round_win_rate:>7.0%}"
        )
    return "\n".join(lines)


def format_economy_table(rates: Sequence[EconomyOpRate]) -> str:
    """One line per player: Op rate in each economy state, with the round count in brackets."""
    by_player: dict[tuple[str, str], dict[str, EconomyOpRate]] = {}
    names: dict[tuple[str, str], str] = {}
    for r in rates:
        by_player.setdefault((r.player_id, r.team_id), {})[r.economy] = r
        names[r.player_id, r.team_id] = r.name
    header = f"{'player':<16}" + "".join(f"{state:>16}" for state in economy.ECONOMY_STATES)
    lines = [header, "-" * len(header)]
    for key, states in by_player.items():
        cells = []
        for state in economy.ECONOMY_STATES:
            r = states.get(state)
            cell = f"{r.op_rate:.0%} ({r.rounds})" if r else "-"
            cells.append(f"{cell:>16}")
        lines.append(f"{names[key][:15]:<16}" + "".join(cells))
    return "\n".join(lines)


def format_duels_table(duels: Sequence[OpeningDuels]) -> str:
    header = (
        f"{'player':<16}{'op rnds':>8}{'op: in duel':>12}{'op: won':>9}"
        f"{'no op: in duel':>15}{'no op: won':>11}"
    )
    lines = [header, "-" * len(header)]
    for d in duels:
        lines.append(
            f"{d.name[:15]:<16}{d.op_rounds:>8}{d.op_duel_rate:>12.0%}{d.op_duel_win_rate:>9.0%}"
            f"{d.other_duel_rate:>15.0%}{d.other_duel_win_rate:>11.0%}"
        )
    return "\n".join(lines)
