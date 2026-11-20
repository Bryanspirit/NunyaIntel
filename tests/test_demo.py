"""The made-up demo dataset: every API endpoint must answer on it (no licensed data needed)."""

import pytest
from fastapi.testclient import TestClient

from nunyaintel import demo
from nunyaintel.api import create_app
from nunyaintel.maps import load_maps

ENDPOINTS = [
    "/api/meta", "/api/findings?team=T1", "/api/scout?team=T1&map=demomap",
    "/api/operator?team=T1&map=demomap", "/api/operator/angles?team=T1&map=demomap",
    "/api/utility?team=T1&map=demomap", "/api/utility/lineups?team=T1&map=demomap",
    "/api/replay?team=T1&map=demomap", "/api/matches?team=T1", "/api/match?team=T1&game=G00",
    "/api/matchup-report?team=T1&map=demomap", "/api/gameplan?team=T1&map=demomap",
    "/api/predict/matchup?team=T1", "/api/predict/next-buy?team=T1", "/api/predict/round",
    "/api/predict/next-buy/forecast?last_buy=eco&won=false&streak=2&credits=12000&kept=0",
    "/api/player?player=T1P3&map=demomap", "/api/players?q=a", "/api/impact?team=T1",
    "/api/recent?team=T1", "/api/comps?team=T1&map=demomap",
    "/api/playstyle?team=T1&map=demomap", "/api/veto?team=T1",
    "/api/clutch?team=T1", "/api/clutch?team=T1&map=demomap",
    "/api/form?team=T1", "/api/brief?team=T1&opponent=T2&map=demomap", "/api/brief?team=T1",
    "/api/maps/demomap",
    "/api/maps/demomap/minimap",
]  # fmt: skip


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo")
    demo.build(d / "demo.sqlite", d / "maps.json")
    load_maps.cache_clear()
    app = create_app(db_path=d / "demo.sqlite", maps_path=d / "maps.json",
                     baselines_path=d / "b.json", minimap_dir=d / "minimaps")  # fmt: skip
    yield TestClient(app)
    load_maps.cache_clear()


@pytest.mark.parametrize("url", ENDPOINTS)
def test_every_endpoint_answers_on_demo_data(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text[:300]


def test_demo_has_believable_content(client):
    meta = client.get("/api/meta").json()
    assert {t["name"] for t in meta["teams"]} == {"Northwind", "Harbor Lights", "Quarry Five"}
    assert meta["maps"] == ["demomap"]
    style = client.get("/api/playstyle", params={"team": "T1", "map": "demomap"}).json()
    assert style["team"]["median_plant_s"] > 55  # Northwind's invented habit: late hits


def test_demo_refuses_to_replace_a_real_extract(tmp_path):
    import sqlite3

    real = tmp_path / "real.sqlite"
    with sqlite3.connect(real) as con:
        con.execute("CREATE TABLE build_info (key TEXT, value TEXT)")
        con.execute("INSERT INTO build_info VALUES ('data_repo', 'D:/data')")
    with pytest.raises(FileExistsError):
        demo.build(real, tmp_path / "maps.json")
    demo.build(tmp_path / "d.sqlite", tmp_path / "m.json")
    demo.build(tmp_path / "d.sqlite", tmp_path / "m.json")  # replacing a demo is fine


def test_demo_match_story_has_buy_calls(client):
    story = client.get("/api/match", params={"team": "T1", "game": "G00"}).json()
    right, n = story["summary"]["opp_buy_calls"]
    assert 0 < n <= len(story["rounds"]) and 0 <= right <= n
    called = [r["opp_call"] for r in story["rounds"] if r["opp_call"]]
    assert all(c["buy"] in ("eco", "semi-eco", "semi-buy", "full-buy") for c in called)


def test_demo_clutch_finds_situations(client):
    r = client.get("/api/clutch", params={"team": "T1", "map": "demomap"}).json()
    assert r["clutch"]["n"] > 0 and r["retake"]["n"] > 0 and r["post_plant"]["n"] > 0
    assert sum(v["n"] for v in r["clutch"]["by_vs"]) == r["clutch"]["n"]
    assert {s["site"] for s in r["retake"]["sites"]} <= {"A", "B"}


def test_demo_form_and_freshness(client):
    f = client.get("/api/form", params={"team": "T1"}).json()
    assert len(f["matches"]) == len(f["rolling"]) >= 2
    assert [m["date"] for m in f["matches"]] == sorted(m["date"] for m in f["matches"])
    for m, r in zip(f["matches"], f["rolling"], strict=True):
        assert m["rounds"][0] <= m["rounds"][1] and 0 <= r["rate"] <= 1 and r["se"] >= 0
        assert m["rounds"][1] == m["attack"][1] + m["defense"][1]
    assert client.get("/api/meta").json()["data_end"] >= f["last_match"]


def test_demo_brief_keeps_evidence(client):
    b = client.get("/api/brief", params={"team": "T1", "opponent": "T2", "map": "demomap"}).json()
    assert b["title"].startswith("Harbor Lights on Demomap")
    assert b["sections"] and all(s["lines"] for s in b["sections"])
    for s in b["sections"]:
        for line in s["lines"]:
            assert line["text"] and line["text"] in b["text"]  # the copy text has every line
    assert b["sections"][-1]["key"] == "todo" and len(b["sections"][-1]["lines"]) <= 3
