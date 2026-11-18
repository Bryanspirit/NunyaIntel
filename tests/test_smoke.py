from nunyaintel import __version__
from nunyaintel.__main__ import main
from nunyaintel.data import Match, Team
from nunyaintel.operator_profiler.profiler import OperatorProfile
from nunyaintel.scouting.report import build_report


def test_version():
    assert __version__ == "0.1.0"


def test_cli_help_exits_cleanly():
    assert main([]) == 0


def test_build_report_counts_matches():
    teams = (Team("c9", "Cloud9"), Team("x", "Opponent"))
    report = build_report("c9", [Match("m1", "Ascent", teams)])
    assert report.matches_analysed == 1


def test_operator_profile_handles_zero_rounds():
    assert OperatorProfile("p1").kills_per_op_round == 0.0
