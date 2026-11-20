"""Game plan: written advice for playing one opponent, every line backed by a number.

Nothing new is measured here. The plan turns tested analyses into short advice:
  veto       map pick / ban from both teams' map records (matchup report)
  exploit    the opponent's league-compared weaknesses (insights, z-scores)
  respect    the opponent's strengths
  watch      our own weaknesses, which a scouting opponent will look for
  map        on one map: which site to attack (their weakest hold), which to stack on defense
  utility    their most-used lineups on the map (what to expect, where, when)
  operator   their main Operator player on the map
  economy    the buy situation where they differ most from the league (next-buy model)

Each item says what to do ("advice"), why ("evidence", with counts) and where to see it
("view": the app selection that shows the number). Fewer than 30 behind it = small sample.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from nunyaintel import insights, matchup_report, predict
from nunyaintel.maps import DEFAULT_PATH, MapInfo, get_map
from nunyaintel.operator_profiler import profiler as op
from nunyaintel.utility import effectiveness, lineups, placement

SMALL_SAMPLE = 30
MIN_HOLD_ROUNDS = 10  # a site's hold rate counts only with this many rounds behind it
MIN_SITUATION = 15  # a buy situation needs this many examples for the team
MIN_BUY_GAP = 0.10  # only point out habits at least 10 points more common than the league's

# advice per (whose, metric key, kind); {r} = their rate, {lr} = league rate
EXPLOIT = {
    "anti_eco_loss": "Punish their full buys with ecos and forces: they lose {r} of them to ecos",
    "eco_upset": "Take your full-buy rounds with confidence: their ecos win only {r}",
    "pistol_win": "Put extra prep into pistol rounds: they win only {r}",
    "pistol_conversion": "Force-buy after losing a pistol: they convert only {r} of pistol wins",
    "attack_win": "Hold your default defense: their attack wins only {r} of rounds",
    "defense_win": "Attack with tempo: their defense wins only {r} of rounds",
    "op_duel_win": "Challenge their Operator early: they win only {r} of Op opening duels",
}
RESPECT = {
    "anti_eco_loss": "Don't count on cheap eco wins: they lose only {r} of full buys to ecos",
    "eco_upset": "Play their eco rounds carefully, no solo pushes: their ecos win {r}",
    "pistol_win": "Their pistols are strong ({r} won): play a safe, trade-heavy pistol",
    "pistol_conversion": "If they win the pistol, consider saving: they convert {r}",
    "attack_win": "Their attack is strong ({r} won): use info utility and retake as five",
    "defense_win": "Their defense holds ({r} won): fake and split rather than run at it",
    "op_duel_win": "Don't dry-peek their Operator: they win {r} of Op opening duels",
}
WATCH = {
    "anti_eco_loss": "Don't gift eco rounds: we lose {r} of full buys to ecos, so play for trades",
    "eco_upset": "Our ecos rarely land ({r} won): consider full saves instead",
    "pistol_win": "Our pistols are weak ({r} won): drill one set pistol play",
    "pistol_conversion": "Close out after pistol wins: we convert only {r}",
    "attack_win": "Our attack is below par ({r} won): plan our best map sides first",
    "defense_win": "Our defense is below par ({r} won): agree on retake setups",
    "op_duel_win": "Our Operator loses opening duels ({r} won): play it for second contact",
}
SIDE_WORD = {"attacker": "attack", "defender": "defense"}
BUY_WORDS = {"eco": "eco", "semi-eco": "semi-eco", "semi-buy": "force / half buy",
             "full-buy": "full-buy"}  # fmt: skip


def _timing(t: float | None) -> str:
    """Median cast time, from the end of the buy phase, in words."""
    if t is None:
        return ""
    if t < 0:
        return f", set up in the buy phase (~{-t:.0f}s before it ends)"
    return f", ~{t:.0f}s into the round"


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _item(section, advice, evidence, n, view, extra=None):
    return {"section": section, "advice": advice, "evidence": evidence, "n": n,
            "small": n < SMALL_SAMPLE, "view": view, **(extra or {})}  # fmt: skip


def _findings(con, team_id, baselines) -> list[insights.Finding]:
    counts = matchup_report._counts(con, team_id, None)
    return insights.league_findings(counts, baselines, team_id)


def _evidence(f: insights.Finding) -> str:
    league = f"; league {_pct(f.league_rate)}" if f.league_rate is not None else ""
    rank = f"; #{f.rank} of {f.ranked_teams}" if f.rank and f.ranked_teams else ""
    return f"{f.hits} of {f.n}{league}{rank}"


def _economy(con, team_id) -> dict | None:
    """The buy the team makes most *more often* than the league does, in one situation.

    Only positive gaps: "expect X" must mean they really do X, not that they rarely do it."""
    seqs, _ = predict.team_round_sequences(con)
    league: dict[tuple, Counter] = defaultdict(Counter)
    team: dict[tuple, Counter] = defaultdict(Counter)
    for (_, tid), seq in seqs.items():
        for sit, nxt in predict.situations(seq):
            league[sit][nxt] += 1
            if tid == team_id:
                team[sit][nxt] += 1
    best = None
    for sit, tc in team.items():
        tn, ln = sum(tc.values()), sum(league[sit].values())
        if tn < MIN_SITUATION:
            continue
        for state in predict.BUY_STATES:
            gap = tc[state] / tn - league[sit][state] / ln
            if gap >= MIN_BUY_GAP and (best is None or gap > best[0]):
                best = (gap, sit, state, tc[state], tn, league[sit][state] / ln)
    if best is None:
        return None
    _, (last, won, streak), state, hits, n, lr = best
    when = f"{'winning' if won else 'losing'} a round on a {BUY_WORDS[last]}"
    if not won and streak > 1:
        when += f" ({streak}{'+' if streak == 3 else ''} losses in a row)"
    return {"when": when, "state": BUY_WORDS[state], "hits": hits, "n": n, "rate": hits / n,
            "league_rate": lr}  # fmt: skip


def plan(
    con: sqlite3.Connection,
    us: str,
    them: str,
    map_info: MapInfo | None = None,
    maps_path: Path = DEFAULT_PATH,
) -> dict:
    baselines = insights.load_baselines(con)
    chosen = map_info is not None
    rep = matchup_report.report(con, us, them, map_info=map_info)
    # no map chosen: plan for the suggested pick (the map where we're furthest ahead)
    if map_info is None and rep["pick"]:
        map_info = get_map(rep["pick"], maps_path)
        rep = matchup_report.report(con, us, them, map_info=map_info)
    a, b = rep["a"]["name"], rep["b"]["name"]
    m = map_info.name if map_info else None
    items: list[dict] = []

    # veto
    pool = {p["map"]: p for p in rep["map_pool"]}
    for key, verb in (("pick", "Pick"), ("ban", "Ban")):
        name = rep[key]
        if name:
            p = pool[name]
            items.append(_item(
                "veto", f"{verb} {name.title()}",
                f"round win rate {a} {_pct(p['a']['round_win_rate'])} "
                f"({p['a']['rounds']} rounds) vs "
                f"{b} {_pct(p['b']['round_win_rate'])} ({p['b']['rounds']} rounds)",
                min(p["a"]["rounds"], p["b"]["rounds"]),
                {"tab": "matchup", "opp": them, "map": name},
            ))  # fmt: skip

    # opponent weaknesses / strengths, our weaknesses (strongest signals first)
    for team_id, kinds in ((them, ("weakness", "strength")), (us, ("weakness",))):
        for f in sorted(_findings(con, team_id, baselines), key=lambda f: -abs(f.z)):
            if f.kind not in kinds:
                continue
            if team_id == them:
                section, table = (
                    ("exploit", EXPLOIT) if f.kind == "weakness" else ("respect", RESPECT)
                )
            else:
                section, table = "watch", WATCH
            text = table.get(f.key, "{r} of " + insights.METRIC_BY_KEY[f.key].label)
            items.append(_item(section, text.format(r=_pct(f.rate)), _evidence(f), f.n,
                               {"tab": "findings", "team": team_id}))  # fmt: skip

    # site plan on the map
    if m and rep["sites"]:
        holds = [r for r in rep["sites"]["a_attacks"] if r["hold_n"] >= MIN_HOLD_ROUNDS]
        if holds:
            weak = min(holds, key=lambda r: r["hold_win"])
            items.append(_item(
                "map", f"On attack, hit {weak['site']}: {b}'s weakest hold on {m.title()}",
                f"{b} held {weak['site']} {round(weak['hold_win'] * weak['hold_n'])} of "
                f"{weak['hold_n']} ({_pct(weak['hold_win'])}); we go there in "
                f"{_pct(weak['attack_share'])} of attack rounds and win {_pct(weak['attack_win'])}",
                weak["hold_n"], {"tab": "matchup", "opp": them, "map": m},
            ))  # fmt: skip
        theirs = rep["sites"]["b_attacks"]
        if theirs:
            fav = max(theirs, key=lambda r: r["attack_share"])
            ours = f"; we hold it {_pct(fav['hold_win'])}" if fav["hold_win"] is not None else ""
            items.append(_item(
                "map", f"On defense, expect {fav['site']}: {b}'s favourite attack site",
                f"{_pct(fav['attack_share'])} of their attack rounds ({fav['attack_n']}), won "
                f"{_pct(fav['attack_win'])}{ours}",
                fav["attack_n"], {"tab": "scouting", "team": them, "map": m},
            ))  # fmt: skip

    # their utility habits on the map
    if map_info is not None:
        usages = placement.load_utility(con, map_name=m, team_id=them)
        scored = effectiveness.score_lineups(con, lineups.find_lineups(usages))
        for s in sorted(scored, key=lambda s: -s.lineup.rounds)[:2]:
            lu = s.lineup
            where = map_info.region_of(lu.x, lu.y)
            when = _timing(lu.median_time_s)
            items.append(_item(
                "utility",
                f"Expect {lu.agent.title()}'s {lu.ability.replace('-', ' ')} from "
                f"{where.super_region} {where.region} on {SIDE_WORD[lu.side]}{when}",
                f"used in {lu.rounds} rounds across {lu.series} matches; they won "
                f"{_pct(lu.round_win_rate)} of those rounds (usual {_pct(s.baseline)})",
                lu.rounds, {"tab": "utility", "team": them, "map": m},
            ))  # fmt: skip

        main = next((p for p in op.profile_players(con, team_id=them, map_name=m)
                     if p.rounds_with_op), None)  # fmt: skip
        if main:
            items.append(_item(
                "operator", f"Track {main.name}'s Operator on {m.title()}",
                f"Op in {_pct(main.op_buy_rate)} of their rounds ({main.rounds_with_op} of "
                f"{main.rounds_played}); {main.op_kills} Op kills, "
                f"won {_pct(main.op_round_win_rate)} of Op rounds",
                main.rounds_with_op, {"tab": "operator", "team": them, "map": m},
            ))  # fmt: skip

    econ = _economy(con, them)
    if econ:
        items.append(_item(
            "economy", f"After {econ['when']}, expect a {econ['state']}",
            f"they go {econ['state']} {econ['hits']} of {econ['n']} times ({_pct(econ['rate'])}); "
            f"league {_pct(econ['league_rate'])}",
            econ["n"], {"tab": "predict", "team": them},
        ))  # fmt: skip

    return {
        "a": rep["a"], "b": rep["b"], "map": m, "map_was_chosen": chosen,
        "elo": {"p_a_wins_map": rep["elo"]["p_a_wins_map"]},
        "head_to_head": {"maps": len(rep["head_to_head"]),
                         "won": sum(h["winner"] == "a" for h in rep["head_to_head"])},
        "items": items,
    }  # fmt: skip
