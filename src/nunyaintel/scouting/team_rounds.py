"""One row per real round, seen from one team's point of view: the input for all scouting.

Each ``TeamRound`` says which map and side the team played, whether they won, how the round
ended, and both teams' buy type (pistol / eco / semi-eco / semi-buy / full-buy, from
``nunyaintel.economy``).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from nunyaintel import economy


@dataclass(frozen=True, slots=True)
class TeamRound:
    series_id: str
    game_id: str
    map_name: str
    game_started_at: str
    round_num: int
    opponent_id: str
    side: str  # "attacker" | "defender"
    won: bool
    win_type: str  # opponentEliminated | bombExploded | bombDefused | timeExpired
    own_buy: str
    opp_buy: str


def load_team_rounds(
    con: sqlite3.Connection,
    team_id: str,
    map_name: str | None = None,
    since: str | None = None,
    series_ids: Sequence[str] | None = None,
) -> list[TeamRound]:
    """All real rounds the team played, oldest first. ``since`` is an ISO date, e.g. 2026-01-01."""
    economy.register(con)
    # Named parameters (:team, :map, ...) can be used several times in one query, which we need:
    # the same filter appears in the team_games CTE and in the main WHERE.
    params: dict[str, Any] = {"team": team_id}
    clauses = ["r.winner_team_id IS NOT NULL", ":team IN (r.attack_team_id, r.defense_team_id)"]
    if map_name:
        clauses.append("lower(g.map) = lower(:map)")
        params["map"] = map_name
    if since:
        clauses.append("g.started_at >= :since")
        params["since"] = since
    if series_ids:
        names = [f"s{i}" for i in range(len(series_ids))]
        clauses.append(f"r.series_id IN ({', '.join(':' + n for n in names)})")
        params.update(zip(names, series_ids, strict=True))
    where = " AND ".join(clauses)

    sql = f"""
    WITH team_games AS (
        SELECT DISTINCT r.game_id
        FROM rounds r JOIN meta_games g ON g.game_id = r.game_id
        WHERE {where}
    ),
    team_buy AS (
        -- team loadout per round = sum over its players (MAX() drops duplicate snapshots)
        SELECT series_id, game_id, round_num, team_id, SUM(lv) AS loadout
        FROM (SELECT series_id, game_id, round_num, team_id, player_id,
                     MAX(loadout_value) AS lv
              FROM loadouts WHERE game_id IN (SELECT game_id FROM team_games)
              GROUP BY series_id, game_id, round_num, team_id, player_id)
        GROUP BY series_id, game_id, round_num, team_id
    )
    SELECT r.series_id, r.game_id, g.map, g.started_at, r.round_num,
           CASE WHEN r.attack_team_id = :team THEN r.defense_team_id
                ELSE r.attack_team_id END AS opponent_id,
           CASE WHEN r.attack_team_id = :team THEN 'attacker' ELSE 'defender' END AS side,
           r.winner_team_id = :team AS won,
           r.win_type,
           classify_buy(r.round_num, own.loadout) AS own_buy,
           classify_buy(r.round_num, opp.loadout) AS opp_buy
    FROM rounds r
    JOIN meta_games g ON g.game_id = r.game_id
    LEFT JOIN team_buy own
           ON own.series_id = r.series_id AND own.game_id = r.game_id
          AND own.round_num = r.round_num AND own.team_id = :team
    LEFT JOIN team_buy opp
           ON opp.series_id = r.series_id AND opp.game_id = r.game_id
          AND opp.round_num = r.round_num AND opp.team_id != :team
    WHERE {where}
    ORDER BY g.started_at, r.round_num
    """
    rows = con.execute(sql, params).fetchall()
    return [TeamRound(*r[:7], bool(r[7]), *r[8:]) for r in rows]
