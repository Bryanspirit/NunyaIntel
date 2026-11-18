"""O3: the angles Operator players hold, per map and side.

An Operator *shot* = one damage event with source "operator" (98% are lethal: the Op one-shots).
For each shot we know where the shooter stood and where the victim was, so the shot has a
spot and a direction. An *angle* = shots from (almost) the same spot in (almost) the same
direction, found with the same DBSCAN as utility lineups (``utility/lineups.py``):

- neighbours = same player and side, shooters within ``radius_cm`` of each other, and shot
  directions within ``max_angle_deg``. Looser than lineups (3 m / 20 deg) because the
  direction depends on where the victim happened to be, not on a fixed aim.
- an angle must recur in at least ``min_series`` different matches.

Each angle gets a readable name from the map callouts, e.g. "A Tree -> A Main".

Two views: ``find_angles`` (precise spots, needs lots of shots) and ``region_angles`` (shots
grouped by named area, the default: works even for players with few Operator rounds).
Shots longer than ``MAX_SHOT_M`` are dropped: no map is that big, so they're bad positions.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from nunyaintel.maps import MapInfo
from nunyaintel.utility.lineups import NOISE, dbscan

MAX_SHOT_M = 100.0


@dataclass(frozen=True, slots=True)
class OpShot:
    series_id: str
    game_id: str
    round_num: int
    player_id: str
    team_id: str
    side: str
    time_s: float | None
    x: float
    y: float
    target_x: float
    target_y: float
    lethal: bool

    @property
    def distance_m(self) -> float:
        return math.dist((self.x, self.y), (self.target_x, self.target_y)) / 100.0

    @property
    def direction(self) -> tuple[float, float]:
        """Unit vector from shooter to target (2D)."""
        dx, dy = self.target_x - self.x, self.target_y - self.y
        length = math.hypot(dx, dy) or 1.0
        return dx / length, dy / length


def load_op_shots(
    con: sqlite3.Connection,
    map_name: str,
    team_id: str | None = None,
    player_id: str | None = None,
    side: str | None = None,
    weapon: str = "operator",
) -> list[OpShot]:
    """Operator hits on one map from real rounds, with shooter and target positions."""
    clauses = [
        "d.source = :weapon",
        "lower(g.map) = lower(:map)",
        "r.winner_team_id IS NOT NULL",
        "d.attacker_x IS NOT NULL AND d.victim_x IS NOT NULL",
    ]
    params: dict[str, object] = {"weapon": weapon, "map": map_name}
    for column, key, value in (
        ("d.attacker_team_id", "team", team_id),
        ("d.attacker_id", "player", player_id),
        ("d.attacker_side", "side", side),
    ):
        if value:
            clauses.append(f"{column} = :{key}")
            params[key] = value
    sql = f"""
    SELECT d.series_id, d.game_id, d.round_num, d.attacker_id, d.attacker_team_id,
           d.attacker_side,
           (julianday(d.occurred_at) - julianday(r.buy_ended_at)) * 86400.0,
           d.attacker_x, d.attacker_y, d.victim_x, d.victim_y,
           COALESCE(d.victim_health_after, 1) <= 0
    FROM damage d
    JOIN rounds r ON r.series_id = d.series_id AND r.game_id = d.game_id
                 AND r.round_num = d.round_num
    JOIN meta_games g ON g.game_id = d.game_id
    WHERE {" AND ".join(clauses)}
    ORDER BY d.occurred_at
    """
    shots = [OpShot(*row[:11], lethal=bool(row[11])) for row in con.execute(sql, params)]
    return [s for s in shots if s.distance_m <= MAX_SHOT_M]


@dataclass(slots=True)
class Angle:
    player_id: str
    team_id: str
    side: str
    shots: list[OpShot]
    from_region: str
    to_region: str
    x: float
    y: float
    target_x: float
    target_y: float

    @property
    def kills(self) -> int:
        return sum(s.lethal for s in self.shots)

    @property
    def series(self) -> int:
        return len({s.series_id for s in self.shots})

    @property
    def median_distance_m(self) -> float:
        return statistics.median(s.distance_m for s in self.shots)

    @property
    def median_time_s(self) -> float | None:
        times = [s.time_s for s in self.shots if s.time_s is not None]
        return statistics.median(times) if times else None


def find_angles(
    shots: Sequence[OpShot],
    map_info: MapInfo,
    radius_cm: float = 300.0,
    max_angle_deg: float = 20.0,
    min_samples: int = 3,
    min_series: int = 2,
) -> list[Angle]:
    """Cluster Operator shots into held angles, separately per (player, side)."""
    cos_limit = math.cos(math.radians(max_angle_deg))
    groups: dict[tuple[str, str, str], list[OpShot]] = defaultdict(list)
    for s in shots:
        groups[s.player_id, s.team_id, s.side].append(s)

    angles: list[Angle] = []
    for (player_id, team_id, side), group in groups.items():
        dirs = [s.direction for s in group]

        def near(i: int, j: int, group=group, dirs=dirs) -> bool:
            a, b = group[i], group[j]
            if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 > radius_cm**2:
                return False
            return dirs[i][0] * dirs[j][0] + dirs[i][1] * dirs[j][1] >= cos_limit

        clusters: dict[int, list[OpShot]] = defaultdict(list)
        for shot, label in zip(group, dbscan(len(group), near, min_samples), strict=True):
            if label != NOISE:
                clusters[label].append(shot)

        for members in clusters.values():
            if len({m.series_id for m in members}) < min_series:
                continue
            x = statistics.fmean(m.x for m in members)
            y = statistics.fmean(m.y for m in members)
            tx = statistics.fmean(m.target_x for m in members)
            ty = statistics.fmean(m.target_y for m in members)
            angles.append(
                Angle(
                    player_id=player_id,
                    team_id=team_id,
                    side=side,
                    shots=members,
                    from_region=map_info.region_of(x, y).name,
                    to_region=map_info.region_of(tx, ty).name,
                    x=x,
                    y=y,
                    target_x=tx,
                    target_y=ty,
                )
            )
    angles.sort(key=lambda a: (-len(a.shots), a.player_id))
    return angles


def format_angles(angles: Sequence[Angle] | Sequence[RegionAngle], names: dict[str, str]) -> str:
    header = (
        f"{'#':>3} {'player':<13}{'side':<9}{'from -> to':<34}{'shots':>6}{'kills':>6}"
        f"{'matches':>8}{'dist':>6}{'median t':>9}"
    )
    lines = [header, "-" * len(header)]
    for i, a in enumerate(angles, 1):
        t = f"{a.median_time_s:+.0f}s" if a.median_time_s is not None else "-"
        route = f"{a.from_region} -> {a.to_region}"
        lines.append(
            f"{i:>3} {names.get(a.player_id, a.player_id)[:12]:<13}{a.side[:8]:<9}"
            f"{route[:33]:<34}{len(a.shots):>6}{a.kills:>6}{a.series:>8}"
            f"{a.median_distance_m:>5.0f}m{t:>9}"
        )
    return "\n".join(lines)


@dataclass(slots=True)
class RegionAngle:
    """Operator shots grouped by named area: who shot from where, into where."""

    player_id: str
    side: str
    from_region: str
    to_region: str
    shots: list[OpShot]

    @property
    def kills(self) -> int:
        return sum(s.lethal for s in self.shots)

    @property
    def series(self) -> int:
        return len({s.series_id for s in self.shots})

    @property
    def median_distance_m(self) -> float:
        return statistics.median(s.distance_m for s in self.shots)

    @property
    def median_time_s(self) -> float | None:
        times = [s.time_s for s in self.shots if s.time_s is not None]
        return statistics.median(times) if times else None


def region_angles(
    shots: Sequence[OpShot], map_info: MapInfo, min_shots: int = 2
) -> list[RegionAngle]:
    """Group shots by (player, side, shooter's region, target's region). Robust with few shots.

    Precise clustering (``find_angles``) needs several shots from nearly the same spot and
    direction, which only heavy Operator players have. Named regions already group nearby
    positions, so this view works for light Operator users too.
    """
    groups: dict[tuple[str, str, str, str], list[OpShot]] = defaultdict(list)
    for s in shots:
        key = (
            s.player_id,
            s.side,
            map_info.region_of(s.x, s.y).name,
            map_info.region_of(s.target_x, s.target_y).name,
        )
        groups[key].append(s)
    out = [RegionAngle(*key, shots=members) for key, members in groups.items()]
    out = [a for a in out if len(a.shots) >= min_shots]
    out.sort(key=lambda a: (-len(a.shots), -a.series, a.player_id))
    return out
