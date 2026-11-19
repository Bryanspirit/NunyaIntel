"""API tests: every endpoint against a tiny synthetic database file and map file.

The analysis logic has its own tests; here we check the HTTP layer: status codes, JSON shapes,
filters reaching the analysis, and minimap coordinates being added. No real data.
"""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from nunyaintel.api import create_app
from nunyaintel.data.extract import SCHEMA
from nunyaintel.maps import load_maps

MAPS = {
    "data": [
        {
            "displayName": "Testmap",
            "displayIcon": "https://example.invalid/testmap.png",
            "xMultiplier": 0.0001, "yMultiplier": -0.0001,
            "xScalarToAdd": 0.5, "yScalarToAdd": 0.5,
            "callouts": [
                {"regionName": "Site", "superRegionName": "A", "location": {"x": 1000, "y": 0}},
                {"regionName": "Site", "superRegionName": "B", "location": {"x": -1000, "y": 0}},
                {"regionName": "Main", "superRegionName": "A", "location": {"x": 2500, "y": 0}},
            ],
        }
    ]
}  # fmt: skip


def _insert(con, table, **row):
    cols = ", ".join(row)
    marks = ", ".join("?" * len(row))
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


@pytest.fixture
def paths(tmp_path):
    """A tiny synthetic database file and map file: (db_path, maps_path)."""
    db = tmp_path / "test.sqlite"
    con = sqlite3.connect(db)
    for table, cols in SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({cols})")
    con.execute(
        "CREATE TABLE meta_teams (team_id TEXT, name TEXT, series_count TEXT, "
        "first_seen TEXT, last_seen TEXT)"
    )
    con.execute("CREATE TABLE meta_players (player_id TEXT, name TEXT)")
    con.execute(
        "CREATE TABLE meta_games (game_id TEXT, map TEXT, started_at TEXT, "
        "team1_id TEXT, team2_id TEXT, winner_team_id TEXT)"
    )
    con.execute("CREATE TABLE meta_series (series_id TEXT, event TEXT)")
    _insert(con, "meta_teams", team_id="A", name="Alpha", series_count="2",
            first_seen="2025-01-01", last_seen="2025-02-01")  # fmt: skip
    _insert(con, "meta_teams", team_id="B", name="Bravo", series_count="2",
            first_seen="2025-01-01", last_seen="2025-02-01")  # fmt: skip
    _insert(con, "meta_players", player_id="p1", name="Alice")

    for i, series in enumerate(("s1", "s2"), 1):
        game = f"g{i}"
        _insert(con, "meta_games", game_id=game, map="Testmap", started_at=f"2025-0{i}-01",
                team1_id="A", team2_id="B", winner_team_id="A")  # fmt: skip
        _insert(con, "meta_series", series_id=series, event="Test Cup 2026")
        for num, winner in ((1, "A"), (2, "B")):
            buy_end = f"2025-0{i}-01T10:0{num}:00.000Z"
            _insert(con, "rounds", series_id=series, game_id=game, round_num=num,
                    buy_ended_at=buy_end, attack_team_id="A", defense_team_id="B",
                    winner_team_id=winner, win_type="opponentEliminated")  # fmt: skip
            _insert(con, "loadouts", series_id=series, game_id=game, round_num=num,
                    player_id="p1", team_id="A", side="attacker", agent="sova",
                    loadout_value=4500, has_operator=1)  # fmt: skip
            at = f"2025-0{i}-01T10:0{num}:10.000Z"
            _insert(con, "objectives", series_id=series, game_id=game, round_num=num,
                    occurred_at=at, team_id="A", action="plantBomb", x=950, y=10)  # fmt: skip
            _insert(con, "kills", series_id=series, game_id=game, round_num=num,
                    occurred_at=at, killer_id="p1", killer_team_id="A", victim_id="e1",
                    victim_team_id="B", weapon="operator", first_kill=1,
                    killer_x=2500, killer_y=0, victim_x=1000, victim_y=0)  # fmt: skip
            _insert(con, "damage", series_id=series, game_id=game, round_num=num,
                    occurred_at=at, attacker_id="p1", attacker_team_id="A",
                    attacker_side="attacker", source="operator", amount=150,
                    victim_health_after=0, attacker_x=2500, attacker_y=0,
                    victim_x=1000, victim_y=0)  # fmt: skip
            # the same recon bolt lineup cast in every round
            for k in range(2):
                _insert(con, "abilities", series_id=series, game_id=game, round_num=num,
                        occurred_at=f"2025-0{i}-01T10:0{num}:0{k + 2}.000Z",
                        event_id=f"{series}-{num}-{k}", player_id="p1", team_id="A",
                        side="attacker", ability="recon-bolt", slot="ABILITY_2",
                        quality="ok", grid_x=2500, grid_y=0, cast_x=2500 + k, cast_y=0,
                        cast_z=0, view_x=-1, view_y=0, view_z=0)  # fmt: skip
    con.commit()
    con.close()

    maps = tmp_path / "maps.json"
    maps.write_text(json.dumps(MAPS), encoding="utf-8")
    load_maps.cache_clear()
    return db, maps


