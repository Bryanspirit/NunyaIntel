"""GRID reader tests use tiny synthetic files only. Never put real hackathon data in tests."""

import json
from compression import zstd

import pytest

from nunyaintel.data.grid import GridRepo, read_jsonl_zst


def _write_zst(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zstd.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "val").mkdir()
    (tmp_path / "meta").mkdir()
    (tmp_path / "val" / "series.csv").write_text(
        "series_id,event,stage,scheduled_start,teams,file,ability_supplement\n"
        "1,Test Event,Playoffs,2025-01-01T00:00:00Z,A vs B,val/events_1_grid.jsonl.zst,\n",
        encoding="utf-8",
    )
    (tmp_path / "meta" / "games.csv").write_text(
        "title,series_id,game_id,team1_id,team2_id\nval,1,g1,10,20\nlol,2,g2,10,30\n",
        encoding="utf-8",
    )
    _write_zst(
        tmp_path / "val" / "events_1_grid.jsonl.zst",
        [{"occurredAt": "t0", "events": [{"type": "grid-started-feed"}]},
         {"occurredAt": "t1", "events": [{"type": "player-killed-player"}]}],
    )
    return GridRepo(tmp_path)


def test_read_jsonl_zst(tmp_path):
    p = tmp_path / "x.jsonl.zst"
    _write_zst(p, [{"a": 1}, {"a": 2}])
    assert [r["a"] for r in read_jsonl_zst(p)] == [1, 2]


def test_series_index(fake_repo):
    assert fake_repo.series()[0].series_id == "1"


def test_series_for_team_filters_to_valorant(fake_repo):
    assert fake_repo.series_for_team("10") == ["1"]


def test_events_stream(fake_repo):
    assert [e["type"] for _, e in fake_repo.events("1")] == [
        "grid-started-feed",
        "player-killed-player",
    ]


def test_missing_repo_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        GridRepo(tmp_path / "nope")
