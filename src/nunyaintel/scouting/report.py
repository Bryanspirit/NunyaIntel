"""Build a scouting report from a team's recent matches."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from nunyaintel.data.models import Match


@dataclass(slots=True)
class ScoutingReport:
    team_id: str
    matches_analysed: int
    notes: list[str] = field(default_factory=list)


def build_report(team_id: str, matches: Iterable[Match]) -> ScoutingReport:
    """TODO: site preferences, default setups, pistol/eco tendencies, round win rates per side."""
    match_list = list(matches)
    return ScoutingReport(team_id=team_id, matches_analysed=len(match_list))
