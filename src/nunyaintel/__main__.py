"""Command-line entry point: ``python -m nunyaintel`` or ``nunyaintel``."""

from __future__ import annotations

import argparse

from nunyaintel import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nunyaintel", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("scout", help="Generate a scouting report for a team (TODO)")
    sub.add_parser("utility", help="Analyse utility placement (TODO)")
    sub.add_parser("operator", help="Profile Operator usage (TODO)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    print(f"'{args.command}' is not implemented yet. See TASKS.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
