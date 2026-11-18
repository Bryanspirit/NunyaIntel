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
