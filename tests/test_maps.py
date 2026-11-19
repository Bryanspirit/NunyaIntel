"""Map callout helpers, on a synthetic map file (tests never touch the network)."""

import json

import pytest

from nunyaintel.maps import get_map, load_maps

FAKE = {
    "data": [
        {
            "displayName": "Testmap",
            "displayIcon": "https://example.invalid/minimap.png",
            "xMultiplier": 0.0001, "yMultiplier": -0.0001,
            "xScalarToAdd": 0.5, "yScalarToAdd": 0.5,
            "callouts": [
                {"regionName": "Site", "superRegionName": "A", "location": {"x": 1000, "y": 0}},
                {"regionName": "Site", "superRegionName": "B", "location": {"x": -1000, "y": 0}},
                {"regionName": "Main", "superRegionName": "A", "location": {"x": 2000, "y": 500}},
                {"regionName": "Courtyard", "superRegionName": "Mid", "location": {"x": 0, "y": 0}},
            ],
        },
        {"displayName": "The Range", "callouts": None},  # no callouts: skipped
    ]
}  # fmt: skip


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "maps.json"
    p.write_text(json.dumps(FAKE), encoding="utf-8")
    load_maps.cache_clear()  # load_maps is cached per path; start clean
    return p


def test_load_and_lookup(path):
    assert set(load_maps(path)) == {"testmap"}
    m = get_map("TestMap", path)
    assert m.region_of(1900, 400).name == "A Main"
    assert m.region_of(100, -50).name == "Mid Courtyard"
    assert m.site_of(100, 0) == "A"  # nearest *site*, even though Mid is closer
    assert m.site_of(-400, 0) == "B"
    assert m.distance_to_site_m(1300, 400) == pytest.approx(5.0)


def test_to_minimap(path):
    m = get_map("testmap", path)
    # u comes from game y, v from game x (the documented axis swap)
    assert m.to_minimap(1000, 2000) == pytest.approx((0.7, 0.4))


def test_unknown_map(path):
    with pytest.raises(KeyError, match="No callout data"):
        get_map("bind", path)


def test_site_of_refuses_to_guess_far_positions(path):
    m = get_map("testmap", path)  # sites at x = +1000 and -1000
    assert m.site_of(900, 0, max_m=40) == "A"
    assert m.site_of(0, 9000, max_m=40) == "unknown"  # 90 m from both: bad position
    assert m.site_of(0, 9000) in {"A", "B"}  # without a limit it still picks the nearest


def test_silhouette_merges_runs_and_drops_rare_cells():
    from collections import Counter

    from nunyaintel.silhouette import render_svg

    cells = Counter({(0, 0): 5, (1, 0): 5, (2, 0): 5, (5, 0): 3, (9, 9): 1})
    svg = render_svg(cells, grid=10, min_hits=3)
    assert '<rect x="0" y="0" width="3" height="1"/>' in svg  # 3 neighbours -> one rectangle
    assert '<rect x="5" y="0" width="1" height="1"/>' in svg
    assert 'x="9" y="9"' not in svg  # seen once: probably a bad position, not floor


def test_silhouette_clean_removes_specks_and_fills_holes():
    from nunyaintel.silhouette import clean

    block = {(c, r) for c in range(1, 6) for r in range(1, 6)} - {(3, 3)}  # 5x5 with a pinhole
    speck = {(9, 9)}
    out = clean(block | speck, grid=12)
    assert (3, 3) in out  # pinhole filled
    assert (9, 9) not in out  # isolated speck dropped
    assert (1, 1) in out  # a corner of the block has 3 neighbours: kept
