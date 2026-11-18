"""Data source interface. Each provider (official API, local JSON dumps, ...) implements this."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from nunyaintel.data.models import Match


class DataSource(Protocol):
    def matches_for_team(self, team_id: str, limit: int = 20) -> Iterable[Match]:
        """Return the most recent matches played by a team."""
        ...
