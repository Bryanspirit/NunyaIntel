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
    sql = f"""
    WITH player_rounds AS (
        -- one row per player per real round; MAX() collapses any duplicate buy snapshots
        SELECT l.player_id, l.team_id, l.series_id, l.game_id, l.round_num,
               MAX(l.has_operator) AS has_op,
               MAX(r.winner_team_id = l.team_id) AS won
        FROM loadouts l
        JOIN rounds r ON r.series_id = l.series_id AND r.game_id = l.game_id
                     AND r.round_num = l.round_num AND r.winner_team_id IS NOT NULL
        JOIN meta_games g ON g.game_id = l.game_id
        WHERE 1 = 1 {where}
        GROUP BY l.player_id, l.team_id, l.series_id, l.game_id, l.round_num
    ),
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
