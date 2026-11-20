"""FastAPI app: the analysis functions, served as JSON for the React frontend.

Design notes
------------
- Every endpoint is a thin wrapper: parse query parameters -> call the same functions the CLI
  uses -> convert the dataclasses to plain dicts. No analysis logic lives here.
- The ``_xxx()`` converters spell out each JSON shape explicitly. They are the contract with the
  frontend (``web/src/api.ts`` mirrors them as TypeScript types).
- Positions are sent both as game coordinates (x, y) and as minimap coordinates (u, v in 0..1),
  so the frontend can draw without knowing any game geometry.
- One read-only SQLite connection per request (FastAPI's ``Depends`` with ``yield`` opens it
  before the endpoint runs and closes it afterwards).
- The data is licensed: this server is for local use / the judges' demo only. Don't deploy it.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from nunyaintel import __version__
from nunyaintel.data.extract import DEFAULT_DB, connect, resolve_team
from nunyaintel.maps import DEFAULT_PATH as DEFAULT_MAPS
from nunyaintel.maps import MINIMAP_DIR, MapInfo, download_minimap, load_maps, minimap_path
from nunyaintel.operator_profiler import angles as op_angles
from nunyaintel.operator_profiler import profiler as op_prof
from nunyaintel.scouting import economy_report, overview, sites
from nunyaintel.scouting.overview import SideRecord
from nunyaintel.scouting.team_rounds import load_team_rounds
from nunyaintel.utility import effectiveness, lineups, placement

AIM_ARROW_CM = 1500.0  # lineup aim arrows are drawn 15 m long


# --- converters: dataclass -> JSON-ready dict -----------------------------------------------


def _record(rec: SideRecord) -> dict[str, Any]:
    return {"won": rec.won, "played": rec.played, "win_rate": rec.win_rate}


def _uv(map_info: MapInfo | None, x: float, y: float) -> dict[str, float]:
    if map_info is None:
        return {}
    u, v = map_info.to_minimap(x, y)
    return {"u": u, "v": v}


def _team(con: sqlite3.Connection, team: str) -> dict[str, str]:
    try:
        team_id = resolve_team(con, team)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    row = con.execute("SELECT name FROM meta_teams WHERE team_id = ?", (team_id,)).fetchone()
    return {"id": team_id, "name": row[0] if row else team_id}


def _names(con: sqlite3.Connection) -> dict[str, str]:
    return dict(con.execute("SELECT player_id, name FROM meta_players").fetchall())


# --- response cache ------------------------------------------------------------------------


class ResponseCache:
    """Memoize successful GET /api/... responses, least-recently-used first out.

    The extract is read-only, so the same question always gets the same answer until it's
    rebuilt. The key includes the extract file's modification time, so a rebuild makes every
    old entry miss automatically. Capped by total bytes (memory is tight on some machines).
    """

    def __init__(self, max_bytes: int = 32 * 1024 * 1024) -> None:
        from collections import OrderedDict

        self.max_bytes = max_bytes
        self.size = 0
        self.items: OrderedDict[tuple, tuple[bytes, str]] = OrderedDict()
        self.hits = self.misses = 0

    def get(self, key: tuple) -> tuple[bytes, str] | None:
        item = self.items.get(key)
        if item is None:
            self.misses += 1
            return None
        self.items.move_to_end(key)  # most recently used
        self.hits += 1
        return item

    def put(self, key: tuple, body: bytes, media_type: str) -> None:
        if len(body) > self.max_bytes:
            return
        if key in self.items:
            self.size -= len(self.items.pop(key)[0])
        self.items[key] = (body, media_type)
        self.size += len(body)
        while self.size > self.max_bytes:  # evict least recently used
            _, (old, _) = self.items.popitem(last=False)
            self.size -= len(old)


# --- app factory ---------------------------------------------------------------------------


def create_app(
    db_path: Path = DEFAULT_DB,
    maps_path: Path = DEFAULT_MAPS,
    static_dir: Path | None = None,
    baselines_path: Path | None = None,
    minimap_dir: Path = MINIMAP_DIR,
) -> FastAPI:
    """Build the app. Tests pass their own small database and map file.

    ``static_dir``: the built React app (``web/dist``). If given and present, it's served at
    ``/``, so one process serves both the page and the API (the one-command demo).
    """
    app = FastAPI(title="NunyaIntel API", version=__version__)
    if baselines_path is None:
        from nunyaintel.insights import BASELINES_PATH as baselines_path

    def get_con() -> Iterator[sqlite3.Connection]:
        # one connection per request; opened and used on possibly different worker threads
        con = connect(db_path, check_same_thread=False)
        try:
            yield con
        finally:
            con.close()

    def get_map(name: str | None) -> MapInfo | None:
        if not name:
            return None
        maps = load_maps(maps_path)
        if name.lower() not in maps:
            raise HTTPException(404, f"No map data for {name!r}")
        return maps[name.lower()]

    db = Depends(get_con)
    cache = ResponseCache()
    app.state.cache = cache

    @app.middleware("http")
    async def cache_api_responses(request: Request, call_next):
        """Serve repeated GET /api/... requests from memory; X-Cache says HIT or MISS."""
        if request.method != "GET" or not request.url.path.startswith("/api/"):
            return await call_next(request)
        try:
            version = Path(db_path).stat().st_mtime_ns  # a rebuilt extract = new version
        except OSError:
            version = 0
        key = (request.url.path, tuple(sorted(request.query_params.multi_items())), version)
        hit = cache.get(key)
        if hit is not None:
            body, media_type = hit
            return Response(body, media_type=media_type, headers={"X-Cache": "HIT"})
        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        media_type = response.media_type or response.headers.get("content-type", "")
        if response.status_code == 200:
            cache.put(key, body, media_type)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        headers["X-Cache"] = "MISS"
        return Response(body, status_code=response.status_code, headers=headers,
                        media_type=media_type)  # fmt: skip

    @app.get("/api/meta")
    def meta(con: sqlite3.Connection = db) -> dict[str, Any]:
        """Teams (with match counts and dates) and maps, to fill the pickers."""
        teams = [
            {
                "id": t,
                "name": n,
                "series": int(s or 0),
                "first_seen": f,
                "last_seen": last,
            }
            for t, n, s, f, last in con.execute(
                "SELECT team_id, name, series_count, first_seen, last_seen FROM meta_teams "
                "ORDER BY lower(name)"
            )
        ]
        played = {r[0] for r in con.execute("SELECT DISTINCT lower(map) FROM meta_games")}
        maps = sorted(played & set(load_maps(maps_path)))
        return {"version": __version__, "teams": teams, "maps": maps}

    @app.get("/api/maps/{name}")
    def map_info(name: str) -> dict[str, Any]:
        """Minimap image URL and named callouts (with minimap u, v) for one map."""
        m = get_map(name)
        assert m is not None
        return {
            "name": m.name,
            # served by us (cached locally), so the app works offline; original kept for reference
            "minimap_url": f"/api/maps/{m.name}/minimap",
            "minimap_source": m.minimap_url,
            "callouts": [
                {"name": c.name, "super_region": c.super_region, "region": c.region,
                 "x": c.x, "y": c.y, **_uv(m, c.x, c.y)}
                for c in m.callouts
            ],
        }  # fmt: skip

    @app.get("/api/maps/{name}/minimap")
    def minimap(name: str, source: str | None = None, con: sqlite3.Connection = db) -> Response:
        """The map's background image, in order of preference:

        1. the real minimap image, cached locally (downloaded once);
        2. downloaded now, if the image server is reachable;
        3. a map drawn from our own position data (``silhouette.py``), cached as SVG. This
           works fully offline, e.g. behind a firewall that blocks the image server.
        """
        from nunyaintel import silhouette

        m = get_map(name)
        assert m is not None
        png = minimap_path(m.name, minimap_dir)
        svg = png.with_suffix(".svg")
        if source == "data":  # ?source=data: always the data-drawn map (to compare / demo)
            if not svg.exists():
                svg.parent.mkdir(parents=True, exist_ok=True)
                svg.write_text(silhouette.build(con, m), encoding="utf-8")
            return FileResponse(
                svg, media_type="image/svg+xml", headers={"X-Minimap": "drawn-from-data"}
            )
        if png.exists():
            return FileResponse(png, media_type="image/png")
        try:
            download_minimap(m, minimap_dir)
            return FileResponse(png, media_type="image/png")
        except OSError:
            pass
        if not svg.exists():
            svg.parent.mkdir(parents=True, exist_ok=True)
            svg.write_text(silhouette.build(con, m), encoding="utf-8")
        return FileResponse(
            svg, media_type="image/svg+xml", headers={"X-Minimap": "drawn-from-data"}
        )

    @app.get("/api/maps/{name}/floor")
    def map_floor(name: str, con: sqlite3.Connection = db) -> dict[str, Any]:
        """Walkable floor drawn from the data, as runs [row, start, length] on a grid (3D walls)."""
        from nunyaintel import silhouette

        m = get_map(name)
        assert m is not None
        return {"map": m.name, "grid": silhouette.GRID, "runs": silhouette.floor_runs(con, m)}

    @app.get("/api/scout")
    def scout(
        team: str,
        map: str | None = None,
        since: str | None = None,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """T1 + T2 (+ T3 when a map is given): the scouting report as data."""
        tm = _team(con, team)
        m = get_map(map)
        rounds = load_team_rounds(con, tm["id"], map_name=map, since=since)
        out: dict[str, Any] = {
            "team": tm,
            "filters": {"map": map, "since": since},
            "rounds": len(rounds),
            "games": len({r.game_id for r in rounds}),
            "first": rounds[0].game_started_at if rounds else None,
            "last": rounds[-1].game_started_at if rounds else None,
        }
        if not rounds:
            return out
        out["maps"] = [
            {"map": r.map_name, "games": r.games, "games_won": r.games_won,
             "rounds_won": r.rounds_won, "rounds_lost": r.rounds_lost,
             "round_win_rate": r.round_win_rate,
             "attack": _record(r.attack), "defense": _record(r.defense)}
            for r in overview.map_records(rounds)
        ]  # fmt: skip
        out["sides"] = {s: _record(r) for s, r in overview.side_records(rounds).items()}
        out["win_types"] = {
            side: {k: dict(c) for k, c in outcome.items()}
            for side, outcome in overview.win_types(rounds).items()
        }
        ps = economy_report.pistol_stats(rounds)
        out["pistol"] = {
            "by_side": {s: _record(r) for s, r in ps.pistols.items()},
            "conversions": _record(ps.conversions),
            "breaks": _record(ps.breaks),
        }
        matrix = economy_report.buy_matrix(rounds)
        out["economy"] = {
            "eco_upsets": _record(economy_report.eco_upsets(matrix)),
            "anti_eco": _record(economy_report.anti_eco(matrix)),
            "matrix": [{"own": o, "opp": p, **_record(r)} for (o, p), r in matrix.items()],
        }
        if m is not None:
            rep = sites.site_report(con, tm["id"], rounds, m)
            duels = sites.opening_duels_by_region(con, tm["id"], rounds, m)

            def site_rows(stats: dict[str, sites.SiteStats]) -> list[dict[str, Any]]:
                return [
                    {"site": s, **_record(st.rounds), "median_plant_time_s": st.median_plant_time_s}
                    for s, st in sorted(stats.items(), key=lambda kv: (kv[0] == "no plant", kv[0]))
                ]

            out["sites"] = {
                "attack_rounds": rep.attack_rounds,
                "defense_rounds": rep.defense_rounds,
                "attack": site_rows(rep.attack),
                "defense": site_rows(rep.defense),
                "plants": [
                    {"key": f"{p.game_id}:{p.round_num}", "side": p.side, "won": p.won,
                     "site": p.site, "time_s": p.time_s,
                     "by_us": p.planter_team_id == tm["id"], "x": p.x, "y": p.y,
                     **_uv(m, p.x, p.y)}
                    for p in sites.plants(con, rounds, m)
                ],
                "setups": [
                    {"player_id": s.player_id, "name": s.name, "side": s.side, "agent": s.agent,
                     "rounds_played": s.rounds_played, "rounds_seen": s.rounds_seen,
                     "regions": [{"region": k, "count": v} for k, v in s.regions.most_common()]}
                    for s in sites.default_setups(con, tm["id"], rounds, m)
                ],
                "opening_duels": {
                    side: [{"region": k, **_record(v)} for k, v in
                           sorted(regs.items(), key=lambda kv: -kv[1].played)]
                    for side, regs in duels.items()
                },
            }  # fmt: skip
        return out

    @app.get("/api/findings")
    def findings(
        team: str,
        map: str | None = None,
        since: str | None = None,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """P3 Key findings: the team's most unusual numbers vs. the league, plus map findings."""
        from nunyaintel import insights

        tm = _team(con, team)
        if map:
            get_map(map)  # 404 for an unknown map
        panel = insights.key_findings(
            con, tm["id"], map_name=map, since=since,
            baselines=insights.load_baselines(con, baselines_path), maps_path=maps_path,
        )  # fmt: skip
        return {"team": tm, **panel}

    @app.get("/api/replay")
    def replay(
        team: str,
        map: str,
        side: str | None = None,
        since: str | None = None,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """Every event of the team's rounds on a map, timed from the buy-phase end (Replay tab)."""
        from nunyaintel import timeline

        m = get_map(map)
        assert m is not None
        tm = _team(con, team)
        return {
            "team": tm,
            "map": m.name,
            **timeline.replay(con, tm["id"], m, side=side, since=since),
        }

    @app.get("/api/matches")
    def matches(team: str, con: sqlite3.Connection = db) -> dict[str, Any]:
        """The team's maps, newest first (for the match-story picker)."""
        from nunyaintel import match

        return {"games": match.games(con, _team(con, team)["id"])}

    @app.get("/api/match")
    def match_story(team: str, game: str, con: sqlite3.Connection = db) -> dict[str, Any]:
        """One map round by round: score, buys, kills, plants, win-chance swings."""
        from nunyaintel import match

        try:
            return match.story(con, _team(con, team)["id"], game, maps_path=maps_path)
        except KeyError:
            raise HTTPException(404, f"No map {game!r} for this team") from None

    @app.get("/api/players")
    def players(q: str = "", limit: int = 20, con: sqlite3.Connection = db) -> dict[str, Any]:
        """Player search by name (for the compare picker)."""
        rows = con.execute(
            "SELECT player_id, name, latest_team_name FROM meta_players "
            "WHERE name LIKE ? ORDER BY CAST(series_count AS INTEGER) DESC LIMIT ?",
            (f"%{q}%", min(limit, 50)),
        ).fetchall()
        return {"players": [{"id": p, "name": n, "team": t} for p, n, t in rows]}

    @app.get("/api/player")
    def player(player: str, map: str | None = None, con: sqlite3.Connection = db) -> dict[str, Any]:
        """One player's profile (agents, fights, weapons, Op, utility, heatmap points)."""
        from nunyaintel import player as player_mod

        try:
            return player_mod.profile(con, player, map_info=get_map(map))
        except KeyError:
            raise HTTPException(404, f"Unknown player: {player!r}") from None

    @app.get("/api/gameplan")
    def gameplan(
        team: str, opponent: str | None = None, map: str | None = None, con: sqlite3.Connection = db
    ) -> dict[str, Any]:
        """Written advice for playing an opponent, every line with its evidence."""
        from nunyaintel import gameplan as gp
        from nunyaintel import predict

        a = _team(con, team)["id"]
        b = _team(con, opponent)["id"] if opponent else predict.frequent_opponent(con, a)
        if b is None:
            raise HTTPException(404, "No opponent found for this team")
        return gp.plan(con, a, b, map_info=get_map(map), maps_path=maps_path)

    @app.get("/api/matchup-report")
    def matchup_report(
        team: str,
        opponent: str | None = None,
        map: str | None = None,
        since: str | None = None,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """Two teams side by side: Elo, habit collisions, map pool, sites, head-to-head."""
        from nunyaintel import matchup_report as mr
        from nunyaintel import predict

        a = _team(con, team)["id"]
        b = _team(con, opponent)["id"] if opponent else predict.frequent_opponent(con, a)
        if b is None:
            raise HTTPException(404, "No opponent found for this team")
        return mr.report(con, a, b, map_info=get_map(map), since=since)

    @app.get("/api/predict/matchup")
    def predict_matchup(
        team: str, opponent: str | None = None, con: sqlite3.Connection = db
    ) -> dict[str, Any]:
        """Elo map-win probability, with the model's tested accuracy and calibration."""
        from nunyaintel import predict

        a = _team(con, team)["id"]
        b = _team(con, opponent)["id"] if opponent else predict.frequent_opponent(con, a)
        if b is None:
            raise HTTPException(404, "No opponent found for this team")
        return predict.matchup(con, a, b)

    @app.get("/api/predict/next-buy")
    def predict_next_buy(team: str, con: sqlite3.Connection = db) -> dict[str, Any]:
        """Next-round buy by situation: league and team distributions, plus tested accuracy."""
        from nunyaintel import predict

        return predict.next_buy(con, _team(con, team)["id"])

    @app.get("/api/predict/round")
    def predict_round(con: sqlite3.Connection = db) -> dict[str, Any]:
        """Round win chance by players alive and spike: the grids, plus the tested accuracy."""
        from nunyaintel import winprob

        m = winprob.model(con)
        return {
            "grid": {"no_plant": m.grid(0), "planted": m.grid(1)},
            "model": winprob.evaluate(con),
        }

    @app.get("/api/operator")
    def operator(
        team: str | None = None,
        map: str | None = None,
        min_op_rounds: int = 1,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """O1 profiles + O2 economy and opening duels."""
        team_id = _team(con, team)["id"] if team else None
        f = {"team_id": team_id, "map_name": map, "min_op_rounds": min_op_rounds}
        return {
            "profiles": [
                {"player_id": p.player_id, "name": p.name, "team_id": p.team_id,
                 "rounds_played": p.rounds_played, "rounds_with_op": p.rounds_with_op,
                 "op_kills": p.op_kills, "first_bloods_with_op": p.first_bloods_with_op,
                 "deaths_with_op": p.deaths_with_op, "rounds_won_with_op": p.rounds_won_with_op,
                 "op_buy_rate": p.op_buy_rate, "kills_per_op_round": p.kills_per_op_round,
                 "op_kd": p.op_kd, "op_round_win_rate": p.op_round_win_rate}
                for p in op_prof.profile_players(con, **f)
            ],
            "economy": [
                {"player_id": r.player_id, "name": r.name, "team_id": r.team_id,
                 "economy": r.economy, "rounds": r.rounds, "rounds_with_op": r.rounds_with_op,
                 "op_rate": r.op_rate}
                for r in op_prof.op_rate_by_economy(con, **f)
            ],
            "duels": [
                {"player_id": d.player_id, "name": d.name, "team_id": d.team_id,
                 "op_rounds": d.op_rounds, "op_duels": d.op_duels,
                 "op_duels_won": d.op_duels_won, "op_duel_rate": d.op_duel_rate,
                 "op_duel_win_rate": d.op_duel_win_rate, "other_rounds": d.other_rounds,
                 "other_duel_rate": d.other_duel_rate,
                 "other_duel_win_rate": d.other_duel_win_rate}
                for d in op_prof.opening_duels(con, **f)
            ],
        }  # fmt: skip

    @app.get("/api/operator/angles")
    def operator_angles(
        map: str,
        team: str | None = None,
        side: str | None = None,
        player: str | None = None,
        precise: bool = False,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """O3: Operator angles, with shooter and target points for drawing."""
        m = get_map(map)
        assert m is not None
        team_id = _team(con, team)["id"] if team else None
        shots = op_angles.load_op_shots(con, map, team_id=team_id, player_id=player, side=side)
        found = op_angles.find_angles(shots, m) if precise else op_angles.region_angles(shots, m)
        names = _names(con)
        rows = []
        for a in found:
            x = statistics.fmean(s.x for s in a.shots)
            y = statistics.fmean(s.y for s in a.shots)
            tx = statistics.fmean(s.target_x for s in a.shots)
            ty = statistics.fmean(s.target_y for s in a.shots)
            target = _uv(m, tx, ty)
            rows.append(
                {"player_id": a.player_id, "name": names.get(a.player_id, a.player_id),
                 "side": a.side, "from_region": a.from_region, "to_region": a.to_region,
                 "shots": len(a.shots), "kills": a.kills, "series": a.series,
                 "median_distance_m": a.median_distance_m, "median_time_s": a.median_time_s,
                 "x": x, "y": y, **_uv(m, x, y),
                 "target_x": tx, "target_y": ty,
                 "target_u": target["u"], "target_v": target["v"],
                 "uses": [[f"{sh.game_id}:{sh.round_num}", round(sh.time_s or 0, 1)]
                          for sh in a.shots[:20]]}
            )  # fmt: skip
        return {"map": m.name, "shots": len(shots), "angles": rows}

    @app.get("/api/utility")
    def utility(
        map: str,
        team: str | None = None,
        side: str | None = None,
        precise_only: bool = False,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """U1: per-ability usage summary."""
        team_id = _team(con, team)["id"] if team else None
        usages = placement.load_utility(
            con, map_name=map, team_id=team_id, side=side, precise_only=precise_only
        )
        return {
            "casts": len(usages),
            "rounds": len({(u.series_id, u.game_id, u.round_num) for u in usages}),
            "summary": [
                {"agent": s.agent, "ability": s.ability, "slot": s.slot, "casts": s.casts,
                 "rounds": s.rounds, "per_round": s.per_round,
                 "buy_phase_share": s.buy_phase_share, "median_time_s": s.median_time_s}
                for s in placement.summarize(usages)
            ],
        }  # fmt: skip

    @app.get("/api/utility/lineups")
    def utility_lineups(
        map: str,
        team: str | None = None,
        side: str | None = None,
        radius: float = Query(150.0, gt=0),
        angle: float = Query(10.0, gt=0, le=180),
        min_matches: int = Query(2, ge=1),
        score: bool = True,
        con: sqlite3.Connection = db,
    ) -> dict[str, Any]:
        """U2 lineups (+ U3 scores), with cast spot and a 15 m aim arrow for drawing."""
        m = get_map(map)
        assert m is not None
        team_id = _team(con, team)["id"] if team else None
        usages = placement.load_utility(con, map_name=map, team_id=team_id, side=side)
        found = lineups.find_lineups(
            usages, radius_cm=radius, max_angle_deg=angle, min_series=min_matches
        )
        scored = {id(s.lineup): s for s in effectiveness.score_lineups(con, found)} if score else {}
        rows = []
        for lu in found:
            ax, ay = lu.x + lu.view_x * AIM_ARROW_CM, lu.y + lu.view_y * AIM_ARROW_CM
            aim = _uv(m, ax, ay)
            row: dict[str, Any] = {
                "team_id": lu.team_id, "side": lu.side, "agent": lu.agent,
                "ability": lu.ability, "casts": lu.casts, "series": lu.series,
                "rounds": lu.rounds, "rounds_won": lu.rounds_won,
                "round_win_rate": lu.round_win_rate, "median_time_s": lu.median_time_s,
                "yaw_deg": lu.yaw_deg, "x": lu.x, "y": lu.y, "z": lu.z, **_uv(m, lu.x, lu.y),
                "aim_u": aim["u"], "aim_v": aim["v"],
                "region": m.region_of(lu.x, lu.y).name,
                # where it was used, for "open in Replay": [round key, seconds], newest first
                "uses": [
                    [f"{u.game_id}:{u.round_num}", round(u.time_s or 0, 1)]
                    for u in sorted(lu.members, key=lambda u: u.occurred_at, reverse=True)[:20]
                ],
            }  # fmt: skip
            s = scored.get(id(lu))
            if s is not None:
                row.update(
                    baseline=s.baseline,
                    adjusted_win_rate=s.adjusted_win_rate,
                    score=s.score,
                    damage_per_cast=s.damage_per_cast,
                    in_round_casts=s.in_round_casts,
                    window_kills=s.window_kills,
                    window_deaths=s.window_deaths,
                )
            rows.append(row)
        if score:
            rows.sort(key=lambda r: -r.get("score", 0.0))
        return {"map": m.name, "casts": len(usages), "lineups": rows}

    # The React app: mounted LAST, so every /api/... route above is matched before it.
    # html=True serves index.html for "/". The app keeps its state in the query string
    # (?team=79&map=lotus), so there are no client-side paths that would need a fallback.
    if static_dir is not None and (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")

    return app