@pytest.fixture
def client(paths):
    db, maps = paths
    return TestClient(create_app(db_path=db, maps_path=maps))


def test_meta(client):
    j = client.get("/api/meta").json()
    assert [t["name"] for t in j["teams"]] == ["Alpha", "Bravo"]
    assert j["teams"][0]["series"] == 2
    assert j["maps"] == ["testmap"]


def test_map_info(client):
    j = client.get("/api/maps/TESTMAP").json()
    assert j["minimap_url"] == "/api/maps/testmap/minimap"  # served by us, works offline
    assert j["minimap_source"].endswith("testmap.png")
    site_a = next(c for c in j["callouts"] if c["name"] == "A Site")
    assert (site_a["u"], site_a["v"]) == pytest.approx((0.5, 0.4))  # u from y, v from x
    assert client.get("/api/maps/nowhere").status_code == 404


def test_scout(client):
    j = client.get("/api/scout", params={"team": "alpha", "map": "testmap"}).json()
    assert j["team"] == {"id": "A", "name": "Alpha"}
    assert (j["games"], j["rounds"]) == (2, 4)
    assert j["sides"]["attacker"] == {"won": 2, "played": 4, "win_rate": 0.5}
    assert j["sites"]["attack"][0]["site"] == "A"
    plant = j["sites"]["plants"][0]
    assert plant["by_us"] is True and 0 <= plant["u"] <= 1
    assert j["sites"]["setups"][0]["name"] == "Alice"
    # without a map: no sites section; unknown team: 404
    assert "sites" not in client.get("/api/scout", params={"team": "A"}).json()
    assert client.get("/api/scout", params={"team": "Nobody"}).status_code == 404


def test_operator(client):
    j = client.get("/api/operator", params={"team": "A"}).json()
    (p,) = j["profiles"]
    assert (p["name"], p["rounds_with_op"], p["op_kills"]) == ("Alice", 4, 4)
    assert {r["economy"] for r in j["economy"]} == {"pistol", "eco"}
    assert j["duels"][0]["op_duels_won"] == 4


def test_operator_angles(client):
    j = client.get("/api/operator/angles", params={"map": "testmap", "team": "A"}).json()
    (a,) = j["angles"]
    assert (a["from_region"], a["to_region"], a["shots"]) == ("A Main", "A Site", 4)
    assert {"u", "v", "target_u", "target_v"} <= set(a)


def test_utility(client):
    j = client.get("/api/utility", params={"map": "testmap", "team": "A"}).json()
    assert (j["casts"], j["rounds"]) == (8, 4)
    assert j["summary"][0]["ability"] == "recon-bolt"


def test_utility_lineups(client):
    j = client.get("/api/utility/lineups", params={"map": "testmap", "team": "A"}).json()
    (lu,) = j["lineups"]
    assert (lu["ability"], lu["series"], lu["region"]) == ("recon-bolt", 2, "A Main")
    assert "score" in lu and lu["aim_u"] is not None
    bad = client.get("/api/utility/lineups", params={"map": "testmap", "radius": -1})
    assert bad.status_code == 422  # FastAPI validates query parameters for us


def test_connection_usable_across_threads(tmp_path):
    """Regression: FastAPI may open the connection on one worker thread and run the endpoint
    on another. With sqlite3's default check_same_thread=True that failed with HTTP 500 when
    the browser sent several requests at once."""
    import threading

    from nunyaintel.data.extract import connect

    db = tmp_path / "x.sqlite"
    sqlite3.connect(db).close()
    con = connect(db, check_same_thread=False)
    errors = []

    def use():
        try:
            con.execute("SELECT 1").fetchone()
        except Exception as exc:  # pragma: no cover - only on regression
            errors.append(exc)

    t = threading.Thread(target=use)
    t.start()
    t.join()
    assert errors == []


def test_parallel_requests(client):
    """Several requests at once (like the browser does) all succeed."""
    from concurrent.futures import ThreadPoolExecutor

    urls = ["/api/meta", "/api/scout?team=A", "/api/utility?map=testmap", "/api/operator"] * 4
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda u: client.get(u).status_code, urls))
    assert codes == [200] * len(urls)


