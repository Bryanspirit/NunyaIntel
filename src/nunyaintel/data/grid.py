"""Low-level access to the Sky's The Limit 2026 GRID data repo (VALORANT only).

Data is licensed for the hackathon: read it in place from ``config.stl_data_dir()``,
stream it (files are 50-150x larger decompressed), and never copy it into this repo.
See the data repo's AGENTS.md and README.md for the full format.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from compression import zstd
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nunyaintel.config import stl_data_dir

TITLE = "val"


def read_jsonl_zst(path: Path) -> Iterator[dict[str, Any]]:
    """Stream one JSON object per line from a .jsonl.zst file."""
    with zstd.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


@dataclass(frozen=True, slots=True)
class SeriesInfo:
    series_id: str
    event: str
    stage: str
    scheduled_start: str
    teams: str
    file: str
    ability_supplement: str


class GridRepo:
    """Entry point to the data repo: series index, meta tables, event feeds, ability supplements."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else stl_data_dir()
        if not (self.root / TITLE / "series.csv").exists():
            raise FileNotFoundError(
                f"GRID data not found at {self.root}. Clone "
                "https://github.com/cloud9esports/stl-hackathon-2026-grid-starter next to this "
                "project or set STL_DATA_DIR."
            )

    # ---- index & metadata -------------------------------------------------------------
    def series(self) -> list[SeriesInfo]:
        with open(self.root / TITLE / "series.csv", newline="", encoding="utf-8") as f:
            return [SeriesInfo(**row) for row in csv.DictReader(f)]

    def meta(self, table: str) -> list[dict[str, str]]:
        """VALORANT rows of meta/<table>.csv (teams, players, games, rosters, ...)."""
        with open(self.root / "meta" / f"{table}.csv", newline="", encoding="utf-8") as f:
            return [row for row in csv.DictReader(f) if row["title"] == TITLE]

    def series_for_team(self, team_id: str) -> list[str]:
        """Series IDs a team played in, using meta/games.csv (join on team ID, not name)."""
        ids = {
            g["series_id"]
            for g in self.meta("games")
            if team_id in (g["team1_id"], g["team2_id"])
        }
        return sorted(ids)

    # ---- feeds ------------------------------------------------------------------------
    def envelopes(self, series_id: str) -> Iterator[dict[str, Any]]:
        yield from read_jsonl_zst(self.root / TITLE / f"events_{series_id}_grid.jsonl.zst")

    def events(self, series_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield (occurredAt, event) for every event in a series, in feed order.

        NOTE: does not yet undo '!'-reversed events or drop rolled-back games
        (see the README's "Data caveats"); that is handled in the parsing layer.
        """
        for env in self.envelopes(series_id):
            for event in env["events"]:
                yield env["occurredAt"], event

    def ability_casts(self, series_id: str) -> Iterator[dict[str, Any]]:
        path = self.root / "val-ability-supplements" / f"{series_id}.jsonl.zst"
        if path.exists():
            yield from read_jsonl_zst(path)
