from nunyaintel import __version__
from nunyaintel.__main__ import main
from nunyaintel.operator_profiler.profiler import OperatorProfile


def test_version():
    assert __version__ == "0.1.0"


def test_cli_help_exits_cleanly():
    assert main([]) == 0


def test_operator_profile_handles_zero_rounds():
    assert OperatorProfile("p1").kills_per_op_round == 0.0