def test_serves_built_web_app(paths, tmp_path):
    """W5: with a built React app, / serves the page and /api/... still reaches the API."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<title>NunyaIntel</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    db, maps = paths
    app = TestClient(create_app(db_path=db, maps_path=maps, static_dir=dist))

    page = app.get("/")
    assert page.status_code == 200 and "NunyaIntel" in page.text
    assert app.get("/assets/app.js").status_code == 200
    assert app.get("/api/meta").json()["maps"] == ["testmap"]  # API not shadowed by the mount
    assert app.get("/docs").status_code == 200


def test_without_built_web_app(paths, tmp_path):
    db, maps = paths
    app = TestClient(create_app(db_path=db, maps_path=maps, static_dir=tmp_path / "missing"))
    assert app.get("/").status_code == 404
    assert app.get("/api/meta").status_code == 200


def test_findings(paths, tmp_path):
    db, maps = paths
    app = TestClient(create_app(db_path=db, maps_path=maps, baselines_path=tmp_path / "b.json"))
    j = app.get("/api/findings", params={"team": "A", "map": "testmap"}).json()
    assert j["team"] == {"id": "A", "name": "Alpha"}
    assert (j["rounds"], j["map"], j["map_was_chosen"]) == (4, "testmap", True)
    assert isinstance(j["league"], list) and isinstance(j["map_findings"], list)
    assert (tmp_path / "b.json").exists()  # baselines cached on first use
    assert app.get("/api/findings", params={"team": "A", "map": "nowhere"}).status_code == 404


def test_response_cache_hit_miss_and_invalidation(paths):
    import os

    db, maps = paths
    app = TestClient(create_app(db_path=db, maps_path=maps))
    first = app.get("/api/scout", params={"team": "A"})
    again = app.get("/api/scout", params={"team": "A"})
    assert (first.headers["X-Cache"], again.headers["X-Cache"]) == ("MISS", "HIT")
    assert first.json() == again.json()
    # different parameters = a different question
    assert app.get("/api/scout", params={"team": "B"}).headers["X-Cache"] == "MISS"
    # errors are never cached
    for _ in range(2):
        assert app.get("/api/scout", params={"team": "Nobody"}).headers["X-Cache"] == "MISS"
    # a rebuilt extract (new modification time) invalidates everything
    st = os.stat(db)
    os.utime(db, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert app.get("/api/scout", params={"team": "A"}).headers["X-Cache"] == "MISS"


def test_response_cache_evicts_least_recently_used():
    from nunyaintel.api.app import ResponseCache

    cache = ResponseCache(max_bytes=10)
    cache.put(("a",), b"12345", "x")
    cache.put(("b",), b"12345", "x")
    assert cache.get(("a",))  # touch "a": now "b" is the least recently used
    cache.put(("c",), b"12345", "x")  # over 10 bytes: evict "b"
    assert cache.get(("b",)) is None and cache.get(("a",)) and cache.get(("c",))
    assert cache.size == 10
    cache.put(("huge",), b"x" * 11, "x")  # bigger than the whole cache: not stored
    assert cache.get(("huge",)) is None


def test_minimap_served_from_local_cache(paths, tmp_path, monkeypatch):
    from nunyaintel.api import app as app_module

    db, maps = paths
    cache = tmp_path / "minimaps"
    cache.mkdir()
    png = b"PNG-BYTES-PLACEHOLDER"
    (cache / "testmap.png").write_bytes(png)
    client = TestClient(create_app(db_path=db, maps_path=maps, minimap_dir=cache))
    r = client.get("/api/maps/testmap/minimap")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content == png

    # not cached and the download fails (offline / firewall): draw the map from the data
    (cache / "testmap.png").unlink()

    def offline(*args, **kwargs):
        raise OSError("certificate verify failed")

    monkeypatch.setattr(app_module, "download_minimap", offline)
    client = TestClient(create_app(db_path=db, maps_path=maps, minimap_dir=cache))
    r = client.get("/api/maps/testmap/minimap")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["x-minimap"] == "drawn-from-data" and r.text.startswith("<svg")
    assert (cache / "testmap.svg").exists()  # cached for next time
    assert client.get("/api/maps/nowhere/minimap").status_code == 404


def test_predict_endpoints(client):
    m = client.get("/api/predict/matchup", params={"team": "A"}).json()
    assert (m["a"]["name"], m["b"]["name"]) == ("Alpha", "Bravo")  # most frequent opponent
    assert m["p_a_wins_map"] > 0.5 and m["head_to_head"] == {"a_won": 2, "maps": 2}
    assert "accuracy" in m["model"] and "calibration" in m["model"]
    explicit = client.get("/api/predict/matchup", params={"team": "A", "opponent": "B"}).json()
    assert explicit["p_a_wins_map"] == m["p_a_wins_map"]
    assert client.get("/api/predict/matchup", params={"team": "Nobody"}).status_code == 404

    nb = client.get("/api/predict/next-buy", params={"team": "A"}).json()
    assert nb["team_id"] == "A" and "situations" in nb and "accuracy" in nb["model"]
