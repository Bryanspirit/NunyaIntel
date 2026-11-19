"""Draw a map's shape from the data itself: the offline fallback for minimap images.

Every recorded position on a map (ability casts, kills, damage: both attacker and victim) is
projected into minimap coordinates (u, v) with the same formula the overlays use, then binned
into a grid. Cells where players have stood often enough are walkable floor; the rest stays
empty. The result is an SVG in the same coordinate frame as every dot and arrow we draw, so it
lines up exactly, and it needs no internet at all.

Rendered once per map and cached next to the downloaded images (``data/cache/minimaps``).
It's derived from the licensed data, so like everything in data/cache it's never committed.
"""

from __future__ import annotations

import sqlite3
from collections import Counter

from nunyaintel.maps import MapInfo

GRID = 160  # cells per side: fine enough for corridors, coarse enough to fill gaps
MIN_HITS = 3  # a cell needs this many positions to count as floor (drops stray bad positions)


def floor_cells(
    con: sqlite3.Connection, info: MapInfo, grid: int = GRID
) -> Counter[tuple[int, int]]:
    """How many recorded positions fall in each (column, row) cell of the minimap."""
    games = [
        r[0]
        for r in con.execute("SELECT game_id FROM meta_games WHERE lower(map) = ?", (info.name,))
    ]
    if not games:
        return Counter()
    marks = ", ".join("?" * len(games))
    sql = f"""
        SELECT grid_x, grid_y FROM abilities WHERE game_id IN ({marks}) AND grid_x IS NOT NULL
        UNION ALL SELECT killer_x, killer_y FROM kills WHERE game_id IN ({marks}) AND killer_x IS NOT NULL
        UNION ALL SELECT victim_x, victim_y FROM kills WHERE game_id IN ({marks}) AND victim_x IS NOT NULL
        UNION ALL SELECT attacker_x, attacker_y FROM damage WHERE game_id IN ({marks}) AND attacker_x IS NOT NULL
        UNION ALL SELECT victim_x, victim_y FROM damage WHERE game_id IN ({marks}) AND victim_x IS NOT NULL
    """  # noqa: E501
    cells: Counter[tuple[int, int]] = Counter()
    for x, y in con.execute(sql, games * 5):
        u, v = info.to_minimap(x, y)
        if 0 <= u < 1 and 0 <= v < 1:
            cells[int(u * grid), int(v * grid)] += 1
    return cells


def clean(floor: set[tuple[int, int]], grid: int = GRID) -> set[tuple[int, int]]:
    """Neighbour filter (a basic image-processing step): drop isolated specks (fewer than 3
    floor neighbours of 8) and fill pinholes (empty cells with 6+ floor neighbours)."""

    def neighbours(c: int, r: int) -> int:
        return sum(
            (c + dc, r + dr) in floor for dc in (-1, 0, 1) for dr in (-1, 0, 1) if (dc or dr)
        )

    kept = {cell for cell in floor if neighbours(*cell) >= 3}
    holes = {
        (c, r)
        for c in range(grid)
        for r in range(grid)
        if (c, r) not in floor and neighbours(c, r) >= 6
    }
    return kept | holes


def render_svg(
    cells: Counter[tuple[int, int]],
    grid: int = GRID,
    min_hits: int = MIN_HITS,
    smooth: bool = False,
) -> str:
    """SVG of the floor cells. Horizontal runs of floor are merged into one rectangle each,
    which keeps the file small (a few thousand shapes instead of tens of thousands)."""
    floor = {c for c, n in cells.items() if n >= min_hits}
    if smooth:
        floor = clean(floor, grid)
    rects = []
    for row in range(grid):
        col = 0
        while col < grid:
            if (col, row) in floor:
                start = col
                while col < grid and (col, row) in floor:
                    col += 1
                rects.append(f'<rect x="{start}" y="{row}" width="{col - start}" height="1"/>')
            else:
                col += 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {grid} {grid}" '
        f'width="1024" height="1024" shape-rendering="crispEdges">'
        f'<g fill="#7a8794" fill-opacity="0.9">{"".join(rects)}</g></svg>'
    )


def build(con: sqlite3.Connection, info: MapInfo) -> str:
    return render_svg(floor_cells(con, info), smooth=True)
