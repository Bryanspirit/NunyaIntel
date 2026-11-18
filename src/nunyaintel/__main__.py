"""Command-line entry point: ``python -m nunyaintel`` or ``nunyaintel``."""

from __future__ import annotations

import argparse

from nunyaintel import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nunyaintel", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sc = sub.add_parser("scout", help="Scouting report: maps, sides, win types, economy")
    sc.add_argument("--team", required=True, help="Team ID or exact name, e.g. 79 or Cloud9")
    sc.add_argument("--map", dest="map_name", help="Only this map, e.g. lotus")
    sc.add_argument("--since", help="Only maps played on/after this date, e.g. 2025-06-01")
    ut = sub.add_parser("utility", help="How a team uses each agent's abilities on a map")
    ut.add_argument("--team", help="Team ID or exact name, e.g. 79 or Cloud9 (default: all)")
    ut.add_argument("--map", dest="map_name", required=True, help="Map, e.g. ascent")
    ut.add_argument("--side", choices=["attacker", "defender"], help="Only this side")
    ut.add_argument("--player", help="Only this player ID")
    ut.add_argument("--precise-only", action="store_true", help="Skip 1 Hz (VCT Americas 2025)")
    ut.add_argument("--lineups", action="store_true", help="Find repeated setups (U2)")
    ut.add_argument("--radius", type=float, default=150.0, help="Lineup spot radius in cm")
    ut.add_argument("--angle", type=float, default=10.0, help="Lineup max aim difference, deg")
    ut.add_argument("--min-matches", type=int, default=2, help="Lineup must recur in N matches")
    ut.add_argument("--top", type=int, default=30, help="Show at most this many lineups")
    ut.add_argument("--score", action="store_true", help="With --lineups: rank by effectiveness")
    op = sub.add_parser("operator", help="Profile Operator usage per player")
    op.add_argument("--team", help="Team ID or exact name, e.g. 79 or Cloud9 (default: all)")
    op.add_argument("--map", dest="map_name", help="Only this map, e.g. ascent")
    op.add_argument("--min-op-rounds", type=int, default=20, help="Hide players below this")
    op.add_argument("--top", type=int, default=25, help="Show at most this many players")
    view = op.add_mutually_exclusive_group()
    view.add_argument("--economy", action="store_true", help="Op rate per team economy state")
    view.add_argument("--duels", action="store_true", help="Opening duels with vs. without Op")
    view.add_argument("--angles", action="store_true", help="Angles held with the Op (needs --map)")
    op.add_argument("--side", choices=["attacker", "defender"], help="With --angles: one side")
    op.add_argument("--player", help="With --angles: only this player ID")
    op.add_argument("--precise", action="store_true", help="With --angles: exact-spot clusters")
    srv = sub.add_parser("serve", help="Run the web API (and the React app once built)")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--host", default="127.0.0.1", help="Keep local: the data is licensed")
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
    if args.command == "serve":
        import uvicorn

        from nunyaintel.api import create_app

        print(f"NunyaIntel API on http://{args.host}:{args.port}  (docs: /docs)")
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0
    if args.command == "scout":
        from nunyaintel.data.extract import connect, resolve_team
        from nunyaintel.scouting.report import build_report

        con = connect()
        team_id = resolve_team(con, args.team)
        print(build_report(con, team_id, map_name=args.map_name, since=args.since))
        return 0
    if args.command == "utility":
        from nunyaintel.data.extract import connect, resolve_team
        from nunyaintel.utility import placement

        con = connect()
        usages = placement.load_utility(
            con,
            map_name=args.map_name,
            team_id=resolve_team(con, args.team) if args.team else None,
            side=args.side,
            player_id=args.player,
            precise_only=args.precise_only,
        )
        rounds = len({(u.series_id, u.game_id, u.round_num) for u in usages})
        print(f"{len(usages)} casts in {rounds} rounds on {args.map_name}\n")
        if args.lineups:
            from nunyaintel.utility import lineups as lu

            found = lu.find_lineups(
                usages,
                radius_cm=args.radius,
                max_angle_deg=args.angle,
                min_series=args.min_matches,
            )
            print(f"{len(found)} lineups\n")
            if args.score:
                from nunyaintel.utility import effectiveness

                scores = effectiveness.score_lineups(con, found)
                print(effectiveness.format_scores(scores[: args.top]))
            else:
                print(lu.format_lineups(found[: args.top]))
        else:
            print(placement.format_summary(placement.summarize(usages)))
        return 0
    if args.command == "operator":
        from nunyaintel.data.extract import connect
        from nunyaintel.operator_profiler import profiler as opp

        con = connect()
        team_id = opp.resolve_team(con, args.team) if args.team else None
        filters = {
            "team_id": team_id,
            "map_name": args.map_name,
            "min_op_rounds": args.min_op_rounds,
        }
        if args.economy:
            rates = opp.op_rate_by_economy(con, **filters)
            top = list(dict.fromkeys((r.player_id, r.team_id) for r in rates))[: args.top]
            print(opp.format_economy_table([r for r in rates if (r.player_id, r.team_id) in top]))
        elif args.angles:
            if not args.map_name:
                parser.error("--angles needs --map")
            from nunyaintel.maps import get_map
            from nunyaintel.operator_profiler import angles as opa

            shots = opa.load_op_shots(
                con, args.map_name, team_id=team_id, player_id=args.player, side=args.side
            )
            map_info = get_map(args.map_name)
            if args.precise:
                found = opa.find_angles(shots, map_info)
            else:
                found = opa.region_angles(shots, map_info)
            names = dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())
            print(f"{len(shots)} Operator hits on {args.map_name}, {len(found)} angles\n")
            print(opa.format_angles(found[: args.top], names))
        elif args.duels:
            print(opp.format_duels_table(opp.opening_duels(con, **filters)[: args.top]))
        else:
            print(opp.format_table(opp.profile_players(con, **filters)[: args.top]))
        return 0
    print(f"'{args.command}' is not implemented yet. See TASKS.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
