"""Can NunyaIntel predict? A feasibility study on the local extract (branch: predictive-analytics).

Three questions, each scored on LATER matches using only EARLIER ones (a time-based split, like a
coach preparing for the next match), and each compared with a simple baseline it has to beat:

  A. Who wins a map?               Elo ratings              vs. a coin flip
  B. Next-round buy (eco/force/..)  learned from the league   vs. "always full buy"
  C. Which site do they attack?     team history + league     vs. league habits / uniform

Run:  .venv\\Scripts\\python scripts\\predictive_feasibility.py
Prints aggregate results only (no raw data), so the output is safe to share.
"""

from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict

from nunyaintel import economy
from nunyaintel.data.extract import connect
from nunyaintel.maps import load_maps
from nunyaintel.scouting.sites import MAX_PLANT_TO_SITE_M

TEST_FRACTION = 0.3  # the latest 30% of maps (by date) are the test set


def log_loss(p: float) -> float:
    return -math.log(max(p, 1e-9))


# --- A and B: the app's own code (nunyaintel.predict) -----------------------------------


def study_map_winner(con) -> None:
    from nunyaintel.predict import evaluate_elo

    r = evaluate_elo(con)
    print("A. Who wins a map? (Elo, K=32)")
    print(f"   test maps: {r['test_maps']} (latest {TEST_FRACTION:.0%}, both teams with 5+ maps)")
    print(f"   Elo:        accuracy {r['accuracy']:.1%}   Brier {r['brier']:.3f}")
    print("   coin flip:  accuracy 50.0%   Brier 0.250")


def study_next_buy(con) -> None:
    from nunyaintel.predict import evaluate_next_buy

    r = evaluate_next_buy(con)
    print()
    print("B. Next-round buy (learned from the league's earlier matches)")
    print(f"   test team-rounds: {r['test_rounds']}")
    print(f"   model:                 accuracy {r['accuracy']:.1%}")
    print(f"   always '{r['baseline']}':  accuracy {r['baseline_accuracy']:.1%}")
    for cls in economy.ECONOMY_STATES[1:]:
        c = r["per_class"].get(cls)
        if c:
            share = c["right"] / c["n"]
            print(f"     actual {cls:<9} {c['n']:>6} rounds, predicted right {share:.0%}")


# --- C. attack site ------------------------------------------------------------------------


def study_attack_site(con, prior_strength: float = 5.0, min_history: int = 10) -> None:
    maps = load_maps()
    rows = con.execute(
        """SELECT o.game_id, lower(g.map), o.team_id, o.x, o.y, g.started_at
           FROM objectives o JOIN meta_games g ON g.game_id = o.game_id
           WHERE o.action = 'plantBomb' AND o.x IS NOT NULL ORDER BY g.started_at"""
    ).fetchall()
    plants = []
    for game, m, team, x, y, started in rows:
        if m in maps:
            site = maps[m].site_of(x, y, MAX_PLANT_TO_SITE_M)
            if site != "unknown":
                plants.append((started, game, m, team, site))
    split = int(len(plants) * (1 - TEST_FRACTION))
    team_hist: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    league: dict[str, Counter[str]] = defaultdict(Counter)
    scores = {"team + league": [0.0, 0], "league habits": [0.0, 0], "uniform": [0.0, 0]}
    top1 = {"team + league": 0, "league habits": 0}
    n = 0
    for i, (_, _, m, team, site) in enumerate(plants):
        hist, lg = team_hist[team, m], league[m]
        sites = [s.super_region for s in maps[m].sites]
        if i >= split and sum(hist.values()) >= min_history and sum(lg.values()):
            n += 1
            lg_total, h_total = sum(lg.values()), sum(hist.values())
            p_league = {s: (lg[s] + 1) / (lg_total + len(sites)) for s in sites}
            # shrinkage: the team's own history, pulled toward the league like U3's lineup score
            p_team = {
                s: (hist[s] + prior_strength * p_league[s]) / (h_total + prior_strength)
                for s in sites
            }
            for name, p in (("team + league", p_team), ("league habits", p_league)):
                scores[name][0] += log_loss(p[site])
                top1[name] += max(p, key=p.get) == site
            scores["uniform"][0] += log_loss(1 / len(sites))
        team_hist[team, m][site] += 1
        league[m][site] += 1
    print("\nC. Which site will they attack? (plant site, team history blended with the league)")
    print(f"   test plants: {n} (latest {TEST_FRACTION:.0%}, {min_history}+ earlier team plants)")
    for name in scores:
        acc = f"   top-1 accuracy {top1[name] / n:.1%}" if name in top1 else ""
        print(f"   {name:<14} log loss {scores[name][0] / n:.3f}{acc}")


if __name__ == "__main__":
    con = connect()
    study_map_winner(con)
    study_next_buy(con)
    study_attack_site(con)
    sys.exit(0)
