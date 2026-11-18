"""Utility placement: where and when each ability is cast (U1).

Loads ability casts from the local extract with the precise cast position and aim direction
from the ability supplement. Positions are in game units (1 unit = 1 cm), in the same x/y frame
as GRID. The supplement gives where the caster *stood and aimed*, not where the ability
landed; landing spots must be estimated later (U2/U3).

Timing: ``time_s`` is seconds since the buy phase ended. Negative values are casts *during*
the buy phase (setup utility such as traps), positive values are during the round.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

# VCT Americas 2025 matches only have 1 Hz movement samples, so cast positions there can be
# off by a few metres (see the data repo's val-ability-supplements/README.md).
LOW_RATE_EVENT_PATTERN = "VCT Americas - % 2025"


@dataclass(frozen=True, slots=True)
class UtilityUsage:
    series_id: str
    game_id: str
    map_name: str
    round_num: int
    player_id: str
    team_id: str
    side: str
    agent: str | None
    ability: str
    slot: str | None
    time_s: float | None
    x: float
    y: float
    z: float | None
    view_x: float | None
    view_y: float | None
    view_z: float | None
    precise: bool
    round_won: bool
    event_id: str = ""  # GRID event ID of the cast (links to damage/kills timing)
    occurred_at: str = ""  # UTC timestamp of the cast

    @property
    def in_buy_phase(self) -> bool:
        return self.time_s is not None and self.time_s < 0


def load_utility(
    con: sqlite3.Connection,
    map_name: str | None = None,
    team_id: str | None = None,
    side: str | None = None,
    player_id: str | None = None,
    agent: str | None = None,
    ability: str | None = None,
    series_ids: Sequence[str] | None = None,
    precise_only: bool = False,
    include_passive: bool = False,
) -> list[UtilityUsage]:
    """Ability casts with a good-quality cast position, from real rounds only.

    Filters are optional and combine with AND. ``side`` is "attacker" or "defender".
    ``include_passive`` keeps PASSIVE-slot casts, which aren't placed utility.
    """
    clauses = ["a.quality = 'ok'", "r.winner_team_id IS NOT NULL"]
    params: list[str] = []
    for column, value in (
        ("lower(g.map)", map_name.lower() if map_name else None),
        ("a.team_id", team_id),
        ("a.side", side),
        ("a.player_id", player_id),
        ("l.agent", agent),
        ("a.ability", ability),
    ):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if series_ids:
        clauses.append(f"a.series_id IN ({', '.join('?' * len(series_ids))})")
        params.extend(series_ids)
    if precise_only:
        clauses.append("ms.event NOT LIKE ?")
        params.append(LOW_RATE_EVENT_PATTERN)
    if not include_passive:
        clauses.append("COALESCE(a.slot, '') != 'PASSIVE'")

    sql = f"""
    SELECT a.series_id, a.game_id, g.map, a.round_num, a.player_id, a.team_id, a.side,
           l.agent, a.ability, a.slot,
           -- julianday() turns an ISO timestamp into days; * 86400 converts days to seconds
           (julianday(a.occurred_at) - julianday(r.buy_ended_at)) * 86400.0 AS time_s,
           a.cast_x, a.cast_y, a.cast_z, a.view_x, a.view_y, a.view_z,
           ms.event NOT LIKE ? AS precise,
           r.winner_team_id = a.team_id AS round_won,
           a.event_id, a.occurred_at
    FROM abilities a
    JOIN rounds r ON r.series_id = a.series_id AND r.game_id = a.game_id
                 AND r.round_num = a.round_num
    JOIN meta_games g ON g.game_id = a.game_id
    JOIN meta_series ms ON ms.series_id = a.series_id
    LEFT JOIN loadouts l ON l.series_id = a.series_id AND l.game_id = a.game_id
                        AND l.round_num = a.round_num AND l.player_id = a.player_id
    WHERE {" AND ".join(clauses)}
    -- a restarted round can leave two loadout rows; GROUP BY the cast keeps one row per cast
    GROUP BY a.event_id
    ORDER BY a.series_id, a.game_id, a.round_num, a.occurred_at
    """
    rows = con.execute(sql, [LOW_RATE_EVENT_PATTERN, *params]).fetchall()
    return [
        UtilityUsage(
            *r[:17], precise=bool(r[17]), round_won=bool(r[18]), event_id=r[19], occurred_at=r[20]
        )
        for r in rows
    ]


@dataclass(slots=True)
class AbilitySummary:
    """How one agent's ability is used across a set of rounds."""

    agent: str
    ability: str
    slot: str
    casts: int
    rounds: int
    buy_phase_casts: int
    median_time_s: float | None

    @property
    def per_round(self) -> float:
        return self.casts / self.rounds if self.rounds else 0.0

    @property
    def buy_phase_share(self) -> float:
        return self.buy_phase_casts / self.casts if self.casts else 0.0


def summarize(usages: Sequence[UtilityUsage]) -> list[AbilitySummary]:
    """Group casts by (agent, ability). ``rounds`` = rounds that agent was played in this set.

    "Per round" divides by rounds where *some player on that agent* cast anything, which is a
    close stand-in for rounds played on the agent.
    """
    agent_rounds: dict[str, set[tuple[str, str, int, str]]] = defaultdict(set)
    groups: dict[tuple[str, str, str], list[UtilityUsage]] = defaultdict(list)
    for u in usages:
        agent = u.agent or "?"
        agent_rounds[agent].add((u.series_id, u.game_id, u.round_num, u.player_id))
        groups[agent, u.ability, u.slot or "?"].append(u)

    summaries = []
    for (agent, ability, slot), casts in groups.items():
        times = [u.time_s for u in casts if u.time_s is not None]
        summaries.append(
            AbilitySummary(
                agent=agent,
                ability=ability,
                slot=slot,
                casts=len(casts),
                rounds=len(agent_rounds[agent]),
                buy_phase_casts=sum(u.in_buy_phase for u in casts),
                median_time_s=statistics.median(times) if times else None,
            )
        )
    summaries.sort(key=lambda s: (s.agent, -s.casts))
    return summaries


def format_summary(summaries: Sequence[AbilitySummary]) -> str:
    header = (
        f"{'agent':<10}{'ability':<20}{'slot':<10}{'casts':>7}{'/round':>8}"
        f"{'in buy':>8}{'median t':>10}"
    )
    lines = [header, "-" * len(header)]
    for s in summaries:
        t = f"{s.median_time_s:+.0f}s" if s.median_time_s is not None else "-"
        lines.append(
            f"{s.agent[:9]:<10}{s.ability[:19]:<20}{s.slot[:9]:<10}{s.casts:>7}"
            f"{s.per_round:>8.2f}{s.buy_phase_share:>8.0%}{t:>10}"
        )
    return "\n".join(lines)
