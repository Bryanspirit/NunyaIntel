"""P9 claims checker: the machinery, on fake claims (real claims need the licensed data)."""

from nunyaintel.claims import Claim, Result, _counts, run, to_markdown


def test_counts_must_match_exactly():
    assert _counts((15, 50), (15, 50)).ok
    assert not _counts((15, 50), (30, 100)).ok  # same 30%, different evidence: a FAIL


def test_run_and_markdown(monkeypatch):
    from nunyaintel import claims

    fake = [
        Claim("good", "README", "a true claim", lambda con: Result(True, "1/2 = 50.0%", 2)),
        Claim("bad", "video", "a stale claim", lambda con: Result(False, "now different")),
        Claim("boom", "README", "a broken check", lambda con: 1 / 0),
    ]
    monkeypatch.setattr(claims, "CLAIMS", fake)
    results = run(None)
    assert [r.ok for _, r in results] == [True, False, False]
    assert "ZeroDivisionError" in results[2][1].measured  # a crash is a FAIL, not a stop

    md = to_markdown(results, "build-1")
    assert "**1 of 3 claims pass**" in md
    assert "| PASS | a true claim *(small sample)* |" in md  # n=2 < 30
    assert "**FAIL**" in md and "extract built build-1" in md
