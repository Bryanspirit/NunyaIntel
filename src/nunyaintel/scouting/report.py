"""Scouting report for one team: overview (T1), economy (T2), and with a map: sites (T3)."""

from __future__ import annotations

import sqlite3

from nunyaintel.scouting.economy_report import format_economy
from nunyaintel.scouting.overview import format_overview
from nunyaintel.scouting.team_rounds import load_team_rounds


def build_report(
    con: sqlite3.Connection,
    team_id: str,
    map_name: str | None = None,
    since: str | None = None,
) -> str:
    rounds = load_team_rounds(con, team_id, map_name=map_name, since=since)
    row = con.execute("SELECT name FROM meta_teams WHERE team_id = ?", (team_id,)).fetchone()
    name = row[0] if row else team_id
    if not rounds:
        return f"No rounds found for {name} with these filters."
    games = len({r.game_id for r in rounds})
    first, last = rounds[0].game_started_at[:10], rounds[-1].game_started_at[:10]
    scope = f" on {map_name}" if map_name else ""
    header = (
        f"SCOUTING REPORT: {name}{scope}\n"
        f"{games} maps, {len(rounds)} rounds, {first} to {last}\n" + "=" * 55
    )
    sections = [header, format_overview(rounds), format_economy(rounds)]
    if map_name:
        from nunyaintel.maps import get_map
        from nunyaintel.scouting.sites import format_sites

        sections.append(format_sites(con, team_id, rounds, get_map(map_name)))
    return "\n\n".join(sections)
