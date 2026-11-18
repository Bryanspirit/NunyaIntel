"""Core domain models. Keep these provider-agnostic: adapters map raw feeds onto them."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Side(StrEnum):
    ATTACK = "attack"
    DEFENSE = "defense"


@dataclass(frozen=True, slots=True)
class Player:
    id: str
    name: str
    team_id: str
    agent: str | None = None


@dataclass(frozen=True, slots=True)
class Team:
    id: str
    name: str


@dataclass(slots=True)
class Round:
    number: int
    map_name: str
    attacking_team_id: str
    winner_team_id: str | None = None
    events: list[dict] = field(default_factory=list)  # TODO: replace with typed events


@dataclass(slots=True)
class Match:
    id: str
    map_name: str
    teams: tuple[Team, Team]
    rounds: list[Round] = field(default_factory=list)
