"""P3: Key findings: the few facts about a team that are most unusual *and* most reliable.

How a finding earns its place
-----------------------------
Each team metric (e.g. "rounds lost on a full buy vs. an eco") is compared with the league
rate using a **z-score**:

    z = (team_rate - league_rate) / sqrt(league_rate * (1 - league_rate) / n)

z counts how many standard errors the team sits from the league. It grows with the gap *and*
with the sample size n, so 15/50 at 30% vs. 17.5% (z = 2.3) beats 3/4 at 75% vs. 50% (z = 1.0).
Findings are sorted by |z|. Each one also gets a rank among teams with enough rounds.

League baselines need every team's numbers (~40 s), so they're computed once per extract build
and cached in ``data/cache/league_baselines.json``. The extract's ``built_at`` invalidates
them automatically after a rebuild.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nunyaintel.config import CACHE_DIR
from nunyaintel.operator_profiler import profiler as op
from nunyaintel.scouting import economy_report as er
from nunyaintel.scouting import overview
from nunyaintel.scouting.team_rounds import TeamRound, load_team_rounds

BASELINES_PATH = CACHE_DIR / "league_baselines.json"
MAX_FINDINGS = 6


@dataclass(frozen=True, slots=True)
class Metric:
    key: str
    label: str  # "rounds lost on a full buy vs. an eco"
    higher_is_better: bool
    min_n: int  # minimum sample for a team to be ranked / shown
    tab: str  # where the details live in the web app


METRICS = [
    Metric("anti_eco_loss", "full-buy rounds lost to an eco or semi-eco", False, 30, "scouting"),
    Metric("eco_upset", "eco rounds won against a full buy", True, 20, "scouting"),
    Metric("pistol_win", "pistol rounds won", True, 20, "scouting"),
    Metric("pistol_conversion", "rounds won right after winning a pistol", True, 15, "scouting"),
    Metric("attack_win", "attack rounds won", True, 150, "scouting"),
    Metric("defense_win", "defense rounds won", True, 150, "scouting"),
    Metric("op_duel_win", "opening duels won while holding an Operator", True, 15, "operator"),
]
METRIC_BY_KEY = {m.key: m for m in METRICS}


def team_counts(rounds: Sequence[TeamRound]) -> dict[str, tuple[int, int]]:
    """(hits, n) per round-based metric for one team's rounds."""
    matrix = er.buy_matrix(rounds)
    anti, upset = er.anti_eco(matrix), er.eco_upsets(matrix)
    ps = er.pistol_stats(rounds)
    sides = overview.side_records(rounds)
    pistols = ps.pistols["attacker"].won + ps.pistols["defender"].won
    pistol_n = ps.pistols["attacker"].played + ps.pistols["defender"].played
    return {
        "anti_eco_loss": (anti.played - anti.won, anti.played),
        "eco_upset": (upset.won, upset.played),
        "pistol_win": (pistols, pistol_n),
        "pistol_conversion": (ps.conversions.won, ps.conversions.played),
        "attack_win": (sides["attacker"].won, sides["attacker"].played),
        "defense_win": (sides["defender"].won, sides["defender"].played),
    }


def _op_duel_counts(con: sqlite3.Connection, team_id: str | None = None) -> dict[str, list[int]]:
    """team_id -> [Op opening duels won, Op opening duels taken] (all players combined)."""
    out: dict[str, list[int]] = {}
    for d in op.opening_duels(con, team_id=team_id):
        acc = out.setdefault(d.team_id, [0, 0])
        acc[0] += d.op_duels_won
        acc[1] += d.op_duels
    return out


def _built_at(con: sqlite3.Connection) -> str:
    """The extract's build time: the cache key for baselines ("" if it isn't recorded)."""
    try:
        row = con.execute("SELECT value FROM build_info WHERE key = 'built_at'").fetchone()
    except sqlite3.OperationalError:  # no build_info table (e.g. a hand-made test database)
        return ""
    return row[0] if row else ""


def compute_baselines(con: sqlite3.Connection) -> dict:
    """Every team's (hits, n) per metric, plus the league totals. Slow (~40 s)."""
    teams = [row[0] for row in con.execute("SELECT team_id FROM meta_teams").fetchall()]
    per_team: dict[str, dict[str, list[int]]] = {}
    for team_id in teams:
        counts = team_counts(load_team_rounds(con, team_id))
        per_team[team_id] = {k: list(v) for k, v in counts.items()}
    for team_id, counts in _op_duel_counts(con).items():
        per_team.setdefault(team_id, {})["op_duel_win"] = counts
    league: dict[str, list[int]] = {}
    for counts in per_team.values():
        for key, (hits, n) in counts.items():
            acc = league.setdefault(key, [0, 0])
            acc[0] += hits
            acc[1] += n
    return {"built_at": _built_at(con), "league": league, "teams": per_team}


_baselines_lock = threading.Lock()  # one ~40 s computation at a time, never two in parallel


