"""`nunyaintel doctor` tests: the failure paths a judge's machine might hit."""

import socket

from nunyaintel import doctor
from nunyaintel.doctor import FAIL, OK, WARN, Check


def test_missing_data_repo_says_how_to_fix(monkeypatch, tmp_path):
    monkeypatch.setenv("STL_DATA_DIR", str(tmp_path / "nowhere"))
    c = doctor.check_data_repo()
    assert c.status == FAIL and "git clone" in c.fix


def test_data_repo_found(monkeypatch, tmp_path):
    (tmp_path / "val").mkdir()
    (tmp_path / "val" / "series.csv").write_text("header\na\nb\n", encoding="utf-8")
    monkeypatch.setenv("STL_DATA_DIR", str(tmp_path))
    c = doctor.check_data_repo()
    assert c.status == OK and "2 VALORANT series" in c.detail


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
