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


# --- A. map winner: Elo -------------------------------------------------------------------


def study_map_winner(con, k: float = 32.0) -> None:
    games = con.execute(
        "SELECT game_id, started_at, team1_id, team2_id, winner_team_id FROM meta_games "
        "WHERE winner_team_id IN (team1_id, team2_id) ORDER BY started_at"
    ).fetchall()
    split = int(len(games) * (1 - TEST_FRACTION))
    rating: dict[str, float] = defaultdict(lambda: 1500.0)
    played: Counter[str] = Counter()
    hits = n = 0
    brier = ll = 0.0
    for i, (_, _, t1, t2, winner) in enumerate(games):
        p1 = 1 / (1 + 10 ** ((rating[t2] - rating[t1]) / 400))  # Elo's win probability
        won1 = winner == t1
        if i >= split and played[t1] >= 5 and played[t2] >= 5:  # score only "known" teams
            n += 1
            hits += (p1 >= 0.5) == won1
            brier += (p1 - won1) ** 2
            ll += log_loss(p1 if won1 else 1 - p1)
        rating[t1] += k * (won1 - p1)
        rating[t2] -= k * (won1 - p1)
        played[t1] += 1
        played[t2] += 1
    print("A. Who wins a map? (Elo, K=32)")
    print(f"   test maps: {n} (latest {TEST_FRACTION:.0%}, both teams with 5+ earlier maps)")
    print(f"   Elo:        accuracy {hits / n:.1%}   Brier {brier / n:.3f}   log loss {ll / n:.3f}")
    print(f"   coin flip:  accuracy 50.0%   Brier 0.250   log loss {math.log(2):.3f}")


# --- B. next-round buy ---------------------------------------------------------------------


def _team_round_sequences(con):
    """{(game_id, team_id): [(round_num, buy, won), ...]} in round order, plus game dates."""
    economy.register(con)
    rows = con.execute(
        """
        WITH team_buy AS (
            SELECT series_id, game_id, round_num, team_id, SUM(lv) AS loadout
            FROM (SELECT series_id, game_id, round_num, team_id, player_id,
                         MAX(loadout_value) AS lv FROM loadouts
                  GROUP BY series_id, game_id, round_num, team_id, player_id)
            GROUP BY series_id, game_id, round_num, team_id
        )
        SELECT r.game_id, b.team_id, r.round_num, classify_buy(r.round_num, b.loadout),
               r.winner_team_id = b.team_id, g.started_at
        FROM rounds r
        JOIN meta_games g ON g.game_id = r.game_id
        JOIN team_buy b ON b.series_id = r.series_id AND b.game_id = r.game_id
                       AND b.round_num = r.round_num
        WHERE r.winner_team_id IS NOT NULL
        ORDER BY r.game_id, b.team_id, r.round_num
        """
    ).fetchall()
    seqs: dict[tuple[str, str], list[tuple[int, str, bool]]] = defaultdict(list)
    dates: dict[str, str] = {}
    for game, team, num, buy, won, started in rows:
        seqs[game, team].append((num, buy, bool(won)))
        dates[game] = started
    return seqs, dates


def _buy_situations(seq):
    """(situation, next buy) pairs. Situation = (last buy, won last round, loss streak cap 3)."""
    streak = 0
    for (num, buy, won), (next_num, next_buy, _) in zip(seq, seq[1:], strict=False):
        streak = 0 if won else streak + 1
        if next_num != num + 1 or next_num in economy.PISTOL_ROUNDS:
            continue  # gaps (restarted rounds) and pistol rounds aren't predictions
        yield (buy, won, min(streak, 3)), next_buy


def study_next_buy(con) -> None:
    seqs, dates = _team_round_sequences(con)
    ordered = sorted(dates, key=dates.get)
    test_games = set(ordered[int(len(ordered) * (1 - TEST_FRACTION)) :])
    table: dict[tuple, Counter[str]] = defaultdict(Counter)
    overall: Counter[str] = Counter()
    for (game, _), seq in seqs.items():
        if game not in test_games:
            for situation, nxt in _buy_situations(seq):
                table[situation][nxt] += 1
                overall[nxt] += 1
    majority = overall.most_common(1)[0][0]
    hits = base = n = 0
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (game, _), seq in seqs.items():
        if game in test_games:
            for situation, nxt in _buy_situations(seq):
                counts = table.get(situation)
                guess = counts.most_common(1)[0][0] if counts else majority
                n += 1
                hits += guess == nxt
                base += majority == nxt
                per_class[nxt][0] += guess == nxt
                per_class[nxt][1] += 1
    print("\nB. Next-round buy (learned from the league's earlier matches)")
    print(f"   test team-rounds: {n}")
    print(f"   model:                 accuracy {hits / n:.1%}")
    print(f"   always '{majority}':  accuracy {base / n:.1%}")
    for cls in economy.ECONOMY_STATES[1:]:
        got, total = per_class[cls]
        if total:
            print(f"     actual {cls:<9} {total:>6} rounds, predicted right {got / total:.0%}")


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