def load_baselines(con: sqlite3.Connection, path: Path = BASELINES_PATH) -> dict:
    """Cached baselines for this extract build, computing them the first time.

    Thread-safe: the web server warms this in a background thread at startup, and a request
    arriving meanwhile waits on the lock and then reads the fresh cache, instead of starting
    a second computation.
    """
    built_at = _built_at(con)
    with _baselines_lock:
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("built_at") == built_at:
                return cached
        baselines = compute_baselines(con)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(baselines), encoding="utf-8")
        return baselines


def warm_baselines() -> threading.Thread:
    """Compute/load the league baselines in the background (used by ``nunyaintel serve``)."""
    from nunyaintel.data.extract import connect

    def work() -> None:
        con = connect(check_same_thread=False)
        try:
            load_baselines(con)
        finally:
            con.close()

    thread = threading.Thread(target=work, name="warm-baselines", daemon=True)
    thread.start()
    return thread


def z_score(hits: int, n: int, p0: float) -> float:
    """Standard errors between the team's rate and the league rate p0."""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 0.0
    return (hits / n - p0) / math.sqrt(p0 * (1 - p0) / n)


@dataclass(slots=True)
class Finding:
    key: str
    kind: str  # "strength" | "weakness" | "tendency"
    headline: str
    detail: str
    hits: int
    n: int
    rate: float
    league_rate: float | None = None
    rank: int | None = None  # 1 = best in the league among ranked teams
    ranked_teams: int | None = None
    z: float = 0.0
    tab: str = "scouting"
    map: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _rank(baselines: dict, metric: Metric, team_id: str) -> tuple[int | None, int]:
    rates = []
    for tid, counts in baselines["teams"].items():
        hits, n = counts.get(metric.key, (0, 0))
        if n >= metric.min_n:
            rates.append((hits / n, tid))
    rates.sort(reverse=metric.higher_is_better)  # best first
    for i, (_, tid) in enumerate(rates, 1):
        if tid == team_id:
            return i, len(rates)
    return None, len(rates)


