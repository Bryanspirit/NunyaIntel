"""P9: every number we quote (README, video, write-up), recomputed from the extract.

``nunyaintel verify-claims`` runs each check and writes ``docs/claims.md``: the claim as worded,
what the data says now, PASS/FAIL, and a small-sample flag. Run it again before submitting
(K7): a rebuilt extract or a changed definition can quietly make a quoted number stale.

A claim passes when the recomputed counts are exactly the ones we state. Rounded percentages
alone aren't enough: "30%" could hide 3 of 10 or 300 of 1,000.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from nunyaintel.config import PROJECT_ROOT

SMALL_SAMPLE = 30  # below this many rounds/duels a claim is flagged as a lead, not a verdict
CLAIMS_DOC = PROJECT_ROOT / "docs" / "claims.md"


@dataclass(frozen=True, slots=True)
class Result:
    ok: bool
    measured: str
    n: int | None = None  # sample size behind the claim, if it's a rate


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    where: str
    text: str
    check: Callable[[sqlite3.Connection], Result]


def _rate(hits: int, n: int) -> str:
    return f"{hits}/{n} = {hits / n:.1%}" if n else f"{hits}/0"


def _counts(expected: tuple[int, int], got: tuple[int, int]) -> Result:
    return Result(tuple(got) == tuple(expected), _rate(*got), got[1])


# --- checks -------------------------------------------------------------------------------


def _dataset(con):
    series = con.execute("SELECT COUNT(*) FROM meta_series").fetchone()[0]
    maps = con.execute("SELECT COUNT(*) FROM meta_games").fetchone()[0]
    rounds = con.execute(
        "SELECT COUNT(*) FROM rounds r JOIN meta_games g ON g.game_id = r.game_id "
        "WHERE r.winner_team_id IS NOT NULL"
    ).fetchone()[0]
    teams = con.execute("SELECT COUNT(*) FROM meta_teams").fetchone()[0]
    first, last = con.execute("SELECT MIN(started_at), MAX(started_at) FROM meta_games").fetchone()
    got = (series, maps, rounds, teams, first[:7], last[:7])
    return Result(
        got == (857, 2078, 42490, 160, "2025-01", "2026-09"),
        f"{series} series, {maps} maps, {rounds} rounds, {teams} teams, {first[:7]} to {last[:7]}",
    )


def _extract_verified(con):
    missing = con.execute(
        "SELECT COUNT(*) FROM meta_games g WHERE NOT EXISTS "
        "(SELECT 1 FROM rounds r WHERE r.game_id = g.game_id)"
    ).fetchone()[0]
    mismatched = con.execute(
        """SELECT COUNT(*) FROM meta_games g JOIN (
               SELECT game_id, COUNT(winner_team_id) AS n FROM rounds GROUP BY game_id
           ) r USING (game_id)
           WHERE CAST(g.team1_score AS INT) + CAST(g.team2_score AS INT) != r.n"""
    ).fetchone()[0]
    detail = f"{missing} maps missing, {mismatched} maps where winners != final score"
    return Result(missing == 0 and mismatched == 0, detail)


def _team_rounds(con, team="79", **kw):
    from nunyaintel.scouting.team_rounds import load_team_rounds

    return load_team_rounds(con, team, **kw)


def _c9_size(con):
    r = _team_rounds(con)
    got = (len({x.game_id for x in r}), len(r))
    return Result(got == (45, 961), f"{got[0]} maps, {got[1]} rounds")


def _anti_eco(con):
    from nunyaintel.scouting import economy_report as er

    a = er.anti_eco(er.buy_matrix(_team_rounds(con)))
    return _counts((15, 50), (a.played - a.won, a.played))


def _league(key):
    def check(con):
        from nunyaintel import insights

        return insights.load_baselines(con)["league"][key]

    return check


def _league_anti_eco(con):
    return _counts((888, 5067), tuple(_league("anti_eco_loss")(con)))


def _anti_eco_rank(con):
    from nunyaintel import insights

    rank, total = insights._rank(
        insights.load_baselines(con), insights.METRIC_BY_KEY["anti_eco_loss"], "79"
    )
    return Result((rank, total) == (55, 55), f"#{rank} of {total} (1 = fewest losses)")


def _pistol(con):
    from nunyaintel.scouting import economy_report as er

    ps = er.pistol_stats(_team_rounds(con))
    got = (ps.conversions.won, ps.conversions.played, ps.breaks.won, ps.breaks.played)
    return Result(
        got == (40, 47, 9, 42),
        f"conversion {_rate(*got[:2])}, break {_rate(*got[2:])}",
        min(got[1], got[3]),
    )


def _league_pistol_conversion(con):
    return _counts((3546, 4114), tuple(_league("pistol_conversion")(con)))


def _lotus_sites(con):
    from nunyaintel.maps import get_map
    from nunyaintel.scouting.sites import site_report

    rep = site_report(con, "79", _team_rounds(con, map_name="lotus"), get_map("lotus"))
    a, no, c = rep.attack["A"].rounds, rep.attack["no plant"].rounds, rep.defense["C"].rounds
    got = (rep.attack_rounds, a.played, a.won, no.played, no.won, c.played, c.won)
    hit_most = max(
        (s for s in rep.defense if s != "no plant"), key=lambda s: rep.defense[s].rounds.played
    )
    return Result(
        got == (155, 55, 42, 35, 1, 49, 16) and hit_most == "C",
        f"attack rounds {got[0]}; A planted {a.played} ({a.played / got[0]:.0%}), won {a.won}; "
        f"no plant {no.played} ({no.played / got[0]:.0%}), won {no.won}; "
        f"defense C {c.won}/{c.played} ({c.win_rate:.0%}), most-hit site = {hit_most}",
        min(a.played, no.played, c.played),
    )


def _oxy(con):
    from nunyaintel.operator_profiler import profiler as op

    p = next(x for x in op.profile_players(con, team_id="79") if x.name == "OXY")
    eco = {r.economy: r for r in op.op_rate_by_economy(con, team_id="79") if r.name == "OXY"}
    full = eco["full-buy"].rounds_with_op
    d = next(x for x in op.opening_duels(con, team_id="79") if x.name == "OXY")
    got = (p.rounds_with_op, p.rounds_played, full, d.op_duels_won, d.op_duels)
    return Result(
        got == (97, 961, 94, 20, 30),
        f"Op rounds {_rate(p.rounds_with_op, p.rounds_played)}; {full} of them on full buys; "
        f"Op opening duels {_rate(d.op_duels_won, d.op_duels)}",
        d.op_duels,
    )


def _oxy_pearl(con):
    from nunyaintel.operator_profiler import profiler as op

    d = next(x for x in op.opening_duels(con, team_id="79", map_name="pearl") if x.name == "OXY")
    return _counts((6, 8), (d.op_duels_won, d.op_duels))


def _cloud9_gc(con):
    from nunyaintel import insights

    b = insights.load_baselines(con)
    duels = b["teams"]["3429"]["op_duel_win"]
    conv = b["teams"]["3429"]["pistol_conversion"]
    rank, total = insights._rank(b, insights.METRIC_BY_KEY["op_duel_win"], "3429")
    got = (*duels, *conv, rank, total)
    return Result(
        got == (27, 34, 16, 21, 6, 76),
        f"Op opening duels {_rate(*duels)} (#{rank} of {total}); pistol conversion {_rate(*conv)}",
        min(duels[1], conv[1]),
    )


def _coverage(con):
    vct_2026 = con.execute(
        "SELECT COUNT(*) FROM meta_series WHERE scheduled_start >= '2026' "
        "AND event NOT LIKE 'Game Changers%'"
    ).fetchone()[0]
    c9 = con.execute(
        "SELECT series_count, first_seen, last_seen FROM meta_teams WHERE team_id = '79'"
    ).fetchone()
    gc = con.execute(
        "SELECT series_count, first_seen, last_seen FROM meta_teams WHERE team_id = '3429'"
    ).fetchone()
    got = (vct_2026, c9[1][:7], c9[2][:7], int(gc[0]), gc[1][:7], gc[2][:7])
    return Result(
        got == (0, "2025-01", "2025-08", 9, "2026-07", "2026-09"),
        f"non-GC series in 2026: {vct_2026}; Cloud9 {c9[1][:7]} to {c9[2][:7]}; "
        f"Cloud9 GC {gc[0]} series, {gc[1][:7]} to {gc[2][:7]}",
    )


def _plant_distances(con):
    from nunyaintel.maps import load_maps
    from nunyaintel.scouting.sites import MAX_PLANT_TO_SITE_M

    medians, gaps, ambiguous, unknown, total = [], [], 0, 0, 0
    for name, m in load_maps().items():
        rows = con.execute(
            "SELECT o.x, o.y FROM objectives o JOIN meta_games g ON g.game_id = o.game_id "
            "WHERE lower(g.map) = ? AND o.action = 'plantBomb' AND o.x IS NOT NULL",
            (name,),
        ).fetchall()
        if not rows:
            continue
        dists = []
        for x, y in rows:
            d = sorted(math.dist((x, y), (s.x, s.y)) for s in m.sites)
            total += 1
            if d[0] / 100 > MAX_PLANT_TO_SITE_M:  # bad position: labelled "unknown"
                unknown += 1
                continue
            dists.append(d[0] / 100)
            ambiguous += d[1] < 1.5 * d[0]
        medians.append(statistics.median(dists))
        gaps.append(
            min(math.dist((a.x, a.y), (b.x, b.y)) for a in m.sites for b in m.sites if a is not b)
            / 100
        )
    lo, hi, glo, ghi = min(medians), max(medians), min(gaps), max(gaps)
    return Result(
        round(lo) >= 3 and round(hi) <= 18 and round(glo) >= 43 and ambiguous == 0
        and unknown == 26,
        f"median plant-to-site {lo:.1f}-{hi:.1f} m on {len(medians)} maps; "
        f"sites {glo:.0f}-{ghi:.0f} m apart; ambiguous {ambiguous}; "
        f"over {MAX_PLANT_TO_SITE_M:.0f} m from any site (labelled unknown) {unknown}/{total}",
    )  # fmt: skip


def _ability_kills(con):
    n, null = con.execute("SELECT COUNT(*), SUM(weapon IS NULL) FROM kills").fetchone()
    return Result(round(100 * null / n, 1) == 3.7, _rate(null, n))


def _lotus_lineups(con):
    """The two Cloud9 Lotus lineups the demo video shows (U2 clustering + U3 scores)."""
    from nunyaintel.maps import get_map
    from nunyaintel.utility import effectiveness, lineups, placement

    m = get_map("lotus")
    usages = placement.load_utility(con, map_name="lotus", team_id="79")
    scores = effectiveness.score_lineups(con, lineups.find_lineups(usages))

    def pick(side, agent, ability, region):
        return next(
            s for s in scores
            if (s.lineup.side, s.lineup.agent, s.lineup.ability) == (side, agent, ability)
            and m.region_of(s.lineup.x, s.lineup.y).name == region
        )  # fmt: skip

    omen = pick("defender", "omen", "dark-cover", "C Main")
    fade = pick("attacker", "fade", "haunt", "A Lobby")
    got = (
        omen.lineup.rounds_won, omen.lineup.rounds, omen.lineup.series, round(omen.baseline * 100),
        fade.lineup.rounds_won, fade.lineup.rounds, fade.lineup.series,
    )  # fmt: skip
    return Result(
        got == (28, 46, 11, 47, 11, 15, 7),
        f"Omen smoke from C Main (defense): {_rate(omen.lineup.rounds_won, omen.lineup.rounds)} "
        f"in {omen.lineup.series} matches, usual {omen.baseline:.0%}; Fade Haunt from A Lobby "
        f"(attack): {_rate(fade.lineup.rounds_won, fade.lineup.rounds)} in "
        f"{fade.lineup.series} matches",
        fade.lineup.rounds,
    )


def _predictions(con):
    """Model accuracy figures shown in the Predict tab and docs/predictive-feasibility.md."""
    from nunyaintel import predict

    elo = predict.evaluate_elo(con)
    nb = predict.evaluate_next_buy(con)
    eco = nb["per_class"]["eco"]
    got = (
        elo["test_maps"], round(elo["accuracy"] * 100, 1), round(elo["brier"], 3),
        nb["test_rounds"], round(nb["accuracy"] * 100, 1), round(nb["baseline_accuracy"] * 100, 1),
        round(100 * eco["right"] / eco["n"]),
    )  # fmt: skip
    return Result(
        got == (503, 66.8, 0.213, 22994, 81.8, 73.6, 87),
        f"Elo: {got[0]} test maps, {got[1]}% right, Brier {got[2]}; next buy: {got[3]} "
        f"test team-rounds, {got[4]}% right vs {got[5]}% always-full-buy; ecos caught {got[6]}%",
    )


def _matchup_nrg(con):
    """Cloud9 vs NRG on Lotus, shown in the Matchup tab and the presentation tour."""
    from nunyaintel import matchup_report, predict
    from nunyaintel.maps import get_map

    opp = predict.frequent_opponent(con, "79")
    r = matchup_report.report(con, "79", opp, map_info=get_map("lotus"))
    a_att = max(r["sites"]["a_attacks"], key=lambda x: x["attack_share"])
    b_att = max(r["sites"]["b_attacks"], key=lambda x: x["attack_share"])
    a_hold_hits = round(a_att["hold_win"] * a_att["hold_n"])
    h2h = r["head_to_head"]
    got = (
        r["b"]["name"], a_att["site"], round(a_att["attack_share"] * 100), a_hold_hits,
        a_att["hold_n"], b_att["site"], round(b_att["attack_share"] * 100),
        round(b_att["hold_win"] * 100), sum(h["winner"] == "a" for h in h2h), len(h2h),
    )  # fmt: skip
    return Result(
        got == ("NRG", "A", 35, 11, 37, "C", 36, 33, 5, 8),
        f"opponent {got[0]}; C9 attacks {got[1]} most ({got[2]}%), NRG holds it "
        f"{_rate(got[3], got[4])}; NRG attacks {got[5]} most ({got[6]}%), C9 holds it "
        f"{got[7]}%; C9 won {got[8]} of {got[9]} head-to-head maps",
        a_att["hold_n"],
    )


def _round_winprob(con):
    """Round win-chance model: test accuracy and the first-kill swing (Replay, Predict tab)."""
    from nunyaintel import winprob

    e = winprob.evaluate(con)
    m = winprob.model(con)
    got = (
        e["test_rounds"], round(e["accuracy"] * 100, 1), round(e["brier"], 3),
        round(e["baseline_brier"], 3), round(m.p_attack(5, 5, 0) * 100),
        round(m.p_attack(5, 4, 0) * 100), round(m.p_attack(4, 5, 0) * 100),
    )  # fmt: skip
    return Result(
        got == (12745, 74.6, 0.162, 0.249, 52, 74, 31),
        f"{got[0]} unseen rounds: {got[1]}% right, Brier {got[2]} vs {got[3]}; attack wins "
        f"{got[4]}% at 5v5, {got[5]}% after getting the first kill, {got[6]}% after losing it",
    )


CLAIMS = [
    Claim("dataset", "README intro",
          "857 series, 2,078 maps, 42,490 rounds, 160 teams (Jan 2025 - Sep 2026)", _dataset),
    Claim("extract", "README How it works",
          "all 2,078 maps present; round winners add up to every map's final score",
          _extract_verified),
    Claim("c9_size", "README findings", "Cloud9: 45 maps / 961 rounds", _c9_size),
    Claim("anti_eco", "README findings, Key findings",
          "Cloud9 lost 30% of full-buy rounds vs. eco/semi-eco (15 of 50)", _anti_eco),
    Claim("league_anti_eco", "README findings",
          "league anti-eco loss rate 17.5% (888 of 5,067)", _league_anti_eco),
    Claim("anti_eco_rank", "README findings, Key findings",
          "worst of the 55 teams with 30+ anti-eco rounds", _anti_eco_rank),
    Claim("pistol", "README findings (85%); 21% is a video candidate",
          "85% next-round win after a pistol win (40 of 47); 21% after a loss (9 of 42)",
          _pistol),
    Claim("league_pistol", "README findings, learning log",
          "league pistol conversion 86.2% (3,546 of 4,114)", _league_pistol_conversion),
    Claim("lotus", "README findings, Key findings",
          "Lotus attack: A 35% of rounds, 76% won (42 of 55); 23% no plant, won 1 of 35; "
          "defense: C hit most, held 33% (16 of 49)", _lotus_sites),
    Claim("oxy", "README findings",
          "OXY: Op in 10% of rounds (97 of 961), 94 of them on full buys; "
          "67% of Op opening duels won (20 of 30)", _oxy),
    Claim("oxy_pearl", "learning log only (too small to headline)",
          "OXY on Pearl: 6 of 8 Op opening duels won", _oxy_pearl),
    Claim("cloud9_gc", "Key findings, learning log",
          "Cloud9 GC: 79% of Op opening duels (27 of 34, top 6 of 76); "
          "pistol conversion 76% (16 of 21)", _cloud9_gc),
    Claim("coverage", "README data coverage",
          "no VCT 2026 data; Cloud9 Jan-Aug 2025; Cloud9 GC 9 series Jul-Sep 2026", _coverage),
    Claim("plant_distance", "README methods",
          "plants sit a median 3-18 m from their site's callout and sites are 43-121 m apart, "
          "so site labels are unambiguous; 26 plants (0.09%, all Bind) are 70+ m from any "
          "site: bad positions, labelled unknown (cut at 50 m, in the gap between 46 and 67 m)",
          _plant_distances),
    Claim("lotus_lineups", "demo video (K1)",
          "Cloud9 Lotus lineups: Omen smoke from C Main on defense, won 28 of 46 rounds "
          "(61%) across 11 matches vs. their usual 47%; Fade Haunt from A Lobby on attack, "
          "won 11 of 15 (73%) across 7 matches", _lotus_lineups),
    Claim("predictions", "Predict tab, docs/predictive-feasibility.md",
          "Elo map winner: 66.8% right on 503 unseen maps (Brier 0.213 vs 0.250); next buy: "
          "81.8% vs 73.6% always-full-buy on 22,994 team-rounds, ecos caught 87%",
          _predictions),
    Claim("matchup_nrg", "Matchup tab, presentation tour",
          "Cloud9 vs NRG on Lotus: C9's most-attacked site A (35%) is held by NRG only 30% "
          "(11 of 37); NRG's most-attacked site C (36%) is C9's 33% hold; C9 won 5 of 8 "
          "head-to-head maps", _matchup_nrg),
    Claim("round_winprob", "Replay win-chance line, Predict tab",
          "round win chance: 74.6% right on 12,745 unseen rounds (Brier 0.162 vs 0.249); "
          "attack wins 52% at 5v5, 74% after the first kill, 31% after losing it",
          _round_winprob),
    Claim("ability_kills", "README caveats", "about 3.7% of kills have no weapon recorded",
          _ability_kills),
]  # fmt: skip


def run(con: sqlite3.Connection) -> list[tuple[Claim, Result]]:
    out = []
    for claim in CLAIMS:
        try:
            out.append((claim, claim.check(con)))
        except Exception as exc:  # a broken check must not hide the others
            out.append((claim, Result(False, f"error: {type(exc).__name__}: {exc}")))
    return out


def to_markdown(results: list[tuple[Claim, Result]], built_at: str) -> str:
    passed = sum(r.ok for _, r in results)
    lines = [
        "# Claims check",
        "",
        "Every number NunyaIntel quotes, recomputed from the local extract by "
        "`nunyaintel verify-claims`. This file is generated, so don't edit it by hand.",
        "",
        f"- Checked: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}; extract built {built_at}",
        f"- Result: **{passed} of {len(results)} claims pass**",
        f"- *small sample* = fewer than {SMALL_SAMPLE} rounds or duels behind the number: "
        "quote it as a lead, not a verdict",
        "- Data coverage: no VCT (main-team) matches in 2026; Cloud9's VCT data ends Aug 2025.",
        "",
        "| | Claim | Where | Data says now |",
        "|---|---|---|---|",
    ]
    for claim, r in results:
        mark = "PASS" if r.ok else "**FAIL**"
        small = " *(small sample)*" if r.n is not None and r.n < SMALL_SAMPLE else ""
        lines.append(f"| {mark} | {claim.text}{small} | {claim.where} | {r.measured} |")
    return "\n".join(lines) + "\n"


def main(write: Path | None = CLAIMS_DOC) -> int:
    from nunyaintel.data.extract import connect

    con = connect()
    built = con.execute("SELECT value FROM build_info WHERE key = 'built_at'").fetchone()
    results = run(con)
    for claim, r in results:
        small = "  (small sample)" if r.n is not None and r.n < SMALL_SAMPLE else ""
        print(f"[{'PASS' if r.ok else 'FAIL'}] {claim.id:<16} {r.measured}{small}")
    if write is not None:
        write.parent.mkdir(parents=True, exist_ok=True)
        write.write_text(to_markdown(results, built[0] if built else "?"), encoding="utf-8")
        print(f"\nwrote {write}")
    return 0 if all(r.ok for _, r in results) else 1
