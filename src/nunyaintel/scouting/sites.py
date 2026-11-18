"""T3: site preferences and default setups for one team on one map.

- **Attack sites:** where the team plants, how often it wins after planting there, and when.
- **Defense sites:** when the opponent plants on a site, how often the team still wins
  (holds or retakes).
- **Default setups:** each player's usual area early in the round. We only know a player's
  position when they *do* something (cast, shoot, take damage, kill, die), so we take their
  first recorded position in the first ``window_s`` seconds after the buy phase. Players who
  stay quiet are invisible: read the "seen in" column as coverage.
- **Opening duels:** where the round's first kill happens and who wins it.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from nunyaintel.maps import MapInfo
from nunyaintel.scouting.overview import SIDES, SideRecord
from nunyaintel.scouting.team_rounds import TeamRound

SETUP_WINDOW_S = 20.0


@dataclass(slots=True)
class SiteStats:
    rounds: SideRecord = field(default_factory=SideRecord)
    plant_times: list[float] = field(default_factory=list)

    @property
    def median_plant_time_s(self) -> float | None:
        return statistics.median(self.plant_times) if self.plant_times else None


@dataclass(slots=True)
class SiteReport:
    attack: dict[str, SiteStats]  # site letter or "no plant" -> stats (our plants)
    defense: dict[str, SiteStats]  # site letter or "no plant" -> stats (their plants)
    attack_rounds: int
    defense_rounds: int


def _marks(values: Sequence[str]) -> str:
    return ", ".join("?" * len(values))


def _round_keys(rounds: Sequence[TeamRound]) -> tuple[list[str], list[str]]:
    return sorted({r.series_id for r in rounds}), sorted({r.game_id for r in rounds})


@dataclass(frozen=True, slots=True)
class Plant:
    """The spike plant of one of the team's rounds (by either team)."""

    game_id: str
    round_num: int
    side: str  # the scouted team's side in that round
    won: bool  # did the scouted team win the round
    planter_team_id: str
    site: str
    x: float
    y: float
    time_s: float | None


def plants(con: sqlite3.Connection, rounds: Sequence[TeamRound], map_info: MapInfo) -> list[Plant]:
    """The first plant of every round in ``rounds`` (positions are for drawing on the map)."""
    series, games = _round_keys(rounds)
    if not games:
        return []
    by_round = {(r.game_id, r.round_num): r for r in rounds}
    found: dict[tuple[str, int], Plant] = {}
    for game, num, planter_team, x, y, t in con.execute(
        f"""SELECT o.game_id, o.round_num, o.team_id, o.x, o.y,
                   (julianday(o.occurred_at) - julianday(r.buy_ended_at)) * 86400.0
            FROM objectives o
            JOIN rounds r ON r.series_id = o.series_id AND r.game_id = o.game_id
                         AND r.round_num = o.round_num
            WHERE o.action = 'plantBomb' AND o.x IS NOT NULL
              AND o.series_id IN ({_marks(series)}) AND o.game_id IN ({_marks(games)})
            ORDER BY o.occurred_at""",
        [*series, *games],
    ):
        r = by_round.get((game, num))
        if r is None or (game, num) in found:
            continue  # not one of our rounds, or a later plant in the same round
        found[game, num] = Plant(
            game, num, r.side, r.won, planter_team, map_info.site_of(x, y), x, y, t
        )
    return list(found.values())


def site_report(
    con: sqlite3.Connection, team_id: str, rounds: Sequence[TeamRound], map_info: MapInfo
) -> SiteReport:
    by_round = {(p.game_id, p.round_num): p for p in plants(con, rounds, map_info)}
    report = SiteReport(defaultdict(SiteStats), defaultdict(SiteStats), 0, 0)
    for r in rounds:
        p = by_round.get((r.game_id, r.round_num))
        site, t = (p.site, p.time_s) if p else ("no plant", None)
        if r.side == "attacker":
            report.attack_rounds += 1
            stats = report.attack[site]
        else:
            report.defense_rounds += 1
            stats = report.defense[site]
        stats.rounds.played += 1
        stats.rounds.won += r.won
        if t is not None:
            stats.plant_times.append(t)
    return report


@dataclass(slots=True)
class PlayerSetup:
    player_id: str
    name: str
    side: str
    agent: str
    rounds_played: int
    regions: Counter[str]

    @property
    def rounds_seen(self) -> int:
        return sum(self.regions.values())