def _rank_phrase(rank: int | None, total: int) -> str:
    if rank is None or total < 5:
        return ""
    if rank == 1:
        return f"best of {total} teams"
    if rank == total:
        return f"worst of {total} teams"
    if rank <= max(1, total // 10):
        return f"top {rank} of {total} teams"
    if rank > total - max(1, total // 10):
        return f"bottom {total - rank + 1} of {total} teams"
    return f"#{rank} of {total} teams"


def league_findings(
    counts: dict[str, tuple[int, int]], baselines: dict, team_id: str
) -> list[Finding]:
    findings = []
    for key, (hits, n) in counts.items():
        metric = METRIC_BY_KEY[key]
        league_hits, league_n = baselines["league"].get(key, (0, 0))
        if n < metric.min_n or not league_n:
            continue
        p0 = league_hits / league_n
        z = z_score(hits, n, p0)
        better = (z > 0) == metric.higher_is_better
        rank, total = _rank(baselines, metric, team_id)
        rank_text = _rank_phrase(rank, total)
        verdict = "strength" if better else "weakness"
        diff = "above" if z > 0 else "below"
        findings.append(
            Finding(
                key=key,
                kind=verdict if abs(z) >= 1.0 else "tendency",
                headline=f"{hits / n:.0%} of {metric.label}",
                detail=(
                    f"{hits} of {n}; league {p0:.1%} ({league_hits} of {league_n}), "
                    f"{abs(z):.1f} standard errors {diff}" + (f"; {rank_text}" if rank_text else "")
                ),
                hits=hits,
                n=n,
                rate=hits / n,
                league_rate=p0,
                rank=rank,
                ranked_teams=total,
                z=z,
                tab=metric.tab,
            )
        )
    return findings


def map_findings(
    con: sqlite3.Connection,
    team_id: str,
    rounds: Sequence[TeamRound],
    map_name: str,
    maps_path: Path | None = None,
) -> list[Finding]:
    """Site-level findings on one map: weakest defended site, attack rounds with no plant."""
    from nunyaintel.maps import DEFAULT_PATH, get_map
    from nunyaintel.scouting.sites import site_report

    map_rounds = [r for r in rounds if r.map_name.lower() == map_name.lower()]
    if not map_rounds:
        return []
    rep = site_report(con, team_id, map_rounds, get_map(map_name, maps_path or DEFAULT_PATH))
    out = []
    # Weakest defended site: compared with the team's own other sites (post-plant holds).
    planted = {s: st.rounds for s, st in rep.defense.items() if s != "no plant"}
    total_won = sum(r.won for r in planted.values())
    total_n = sum(r.played for r in planted.values())
    candidates = [(s, r) for s, r in planted.items() if r.played >= 10]
    if candidates and total_n:
        site, rec = min(candidates, key=lambda kv: kv[1].win_rate)
        others_n = total_n - rec.played
        others = (total_won - rec.won) / others_n if others_n else None
        out.append(
            Finding(
                key="weakest_site",
                kind="weakness",
                headline=f"{site} site is their weakest hold on {map_name.title()}",
                detail=(
                    f"held or retook {rec.won} of {rec.played} ({rec.win_rate:.0%}) when "
                    f"opponents planted {site}"
                    + (f", vs. {others:.0%} on their other sites" if others is not None else "")
                ),
                hits=rec.won,
                n=rec.played,
                rate=rec.win_rate,
                tab="scouting",
                map=map_name,
                extra={"site": site, "share": rec.played / max(1, rep.defense_rounds)},
            )
        )
    no_plant = rep.attack.get("no plant")
    if no_plant and rep.attack_rounds >= 20 and no_plant.rounds.played >= 5:
        rec = no_plant.rounds
        out.append(
            Finding(
                key="no_plant",
                kind="tendency",
                headline=(
                    f"{rec.played / rep.attack_rounds:.0%} of attack rounds on "
                    f"{map_name.title()} end without a plant"
                ),
                detail=f"they win {rec.won} of {rec.played} of those ({rec.win_rate:.0%})",
                hits=rec.won,
                n=rec.played,
                rate=rec.win_rate,
                tab="scouting",
                map=map_name,
            )
        )
    favourite = max(
        ((s, st.rounds) for s, st in rep.attack.items() if s != "no plant"),
        key=lambda kv: kv[1].played,
        default=None,
    )
    if favourite and favourite[1].played >= 10:
        site, rec = favourite
        out.append(
            Finding(
                key="attack_site",
                kind="tendency",
                headline=f"On attack they favour {site} site on {map_name.title()}",
                detail=(
                    f"{rec.played} of {rep.attack_rounds} attack rounds "
                    f"({rec.played / rep.attack_rounds:.0%}) planted {site}; "
                    f"won {rec.won} of them ({rec.win_rate:.0%})"
                ),
                hits=rec.won,
                n=rec.played,
                rate=rec.win_rate,
                tab="scouting",
                map=map_name,
                extra={"site": site},
            )
        )
    return out


def most_played_map(rounds: Sequence[TeamRound]) -> str | None:
    games = {(r.game_id, r.map_name) for r in rounds}  # one entry per map played
    by_map = Counter(m for _, m in games)
    return by_map.most_common(1)[0][0] if by_map else None


def key_findings(
    con: sqlite3.Connection,
    team_id: str,
    map_name: str | None = None,
    since: str | None = None,
    baselines: dict | None = None,
    max_findings: int = MAX_FINDINGS,
    maps_path: Path | None = None,
) -> dict:
    """The panel: up to ``max_findings`` league-comparison findings (most unusual first) plus
    map findings for ``map_name`` (or the team's most-played map)."""
    baselines = baselines if baselines is not None else load_baselines(con)
    rounds = load_team_rounds(con, team_id, since=since)
    counts = team_counts(rounds)
    duels = _op_duel_counts(con, team_id=team_id).get(team_id)
    if duels:
        counts["op_duel_win"] = (duels[0], duels[1])

    ranked = sorted(league_findings(counts, baselines, team_id), key=lambda f: -abs(f.z))
    shown = [f for f in ranked if f.kind != "tendency"][:max_findings]
    if len(shown) < 3:  # always show something, even for an unremarkable team
        shown += [f for f in ranked if f.kind == "tendency"][: 3 - len(shown)]

    focus_map = map_name or most_played_map(rounds)
    site_findings = map_findings(con, team_id, rounds, focus_map, maps_path) if focus_map else []
    return {
        "team_id": team_id,
        "rounds": len(rounds),
        "maps": len({r.game_id for r in rounds}),
        "map": focus_map,
        "map_was_chosen": map_name is not None,
        "since": since,
        "league": [f.to_dict() for f in shown],
        "map_findings": [f.to_dict() for f in site_findings],
    }


def format_findings(panel: dict, team_name: str) -> str:
    lines = [
        f"KEY FINDINGS: {team_name}  ({panel['maps']} maps, {panel['rounds']} rounds)",
        "=" * 60,
    ]
    for f in panel["league"]:
        tag = {"strength": "+", "weakness": "-", "tendency": "~"}[f["kind"]]
        lines.append(f" [{tag}] {f['headline']}")
        lines.append(f"     {f['detail']}")
    if panel["map_findings"]:
        chosen = "" if panel["map_was_chosen"] else " (their most-played map)"
        lines.append(f"\n On {panel['map'].title()}{chosen}:")
        for f in panel["map_findings"]:
            lines.append(f" [{'-' if f['kind'] == 'weakness' else '~'}] {f['headline']}")
            lines.append(f"     {f['detail']}")
    lines.append("\n[+] strength  [-] weakness  [~] tendency; sorted by how unusual vs. the league")
    return "\n".join(lines)
