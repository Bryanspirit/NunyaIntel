"""P3 Key findings: statistics, ranking and wording on synthetic numbers. No real data."""

import pytest

from nunyaintel import insights
from nunyaintel.insights import _rank_phrase, format_findings, league_findings, z_score


def test_z_score_rewards_sample_size():
    # 15/50 at 30% vs 17.5% is a real signal; 3/4 at 75% vs 50% is mostly noise
    big = z_score(15, 50, 0.175)
    small = z_score(3, 4, 0.5)
    assert big == pytest.approx(2.33, abs=0.01)
    assert small == pytest.approx(1.0, abs=0.01)
    assert big > small
    assert z_score(0, 0, 0.5) == 0.0 and z_score(1, 2, 0.0) == 0.0


def test_rank_phrase():
    assert _rank_phrase(55, 55) == "worst of 55 teams"
    assert _rank_phrase(1, 55) == "best of 55 teams"
    assert _rank_phrase(3, 55) == "top 3 of 55 teams"
    assert _rank_phrase(53, 55) == "bottom 3 of 55 teams"
    assert _rank_phrase(20, 55) == "#20 of 55 teams"
    assert _rank_phrase(1, 3) == ""  # too few teams to rank meaningfully


BASELINES = {
    "league": {"anti_eco_loss": [175, 1000], "pistol_win": [500, 1000]},
    "teams": {
        "us": {"anti_eco_loss": [15, 50], "pistol_win": [25, 50]},
        **{f"t{i}": {"anti_eco_loss": [i, 40], "pistol_win": [20, 40]} for i in range(1, 6)},
    },
}


def test_league_findings_classify_and_rank():
    counts = {"anti_eco_loss": (15, 50), "pistol_win": (25, 50)}
    found = {f.key: f for f in league_findings(counts, BASELINES, "us")}

    anti = found["anti_eco_loss"]  # lower is better, and we're well above the league
    assert anti.kind == "weakness" and anti.z > 2
    assert (anti.rank, anti.ranked_teams) == (6, 6)  # worst: 15/50 is the highest loss rate
    assert "worst of 6 teams" in anti.detail and "15 of 50" in anti.detail

    pistol = found["pistol_win"]  # exactly the league rate: within normal variation
    assert pistol.kind == "tendency" and pistol.z == pytest.approx(0)


def test_small_samples_are_not_shown():
    found = league_findings({"anti_eco_loss": (3, 4)}, BASELINES, "us")  # min_n is 30
    assert found == []


def test_format_findings():
    panel = {
        "maps": 2, "rounds": 40, "map": "lotus", "map_was_chosen": False,
        "league": [league_findings({"anti_eco_loss": (15, 50)}, BASELINES, "us")[0].to_dict()],
        "map_findings": [],
    }  # fmt: skip
    text = format_findings(panel, "Alpha")
    assert text.startswith("KEY FINDINGS: Alpha") and "[-]" in text


def test_baseline_cache_is_tied_to_the_extract_build(tmp_path, monkeypatch):
    calls = []

    def fake_compute(con):
        calls.append(1)
        return {"built_at": "build-1", "league": {}, "teams": {}}

    monkeypatch.setattr(insights, "compute_baselines", fake_compute)
    monkeypatch.setattr(insights, "_built_at", lambda con: built["at"])
    built = {"at": "build-1"}
    path = tmp_path / "b.json"

    insights.load_baselines(None, path)
    insights.load_baselines(None, path)
    assert len(calls) == 1  # second call read the cache

    built["at"] = "build-2"  # the extract was rebuilt: the cache must be ignored
    insights.load_baselines(None, path)
    assert len(calls) == 2
