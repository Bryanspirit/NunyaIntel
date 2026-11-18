"""`nunyaintel doctor` tests: the failure paths a judge's machine might hit."""

import socket

from nunyaintel import doctor
from nunyaintel.doctor import FAIL, OK, WARN, Check


def test_missing_data_repo_says_how_to_fix(monkeypatch, tmp_path):
    monkeypatch.setenv("STL_DATA_DIR", str(tmp_path / "nowhere"))
    c = doctor.check_data_repo()
    assert c.status == FAIL and "git clone" in c.fix


def _fake_data_repo(root, with_meta=True):
    (root / "val").mkdir(parents=True)
    (root / "val" / "series.csv").write_text("header\na\nb\n", encoding="utf-8")
    (root / "val-ability-supplements").mkdir()
    if with_meta:
        (root / "meta").mkdir()
        (root / "meta" / "games.csv").write_text("title\n", encoding="utf-8")


def test_data_repo_found(monkeypatch, tmp_path):
    _fake_data_repo(tmp_path)
    monkeypatch.setenv("STL_DATA_DIR", str(tmp_path))
    c = doctor.check_data_repo()
    assert c.status == OK and "2 VALORANT series" in c.detail


def test_sparse_checkout_without_meta_is_caught(monkeypatch, tmp_path):
    """Rehearsal finding: the data README's sparse-checkout example omits meta/."""
    _fake_data_repo(tmp_path, with_meta=False)
    monkeypatch.setenv("STL_DATA_DIR", str(tmp_path))
    c = doctor.check_data_repo()
    assert c.status == FAIL and "meta/" in c.detail and "sparse-checkout set" in c.fix


def test_run_reports_crashing_check_as_fail():
    def boom() -> Check:
        raise RuntimeError("kaput")

    results, code = doctor.run([lambda: Check("fine", OK, "yes"), boom])
    assert [r.status for r in results] == [OK, FAIL] and "kaput" in results[1].detail
    assert code == 1


def test_report_shows_fixes_and_verdict():
    text = doctor.report(
        [Check("A", OK, "good", "never shown"), Check("B", WARN, "meh", "do this")]
    )
    assert "fix: do this" in text and "never shown" not in text
    assert "Ready (1 warning(s))" in text
    failing = doctor.report([Check("C", FAIL, "bad", "fix it")])
    assert "1 problem(s) to fix" in failing


def test_version_tuple():
    assert doctor._version_tuple("v24.15.0") == (24, 15)
    assert doctor._version_tuple("22.12.1\n") >= doctor.MIN_NODE


def test_port_free_and_taken():
    with socket.socket() as s:  # grab a free port, then check it while we hold it
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        taken = doctor.check_port(port)
    assert taken.status == WARN and "--port" in taken.fix  # held by a non-NunyaIntel socket
    assert doctor.check_port(port).status == OK  # released again


def test_partial_extract_warns(monkeypatch, tmp_path):
    """Rehearsal finding: a `build-cache --series ...` extract looked 'ok' but holds few matches."""
    import sqlite3

    from nunyaintel.data import extract

    data = tmp_path / "data"
    _fake_data_repo(data)  # its series.csv lists 2 series
    monkeypatch.setenv("STL_DATA_DIR", str(data))
    db = tmp_path / "x.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE build_info (key TEXT, value TEXT)")
    con.executemany(
        "INSERT INTO build_info VALUES (?, ?)",
        [("schema_version", str(extract.SCHEMA_VERSION)), ("series_parsed", "1")],
    )
    con.commit()
    con.close()
    monkeypatch.setattr(extract, "DEFAULT_DB", db)

    c = doctor.check_extract()
    assert c.status == WARN and "partial (1 of 2 series)" in c.detail
