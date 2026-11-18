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
    op = sub.add_parser("operator", help="Profile Operator usage per player")
    op.add_argument("--team", help="Team ID or exact name, e.g. 79 or Cloud9 (default: all)")
    op.add_argument("--map", dest="map_name", help="Only this map, e.g. ascent")
    op.add_argument("--min-op-rounds", type=int, default=20, help="Hide players below this")
    op.add_argument("--top", type=int, default=25, help="Show at most this many players")
    build = sub.add_parser(
        "build-cache", help="Extract the GRID data into data/cache/nunyaintel.sqlite"
    )
    build.add_argument("--series", nargs="*", help="Only these series IDs (default: all)")
    build.add_argument("--workers", type=int, default=None, help="Parallel processes")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "build-cache":
        import json

        from nunyaintel.data.extract import build_cache

        summary = build_cache(series_ids=args.series, workers=args.workers)
        print(json.dumps(summary, indent=2))
        return 1 if summary["failures"] else 0
    if args.command == "operator":
        from nunyaintel.data.extract import connect
        from nunyaintel.operator_profiler.profiler import (
            format_table,
            profile_players,
            resolve_team,
        )

        con = connect()
        team_id = resolve_team(con, args.team) if args.team else None
        profiles = profile_players(
            con, team_id=team_id, map_name=args.map_name, min_op_rounds=args.min_op_rounds
        )
        print(format_table(profiles[: args.top]))
        return 0
    print(f"'{args.command}' is not implemented yet. See TASKS.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
