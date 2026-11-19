"""Map knowledge: named regions ("A Main", "Mid Courtyard"), sites, and minimap coordinates.

GRID positions are raw game coordinates with no names. The community API valorant-api.com
publishes, per map, named *callouts* (a point in the same game coordinates) and the formula to
convert game coordinates to minimap image coordinates. We verified the coordinate systems
match: spike plants sit a median 3-10 m from the nearest "Site" callout.

``region_of`` gives a position the name of the *nearest* callout. That splits the map into one
zone per callout (a "Voronoi diagram"): simple, and good enough for "which area was this in".

The JSON is downloaded once to ``data/cache/maps.json`` (gitignored).
"""

from __future__ import annotations

import json
import math
import urllib.request
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from nunyaintel.config import DATA_DIR

MAPS_URL = "https://valorant-api.com/v1/maps"
DEFAULT_PATH = DATA_DIR / "cache" / "maps.json"
# Minimap images, downloaded once so the app works offline (and when a network blocks the
# image server: on 19 Nov a TLS-inspecting network made media.valorant-api.com unreachable).
MINIMAP_DIR = DATA_DIR / "cache" / "minimaps"


@dataclass(frozen=True, slots=True)
class Callout:
    super_region: str  # "A", "B", "C", "Mid", "Attacker Side", "Defender Side"
    region: str  # "Site", "Main", "Lobby", "Courtyard", ...
    x: float
    y: float

    @property
    def name(self) -> str:
        return f"{self.super_region} {self.region}"


@dataclass(frozen=True, slots=True)
class MapInfo:
    name: str
    callouts: tuple[Callout, ...]
    x_multiplier: float
    y_multiplier: float
    x_scalar_to_add: float
    y_scalar_to_add: float
    minimap_url: str | None

    def region_of(self, x: float, y: float) -> Callout:
        """The nearest named callout to a game position."""
        return min(self.callouts, key=lambda c: (c.x - x) ** 2 + (c.y - y) ** 2)

    @property
    def sites(self) -> tuple[Callout, ...]:
        return tuple(c for c in self.callouts if c.region == "Site")

    def site_of(self, x: float, y: float, max_m: float | None = None) -> str:
        """Nearest bomb site letter ("A", "B", "C") to a game position.

        With ``max_m``, a position farther than that from every site returns "unknown"
        instead of a guess. A spike can only be planted on a site, so a "plant" 70 m from
        both sites is a bad position record (26 such plants, all on Bind), not a real plant
        location.
        """
        site = min(self.sites, key=lambda c: (c.x - x) ** 2 + (c.y - y) ** 2)
        if max_m is not None and math.dist((x, y), (site.x, site.y)) / 100 > max_m:
            return "unknown"
        return site.super_region

    def distance_to_site_m(self, x: float, y: float) -> float:
        return min(math.dist((x, y), (c.x, c.y)) for c in self.sites) / 100.0

    def to_minimap(self, x: float, y: float) -> tuple[float, float]:
        """Game position -> (u, v) in 0..1 on the minimap image (u = right, v = down).

        Note the swap: the image's horizontal axis comes from the game's *y* coordinate.
        This is the formula valorant-api.com documents for its multipliers.
        """
        u = y * self.x_multiplier + self.x_scalar_to_add
        v = x * self.y_multiplier + self.y_scalar_to_add
        return u, v


def _parse(raw: dict[str, Any]) -> MapInfo:
    callouts = tuple(
        Callout(c["superRegionName"], c["regionName"], c["location"]["x"], c["location"]["y"])
        for c in raw.get("callouts") or []
    )
    return MapInfo(
        name=raw["displayName"].lower(),
        callouts=callouts,
        x_multiplier=raw.get("xMultiplier") or 0.0,
        y_multiplier=raw.get("yMultiplier") or 0.0,
        x_scalar_to_add=raw.get("xScalarToAdd") or 0.0,
        y_scalar_to_add=raw.get("yScalarToAdd") or 0.0,
        minimap_url=raw.get("displayIcon"),
    )


def download(path: Path = DEFAULT_PATH) -> Path:
    """Fetch the public map metadata once. No user or project data is sent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(MAPS_URL, headers={"User-Agent": "nunyaintel"})
    with urllib.request.urlopen(request, timeout=60) as response:
        path.write_bytes(response.read())
    return path


def minimap_path(name: str, directory: Path = MINIMAP_DIR) -> Path:
    return directory / f"{name.lower()}.png"


def download_minimap(info: MapInfo, directory: Path = MINIMAP_DIR, timeout: float = 15) -> Path:
    """Fetch one minimap image into the local cache. Raises OSError on any network problem.

    Certificate checks stay on: a network that breaks HTTPS gets an error, not a silent bypass.
    """
    if not info.minimap_url:
        raise OSError(f"no minimap URL for {info.name}")
    request = urllib.request.Request(info.minimap_url, headers={"User-Agent": "nunyaintel"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if not data.startswith(b"\x89PNG"):  # every PNG file starts with these bytes
        raise OSError(f"{info.name}: not a PNG image")
    directory.mkdir(parents=True, exist_ok=True)
    target = minimap_path(info.name, directory)
    target.write_bytes(data)
    return target


def cache_minimaps(maps_path: Path | None = None, directory: Path = MINIMAP_DIR) -> dict[str, str]:
    """Download every minimap not cached yet. Returns {map: "cached" / "downloaded" / error}."""
    result = {}
    for name, info in load_maps(maps_path or DEFAULT_PATH).items():
        if minimap_path(name, directory).exists():
            result[name] = "cached"
            continue
        try:
            download_minimap(info, directory)
            result[name] = "downloaded"
        except OSError as exc:
            result[name] = f"failed: {exc}"
    return result


@cache
def load_maps(path: Path = DEFAULT_PATH) -> dict[str, MapInfo]:
    """All maps that have callouts, keyed by lower-case name (e.g. "lotus")."""
    if not path.exists():
        download(path)
    data = json.loads(path.read_text(encoding="utf-8"))["data"]
    return {m.name: m for m in map(_parse, data) if m.callouts and m.sites}


def get_map(name: str, path: Path = DEFAULT_PATH) -> MapInfo:
    maps = load_maps(path)
    try:
        return maps[name.lower()]
    except KeyError:
        raise KeyError(f"No callout data for map {name!r}. Known: {sorted(maps)}") from None
