"""Extractor tests on a tiny synthetic feed. Never use real hackathon data in tests."""

import json
from compression import zstd

from nunyaintel.data.extract import build_cache, connect, parse_series
from nunyaintel.data.grid import GridRepo


def _write_zst(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zstd.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _player(pid, team, side, x=0.0, y=0.0):
    return {"id": pid, "teamId": team, "side": side, "game": {"position": {"x": x, "y": y}}}


def _ev(eid, t, actor, target, **extra):
    a_type, action, t_type = t.split("-")
    return {
        "id": eid,
        "type": t,
        "action": action.lstrip("!"),
        "actor": {"type": a_type, **actor},
        "target": {"type": t_type, **target},
        **extra,
    }


def _freezetime_end(game_id):
    def team(tid, side, pid, items):
        return {
            "id": tid,
            "side": side,
            "players": [
                {
                    "id": pid,
                    "character": {"id": "jett"},
                    "money": 100,
                    "loadoutValue": 5000,
                    "inventory": {"items": [{"id": i} for i in items]},
                }
            ],
        }

    state = {
        "games": [
            {
                "id": game_id,
                "teams": [
                    team("A", "attacker", "p1", ["melee", "classic", "operator"]),
                    team("B", "defender", "p2", ["melee", "vandal"]),
                ],
            }
        ]
    }
    return _ev(
        "fz", "round-ended-freezetime", {"id": "round-1"}, {"id": "freezetime-1"}, seriesState=state
    )


def _kill(eid, weapon):
    return _ev(
        eid,
        "player-killed-player",
        {
            "id": "p1",
            "state": _player("p1", "A", "attacker", 1, 2),
            "stateDelta": {"round": {"weaponKills": {weapon: 1}, "firstKill": True}},
        },
        {"id": "p2", "state": _player("p2", "B", "defender", 3, 4)},
    )


FEED = [
    # game g0 is started, then rolled back (abandoned map): everything in it must be dropped
    [_ev("s0", "series-started-game", {"id": "S"}, {"id": "g0"})],
    [
        _ev(
            "r0",
            "game-started-round",
            {"id": "g0"},
            {"id": "round-1", "state": {"sequenceNumber": 1}},
        )
    ],
    [_kill("k0", "ghost")],
    [_ev("s0x", "series-!started-game", {"id": "S"}, {"id": "g0"})],
    # the replayed game g1
    [_ev("s1", "series-started-game", {"id": "S"}, {"id": "g1"})],
    [
        _ev(
            "r1",
            "game-started-round",
            {"id": "g1"},
            {"id": "round-1", "state": {"sequenceNumber": 1}},
        )
    ],
    [_freezetime_end("g1")],
    [_kill("k1", "operator")],
    [_kill("k2", "sheriff")],
    [_ev("k2x", "player-!killed-player", {"id": "p1"}, {"id": "p2"})],  # undoes k2
    [
        _ev(
            "a1",
            "player-used-ability",
            {"id": "p1", "state": _player("p1", "A", "attacker", 5, 6)},
            {"id": "tailwind"},
        )
    ],
    [
        _ev(
            "w1",
            "team-won-round",
            {"id": "A", "stateDelta": {"round": {"winType": "opponentEliminated"}}},
            {"id": "round-1", "state": {"sequenceNumber": 1}},
        )
    ],
]

SUPPLEMENT = [
    {
        "grid_event_id": "a1",
        "in_grid": True,
        "slot": "ABILITY_2",
        "quality": "ok",
        "interpolated": {"position": {"x": 10, "y": 20, "z": 30}, "view": {"x": 1, "y": 0, "z": 0}},
    }
]


def _fake_repo(tmp_path):
    _write_zst(
        tmp_path / "val" / "events_S_grid.jsonl.zst",
        [{"occurredAt": f"t{i}", "events": evs} for i, evs in enumerate(FEED)],
    )
    _write_zst(tmp_path / "val-ability-supplements" / "S.jsonl.zst", SUPPLEMENT)
    (tmp_path / "val" / "series.csv").write_text(
        "series_id,event,stage,scheduled_start,teams,file,ability_supplement\nS,E,P,t,A vs B,f,s\n",
        encoding="utf-8",
    )
    meta = tmp_path / "meta"
    meta.mkdir()
    for name in ("teams", "players", "characters", "games", "rosters", "tournaments"):
        (meta / f"{name}.csv").write_text("title,x\nval,1\nlol,2\n", encoding="utf-8")
    return tmp_path


def test_parse_series(tmp_path):
    rows = parse_series(_fake_repo(tmp_path), "S")["rows"]

    assert [k["weapon"] for k in rows["kills"]] == ["operator"]  # g0 dropped, k2 undone
    kill = rows["kills"][0]
    assert (kill["game_id"], kill["round_num"], kill["first_kill"]) == ("g1", 1, 1)
    assert (kill["killer_x"], kill["victim_y"]) == (1, 4)

    (rnd,) = rows["rounds"]
    assert (rnd["attack_team_id"], rnd["defense_team_id"]) == ("A", "B")
    assert (rnd["winner_team_id"], rnd["win_type"]) == ("A", "opponentEliminated")

    (cast,) = rows["abilities"]
    assert (cast["ability"], cast["cast_x"], cast["view_x"], cast["grid_x"]) == (
        "tailwind",
        10,
        1,
        5,
    )

    by_player = {r["player_id"]: r for r in rows["loadouts"]}
    assert by_player["p1"]["has_operator"] == 1 and by_player["p1"]["weapons"] == "classic,operator"
    assert by_player["p2"]["has_operator"] == 0


def test_build_cache_writes_sqlite(tmp_path):
    repo = GridRepo(_fake_repo(tmp_path / "data"))
    db = tmp_path / "out.sqlite"
    summary = build_cache(db, workers=1, repo=repo, progress=False)
    assert summary["failures"] == {}
    assert summary["rows"]["kills"] == 1
    con = connect(db)
    assert con.execute("SELECT COUNT(*) FROM meta_teams").fetchone()[0] == 1  # val rows only
    assert (
        con.execute("SELECT value FROM build_info WHERE key='series_parsed'").fetchone()[0] == "1"
    )
