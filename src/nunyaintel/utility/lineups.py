"""Lineup detection (U2): find the utility setups a team repeats.

A *lineup* = the same agent's same ability, cast from (almost) the same spot, aimed in (almost)
the same direction. We find them by clustering casts with DBSCAN:

- Two casts are **neighbours** if they are the same (agent, ability), the casters stood within
  ``radius_cm`` of each other, and their aim directions differ by at most ``max_angle_deg``.
- A cast with at least ``min_samples`` neighbours (itself included) is a **core** cast.
- A cluster = core casts linked through neighbours, plus the non-core casts next to them.
- Casts in no cluster are **noise**: one-off plays.

DBSCAN finds however many clusters exist (no need to choose k up front, unlike k-means).
A cluster only counts as a lineup if it shows up in at least ``min_series`` different matches,
so it reflects a habit rather than one game plan.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from nunyaintel.utility.placement import UtilityUsage

NOISE = -1


def dbscan(n: int, are_neighbours: Callable[[int, int], bool], min_samples: int) -> list[int]:
    """Cluster items 0..n-1. Returns a label per item: 0, 1, 2, ... or NOISE (-1).

    Plain O(n^2) DBSCAN: fine for the few hundred casts in one (team, map, side, ability) group.
    """
    neighbours = [[j for j in range(n) if j == i or are_neighbours(i, j)] for i in range(n)]
    labels = [None] * n
    cluster = 0
    for i in range(n):
        if labels[i] is not None:
            continue
        if len(neighbours[i]) < min_samples:
            labels[i] = NOISE  # may still be claimed by a cluster later as a border point
            continue
        labels[i] = cluster
        queue = list(neighbours[i])
        while queue:  # grow the cluster outwards from core points
            j = queue.pop()
            if labels[j] == NOISE:
                labels[j] = cluster  # border point
            if labels[j] is not None:
                continue
            labels[j] = cluster
            if len(neighbours[j]) >= min_samples:
                queue.extend(neighbours[j])
        cluster += 1
    return [NOISE if label is None else label for label in labels]  # type: ignore[misc]


def _unit(x: float, y: float, z: float) -> tuple[float, float, float]:
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    return x / length, y / length, z / length


@dataclass(slots=True)
class Lineup:
    team_id: str
    map_name: str
    side: str
    agent: str
    ability: str
    casts: int
    series: int
    rounds: int
    x: float
    y: float
    z: float
    view_x: float
    view_y: float
    view_z: float
    median_time_s: float | None
    rounds_won: int
    members: list[UtilityUsage]

    @property
    def round_win_rate(self) -> float:
        return self.rounds_won / self.rounds if self.rounds else 0.0

    @property
    def yaw_deg(self) -> float:
        """Horizontal aim direction in degrees (0 = +x, 90 = +y), handy for drawing arrows."""
        return math.degrees(math.atan2(self.view_y, self.view_x)) % 360


def find_lineups(
    usages: Sequence[UtilityUsage],
    radius_cm: float = 150.0,
    max_angle_deg: float = 10.0,
    min_samples: int = 3,
    min_series: int = 2,
) -> list[Lineup]:
    """Cluster casts into lineups, separately per (team, map, side, agent, ability)."""
    cos_limit = math.cos(math.radians(max_angle_deg))
    radius_sq = radius_cm**2

    groups: dict[tuple[str, str, str, str, str], list[UtilityUsage]] = defaultdict(list)
    for u in usages:
        if u.view_x is None or u.view_y is None or u.view_z is None:
            continue  # need an aim direction to tell lineups apart
        groups[u.team_id, u.map_name, u.side, u.agent or "?", u.ability].append(u)

    lineups: list[Lineup] = []
    for (team_id, map_name, side, agent, ability), casts in groups.items():
        views = [_unit(c.view_x, c.view_y, c.view_z) for c in casts]  # type: ignore[arg-type]

        # casts=casts, views=views binds *this* group's lists now (closures look variables
        # up when called, so without this a stored function would see a later loop value)
        def are_neighbours(i: int, j: int, casts=casts, views=views) -> bool:
            a, b = casts[i], casts[j]
            dx, dy, dz = a.x - b.x, a.y - b.y, (a.z or 0.0) - (b.z or 0.0)
            if dx * dx + dy * dy + dz * dz > radius_sq:
                return False
            # dot product of two unit vectors = cos(angle between them)
            dot = sum(p * q for p, q in zip(views[i], views[j], strict=True))
            return dot >= cos_limit

        labels = dbscan(len(casts), are_neighbours, min_samples)
        clusters: dict[int, list[int]] = defaultdict(list)
        for idx, label in enumerate(labels):
            if label != NOISE:
                clusters[label].append(idx)

        for idxs in clusters.values():
            members = [casts[i] for i in idxs]
            series = {m.series_id for m in members}
            if len(series) < min_series:
                continue
            rounds = {(m.series_id, m.game_id, m.round_num): m.round_won for m in members}
            vx, vy, vz = _unit(*(sum(views[i][k] for i in idxs) for k in range(3)))
            times = [m.time_s for m in members if m.time_s is not None]
            lineups.append(
                Lineup(
                    team_id=team_id,
                    map_name=map_name,
                    side=side,
                    agent=agent,
                    ability=ability,
                    casts=len(members),
                    series=len(series),
                    rounds=len(rounds),
                    x=statistics.fmean(m.x for m in members),
                    y=statistics.fmean(m.y for m in members),
                    z=statistics.fmean(m.z or 0.0 for m in members),
                    view_x=vx,
                    view_y=vy,
                    view_z=vz,
                    median_time_s=statistics.median(times) if times else None,
                    rounds_won=sum(rounds.values()),
                    members=members,
                )
            )
    lineups.sort(key=lambda lu: (-lu.series, -lu.casts))
    return lineups


def format_lineups(lineups: Sequence[Lineup]) -> str:
    header = (
        f"{'#':>3} {'side':<9}{'agent':<10}{'ability':<18}{'casts':>6}{'matches':>8}"
        f"{'median t':>9}{'win %':>7}   {'spot (x, y)':<18}{'aim':>5}"
    )
    lines = [header, "-" * len(header)]
    for i, lu in enumerate(lineups, 1):
        t = f"{lu.median_time_s:+.0f}s" if lu.median_time_s is not None else "-"
        lines.append(
            f"{i:>3} {lu.side[:8]:<9}{lu.agent[:9]:<10}{lu.ability[:17]:<18}{lu.casts:>6}"
            f"{lu.series:>8}{t:>9}{lu.round_win_rate:>7.0%}   "
            f"{f'({lu.x:.0f}, {lu.y:.0f})':<18}{lu.yaw_deg:>4.0f}°"
        )
    return "\n".join(lines)