def default_setups(
    con: sqlite3.Connection,
    team_id: str,
    rounds: Sequence[TeamRound],
    map_info: MapInfo,
    window_s: float = SETUP_WINDOW_S,
) -> list[PlayerSetup]:
    """Each player's first known region in the first ``window_s`` s of the action phase."""
    series, games = _round_keys(rounds)
    if not games:
        return []
    keep = {(r.game_id, r.round_num): r.side for r in rounds}
    s_marks, g_marks = _marks(series), _marks(games)
    where = f"series_id IN ({s_marks}) AND game_id IN ({g_marks})"
    # Every event that tells us where one of our players stood, as one long list (UNION ALL)
    sql = f"""
    WITH positions AS (
        SELECT game_id, round_num, player_id AS pid, team_id AS tid, occurred_at,
               grid_x AS x, grid_y AS y FROM abilities WHERE {where}
        UNION ALL SELECT game_id, round_num, killer_id, killer_team_id, occurred_at,
               killer_x, killer_y FROM kills WHERE {where}
        UNION ALL SELECT game_id, round_num, victim_id, victim_team_id, occurred_at,
               victim_x, victim_y FROM kills WHERE {where}
        UNION ALL SELECT game_id, round_num, attacker_id, attacker_team_id, occurred_at,
               attacker_x, attacker_y FROM damage WHERE {where}
        UNION ALL SELECT game_id, round_num, victim_id, victim_team_id, occurred_at,
               victim_x, victim_y FROM damage WHERE {where}
    )
    SELECT p.game_id, p.round_num, p.pid, p.x, p.y,
           (julianday(p.occurred_at) - julianday(r.buy_ended_at)) * 86400.0 AS t
    FROM positions p
    JOIN rounds r ON r.game_id = p.game_id AND r.round_num = p.round_num
                 AND r.winner_team_id IS NOT NULL
    WHERE p.tid = ? AND p.x IS NOT NULL
    """
    params = [*series, *games] * 5 + [team_id]
    first: dict[tuple[str, int, str], tuple[float, float, float]] = {}
    for game, num, pid, x, y, t in con.execute(sql, params):
        if (game, num) not in keep or t is None or not 0 <= t <= window_s:
            continue
        key = (game, num, pid)
        if key not in first or t < first[key][0]:
            first[key] = (t, x, y)

    agents: dict[tuple[str, int, str], str] = {}
    for game, num, pid, agent in con.execute(
        f"""SELECT game_id, round_num, player_id, agent FROM loadouts
            WHERE {where} AND team_id = ?""",
        [*series, *games, team_id],
    ):
        if (game, num) in keep:
            agents[game, num, pid] = agent or "?"

    played: Counter[tuple[str, str]] = Counter()
    agent_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    regions: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for (game, num, pid), agent in agents.items():
        side = keep[game, num]
        played[pid, side] += 1
        agent_counts[pid, side][agent] += 1
        if (game, num, pid) in first:
            _, x, y = first[game, num, pid]
            regions[pid, side][map_info.region_of(x, y).name] += 1

    names = dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())
    setups = [
        PlayerSetup(
            player_id=pid,
            name=names.get(pid, pid),
            side=side,
            agent=agent_counts[pid, side].most_common(1)[0][0],
            rounds_played=n,
            regions=regions[pid, side],
        )
        for (pid, side), n in played.items()
    ]
    setups.sort(key=lambda s: (SIDES.index(s.side), -s.rounds_played, s.name))
    return setups


def opening_duels_by_region(
    con: sqlite3.Connection, team_id: str, rounds: Sequence[TeamRound], map_info: MapInfo
) -> dict[str, dict[str, SideRecord]]:
    """``{side: {region: SideRecord}}``: where first kills happen and how often we win them.

    The region is where the *victim* stood (the contested spot, not the shooter's angle).
    """
    series, games = _round_keys(rounds)
    sides = {(r.game_id, r.round_num): r.side for r in rounds}
    out: dict[str, dict[str, SideRecord]] = {side: defaultdict(SideRecord) for side in SIDES}
    if not games:
        return out
    for game, num, killer_team, x, y in con.execute(
        f"""SELECT game_id, round_num, killer_team_id, victim_x, victim_y FROM kills
            WHERE first_kill = 1 AND victim_x IS NOT NULL
              AND series_id IN ({_marks(series)}) AND game_id IN ({_marks(games)})""",
        [*series, *games],
    ):
        side = sides.get((game, num))
        if side is None:
            continue
        rec = out[side][map_info.region_of(x, y).name]
        rec.played += 1
        rec.won += killer_team == team_id
    return out


def format_sites(
    con: sqlite3.Connection, team_id: str, rounds: Sequence[TeamRound], map_info: MapInfo
) -> str:
    rep = site_report(con, team_id, rounds, map_info)
    lines = [f"Sites on {map_info.name} (spike plants named by nearest site)"]

    def site_lines(stats: dict[str, SiteStats], total: int, verb: str) -> None:
        for site in sorted(stats, key=lambda s: (s == "no plant", s)):
            st = stats[site]
            t = st.median_plant_time_s
            when = f", median plant {t:.0f}s in" if t is not None else ""
            lines.append(
                f"  {site:<9} {st.rounds.played:>4} rounds ({st.rounds.played / total:.0%})"
                f"  {verb} {st.rounds.win_rate:.0%}{when}"
            )

    if rep.attack_rounds:
        lines.append(f" Attack ({rep.attack_rounds} rounds): where WE plant")
        site_lines(rep.attack, rep.attack_rounds, "won")
    if rep.defense_rounds:
        lines.append(f" Defense ({rep.defense_rounds} rounds): where THEY plant")
        site_lines(rep.defense, rep.defense_rounds, "held/retook")

    lines.append(f"\nDefault setups (first area seen in the first {SETUP_WINDOW_S:.0f}s)")
    for s in default_setups(con, team_id, rounds, map_info):
        top = ", ".join(
            f"{region} {n / s.rounds_seen:.0%}" for region, n in s.regions.most_common(3)
        )
        lines.append(
            f"  {s.side:<9} {s.name[:12]:<13}{s.agent[:9]:<10}"
            f"seen in {s.rounds_seen:>3}/{s.rounds_played:<3}  {top}"
        )

    lines.append("\nOpening duels (where the first kill happens; our win %)")
    for side, regions in opening_duels_by_region(con, team_id, rounds, map_info).items():
        total = sum(r.played for r in regions.values())
        top = sorted(regions.items(), key=lambda kv: -kv[1].played)[:4]
        parts = ", ".join(
            f"{name} {rec.played / total:.0%} (win {rec.win_rate:.0%})" for name, rec in top
        )
        lines.append(f"  {side:<9} ({total:>3}): {parts}")
    return "\n".join(lines)
