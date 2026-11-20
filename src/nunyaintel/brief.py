"""Coach's brief: one opponent in plain English, the short version of the game plan.

The game plan lists separate pieces of advice. The brief puts them into a story a coach can
read in a minute: who the team is, how it wins rounds, where rounds slip away from it, what
has changed lately, and what to do. Where two checked facts point the same way, it says so
("putting it together"), e.g. fast hits + a weak opening duel = contest the first fight.

Nothing is invented: every sentence is written by code from numbers that are already
computed (and tested) elsewhere, and keeps its evidence and a link to the view behind it.
The linking rules are explicit below, so a reader can check each one. They are readings of
the numbers for a coach, not proof of cause.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nunyaintel import clutch, comps, gameplan, impact, insights, matchup_report, playstyle
from nunyaintel.maps import DEFAULT_PATH, MapInfo, get_map

SIDE_GAP_Z = 1.5  # attack vs defense z-scores this far apart = a team that leans on one side
EXPOSED_HOLD = 0.40  # our hold rate on their favourite site below this = the round to plan for
TOP_PLAYERS = 2


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _line(text: str, evidence: str = "", view: dict | None = None, n: int | None = None) -> dict:
    return {"text": text, "evidence": evidence, "view": view,
            "small": n is not None and n < gameplan.SMALL_SAMPLE}  # fmt: skip


def brief(
    con: sqlite3.Connection,
    us: str,
    them: str,
    map_info: MapInfo | None = None,
    maps_path: Path = DEFAULT_PATH,
) -> dict:
    plan = gameplan.plan(con, us, them, map_info, maps_path=maps_path)
    m = plan["map"]
    if map_info is None and m:
        map_info = get_map(m, maps_path)  # the plan picked the map (our best pick)
    a, b = plan["a"]["name"], plan["b"]["name"]
    on = f" on {m.title()}" if m else ""
    items = plan["items"]

    def first(section: str) -> list[dict]:
        return [i for i in items if i["section"] == section]

    def as_line(i: dict) -> dict:
        return _line(i["advice"], i["evidence"], i["view"], i["n"])

    findings = {f.key: f for f in gameplan._findings(con, them, insights.load_baselines(con))}
    style = playstyle.fingerprint(con, them, map_info)["team"]["rates"] if map_info else {}
    tight = clutch.analyse(con, them, map_info)
    rep = matchup_report.report(con, us, them, map_info=map_info) if map_info else None
    recent = comps.recent(con, them)
    players = impact.team_players(con, them, None)[:TOP_PLAYERS]
    scout = {"tab": "scouting", "team": them, **({"map": m} if m else {})}

    # ---- who they are ----------------------------------------------------------------------
    who: list[dict] = []
    att, dfn = findings.get("attack_win"), findings.get("defense_win")
    if att and dfn:
        gap = dfn.z - att.z
        lean = (
            "lean on their defense"
            if gap >= SIDE_GAP_Z
            else "lean on their attack"
            if gap <= -SIDE_GAP_Z
            else "are balanced across sides"
        )
        who.append(_line(
            f"{b} {lean}: their defense wins {_pct(dfn.rate)} of rounds (league "
            f"{_pct(dfn.league_rate or 0)}), their attack {_pct(att.rate)} (league "
            f"{_pct(att.league_rate or 0)}).",
            f"{dfn.hits} of {dfn.n} defense, {att.hits} of {att.n} attack rounds",
            {"tab": "findings", "team": them}, min(att.n, dfn.n),
        ))  # fmt: skip
    h2h = plan["head_to_head"]
    if h2h["maps"]:
        who.append(_line(f"Head to head, {a} won {h2h['won']} of {h2h['maps']} maps.", "",
                         {"tab": "matchup", "opp": them, **({"map": m} if m else {})}))  # fmt: skip
    if players:
        names = ", ".join(
            f"{p['name']} ({p['per_100']:+.1f} round wins added per 100, #{p['rank']} of "
            f"{p['ranked']})"
            if p.get("rank")
            else f"{p['name']} ({p['per_100']:+.1f})"
            for p in players
        )
        who.append(_line(f"Their most valuable players: {names}.", "win chance added by "
                         "each player's kills and deaths, 200+ rounds", scout))  # fmt: skip
    who += [as_line(i) for i in first("playstyle")]

    # ---- how they win / where rounds slip away ---------------------------------------------
    wins = [as_line(i) for i in first("respect")]
    slips = [as_line(i) for i in first("exploit")]
    for kind, label in (("retake", "retakes"), ("post_plant", "post-plants")):
        for s in tight[kind]["sites"]:
            if s["notable"]:
                line = _line(
                    f"Their {label} on {s['site']} are {'better' if s['above'] > 0 else 'worse'} "
                    f"than the league's: {s['won']} of {s['n']}{on}, where the league would "
                    f"win {s['expected']:.1f}.",
                    f"{abs(s['z']):.1f} standard errors", scout, s["n"],
                )  # fmt: skip
                (wins if s["above"] > 0 else slips).append(line)
    c = tight["clutch"]
    if c["notable"]:
        (wins if c["above"] > 0 else slips).append(_line(
            f"Their last player alive wins {c['won']} of {c['n']} clutches{on}, where the "
            f"league would win {c['expected']:.1f}.", f"{abs(c['z']):.1f} standard errors",
            scout, c["n"],
        ))  # fmt: skip
    slips += [as_line(i) for i in first("map") if i["advice"].startswith("On attack")]
    econ = first("economy")

    # ---- putting it together: explicit rules, each needing two facts ------------------------
    links: list[dict] = []
    fast, fk = style.get("fast"), style.get("first_kill")
    if fast and fk and fast["notable"] and fast["z"] > 0 and fk["notable"] and fk["z"] < 0:
        links.append(_line(
            f"They hit fast ({_pct(fast['rate'])} plant within 35 s) but win the opening duel "
            f"on attack only {_pct(fk['rate'])}: their quick hits often start a player down. "
            "Hold early contact positions and take the first fight.",
            f"fast {fast['hits']} of {fast['n']}, first kill {fk['hits']} of {fk['n']}",
            scout, min(fast["n"], fk["n"]),
        ))  # fmt: skip
    late = style.get("late")
    if late and late["notable"] and late["z"] > 0 and fk and not (fk["notable"] and fk["z"] > 0):
        links.append(_line(
            f"They take their time ({_pct(late['rate'])} of attack rounds plant after 70 s): "
            "don't over-rotate on early noise, and keep utility for the late hit.",
            f"{late['hits']} of {late['n']}", scout, late["n"],
        ))  # fmt: skip
    if rep and rep["sites"]:
        theirs = rep["sites"]["b_attacks"]
        if theirs:
            fav = max(theirs, key=lambda r: r["attack_share"])
            hold = fav["hold_win"]
            if hold is not None and hold < EXPOSED_HOLD:
                links.append(_line(
                    f"{fav['site']} is where you're most exposed: it's their favourite attack site "
                    f"({_pct(fav['attack_share'])} of their attack rounds) and {a} hold it only "
                    f"{_pct(hold)}. Agree the {fav['site']} setup and the retake before the match.",
                    f"{fav['attack_n']} of their attack rounds went {fav['site']}",
                    {"tab": "matchup", "opp": them, "map": m}, fav["attack_n"],
                ))  # fmt: skip
        mine = [r for r in rep["sites"]["a_attacks"] if r["hold_n"] >= gameplan.MIN_HOLD_ROUNDS]
        if mine:
            weak = min(mine, key=lambda r: r["hold_win"])
            ours = max(rep["sites"]["a_attacks"], key=lambda r: r["attack_share"])
            if weak["site"] == ours["site"]:
                links.append(_line(
                    f"Their weakest hold, {weak['site']} ({_pct(weak['hold_win'])} held), is "
                    f"already {a}'s most-used attack site: keep going there.",
                    f"{round(weak['hold_win'] * weak['hold_n'])} of {weak['hold_n']} held",
                    {"tab": "matchup", "opp": them, "map": m}, weak["hold_n"],
                ))  # fmt: skip
    ae, eu = findings.get("anti_eco_loss"), findings.get("eco_upset")
    if ae and eu and ae.z < -1 and eu.z < -1:  # both below the league: buys go to form
        links.append(_line(
            "Their economy rounds go to form: their ecos rarely win "
            f"({_pct(eu.rate)}) and their full buys rarely lose to ecos ({_pct(ae.rate)}). "
            "Expect no cheap rounds either way; the buy rounds decide it.",
            f"{eu.hits} of {eu.n} ecos won, {ae.hits} of {ae.n} full buys lost",
            {"tab": "findings", "team": them}, min(ae.n, eu.n),
        ))  # fmt: skip

    # ---- lately -----------------------------------------------------------------------------
    lately: list[dict] = []
    if recent.get("enough"):
        for ch in recent["changes"]:
            if ch["changed"]:
                r, bf = ch["recent"], ch["before"]
                lately.append(_line(
                    f"{ch['label'][0].upper()}{ch['label'][1:]}: {_pct(r[0] / r[1])} in their "
                    f"last {recent['recent_series']} matches vs {_pct(bf[0] / bf[1])} before "
                    f"({'better' if ch['direction'] == 'better' else 'worse'} for them).",
                    f"{r[0]} of {r[1]} vs {bf[0]} of {bf[1]}; {abs(ch['z']):.1f} standard errors",
                    {"tab": "findings", "team": them}, r[1],
                ))  # fmt: skip
        if not lately:
            lately.append(
                _line(
                    f"Nothing in their last {recent['recent_series']} matches "
                    f"({recent['recent_from']} to {recent['recent_to']}) differs from before "
                    "beyond luck."
                )
            )

    # ---- three things to do -----------------------------------------------------------------
    todo = [as_line(i) for i in first("map")][:2]
    best_exploit = max(first("exploit"), key=lambda i: i["n"], default=None)
    if best_exploit:
        todo.append(as_line(best_exploit))
    elif econ:
        todo.append(as_line(econ[0]))
    todo = todo[:3]

    sections = [
        {"key": "who", "title": "Who they are", "lines": who},
        {"key": "wins", "title": "How they win rounds", "lines": wins},
        {"key": "slips", "title": "Where rounds slip away from them",
         "lines": slips + [as_line(i) for i in econ]},
        {"key": "links", "title": "Putting it together", "lines": links},
        {"key": "lately", "title": "Lately", "lines": lately},
        {"key": "todo", "title": "Three things to do", "lines": todo},
    ]  # fmt: skip
    sections = [s for s in sections if s["lines"]]
    title = f"{b}{on}: the short version"
    return {"a": plan["a"], "b": plan["b"], "map": m, "map_was_chosen": plan["map_was_chosen"],
            "title": title, "sections": sections, "text": _text(title, sections)}  # fmt: skip


def _text(title: str, sections: list[dict]) -> str:
    """Plain text for copy and paste (a team chat, a notes app)."""
    out = [title, ""]
    for s in sections:
        out.append(s["title"].upper())
        for ln in s["lines"]:
            small = "; small sample" if ln["small"] else ""
            ev = f" [{ln['evidence']}{small}]" if ln["evidence"] else ""
            out.append(f"- {ln['text']}{ev}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
