"""Where and when utility is used, and how effective it is."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UtilityUsage:
    player_id: str
    agent: str
    ability: str
    map_name: str
    round_number: int
    x: float
    y: float
    time_s: float


# TODO: cluster placements per map/side, find common lineups, score effectiveness.
