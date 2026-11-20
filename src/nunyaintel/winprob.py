"""Live round win chance: who wins the round from here?

The state of a round at any moment is (attackers alive, defenders alive, spike planted). We
count, over many rounds, how often the attack went on to win from each state, then read the
chance at every kill and plant of a round to draw a win-chance line.

Rare states (say 1 v 4 with the spike down) have few examples, so each state's rate is shrunk
toward a broader group, the same empirical-Bayes idea as the lineup scores:
  state (a, d, planted)  ->  man advantage (a - d, planted)  ->  planted or not  ->  all rounds

Revives (Sage) are not in the data, so a side can show 6 deaths; alive counts stop at 0.
Time left is not in the state yet: a 2 v 2 with 5 s left plays differently from one with 60 s.
"""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from nunyaintel.predict import TEST_FRACTION, log_loss

K = 10.0  # shrinkage strength: a state needs ~10 rounds before its own rate dominates
START_STATE = (5, 5, 0)


@dataclass
class RoundStory:
    key: tuple[str, str, int]
    started_at: str  # the map's start: used to split train / test by time
    attack_team: str
    attack_won: bool
    buy_end: str | None
    # (occurred_at, attackers alive, defenders alive, planted, what happened)
    steps: list[tuple[str, int, int, int, str]] = field(default_factory=list)


def stories(con: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[RoundStory]:
    """Every round (or those matching `where` on the rounds table `x`) as a list of states."""
    rounds: dict[tuple, RoundStory] = {}
    for s, g, n, started, buy_end, att, winner in con.execute(
        f"""SELECT x.series_id, x.game_id, x.round_num, g.started_at, x.buy_ended_at,
                   x.attack_team_id, x.winner_team_id
            FROM rounds x JOIN meta_games g ON g.game_id = x.game_id
            WHERE x.attack_team_id IS NOT NULL AND x.winner_team_id IS NOT NULL {where}""",
        params,
    ):
        rounds[(s, g, n)] = RoundStory((s, g, n), started or "", att, winner == att, buy_end)

    happenings: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    for s, g, n, at, victim_side in con.execute(
        f"""SELECT k.series_id, k.game_id, k.round_num, k.occurred_at, k.victim_side
            FROM kills k JOIN rounds x USING (series_id, game_id, round_num)
            WHERE k.occurred_at IS NOT NULL {where}""",
        params,
    ):
        happenings[(s, g, n)].append(
            (at, "attacker died" if victim_side == "attacker" else "defender died")
        )
    for s, g, n, at in con.execute(
        f"""SELECT o.series_id, o.game_id, o.round_num, o.occurred_at
            FROM objectives o JOIN rounds x USING (series_id, game_id, round_num)
            WHERE o.action = 'plantBomb' AND o.occurred_at IS NOT NULL {where}""",
        params,
    ):
        happenings[(s, g, n)].append((at, "spike planted"))

    for key, story in rounds.items():
        a, d, planted = START_STATE
        for at, what in sorted(happenings.get(key, [])):
            if what == "attacker died":
                a = max(0, a - 1)
            elif what == "defender died":
                d = max(0, d - 1)
            else:
                planted = 1
            story.steps.append((at, a, d, planted, what))
    return sorted(rounds.values(), key=lambda r: (r.started_at, r.key))


def visited(story: RoundStory) -> list[tuple[int, int, int]]:
    """The states a round passed through, in order, starting from 5 v 5."""
    out = [START_STATE]
    for _, a, d, p, _ in story.steps:
        if (a, d, p) != out[-1]:
            out.append((a, d, p))
    return out


class Model:
    """Counts of (attack wins, rounds) per state and per broader group."""

    def __init__(self, train: list[RoundStory]):
        self.state: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.adv: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.plant: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        self.all = [0, 0]
        for r in train:
            for a, d, p in set(visited(r)):  # each state counts once per round
                for table, key in (
                    (self.state, (a, d, p)),
                    (self.adv, (a - d, p)),
                    (self.plant, p),
                ):
                    table[key][0] += r.attack_won
                    table[key][1] += 1
            self.all[0] += r.attack_won
            self.all[1] += 1

    def p_attack(self, a: int, d: int, planted: int) -> float:
        """Chance the attack wins the round from this state."""
        if a == 0 and not planted:
            return 0.0  # no attackers and no spike: the round is over
        if d == 0:
            return 1.0  # no defenders left: nobody can defuse
        base = self.all[0] / self.all[1] if self.all[1] else 0.5
        p = base
        for count in (
            self.plant.get(planted),
            self.adv.get((a - d, planted)),
            self.state.get((a, d, planted)),
        ):
            w, n = count or (0, 0)
            p = (w + K * p) / (n + K)
        return p

    def grid(self, planted: int) -> list[dict]:
        """Every (attackers, defenders) state: chance and how many rounds back it (for a chart)."""
        return [
            {
                "a": a,
                "d": d,
                "p": self.p_attack(a, d, planted),
                "n": self.state.get((a, d, planted), (0, 0))[1],
            }
            for a in range(5, -1, -1)
            for d in range(5, -1, -1)
        ]


_cache: dict[tuple, Model] = {}


def model(con: sqlite3.Connection) -> Model:
    """A model trained on every round, rebuilt only when the extract file changes."""
    path = con.execute("PRAGMA database_list").fetchone()[2] or ":memory:"
    stamp = os.path.getmtime(path) if os.path.exists(path) else 0
    key = (path, stamp)
    if key not in _cache:
        _cache.clear()
        _cache[key] = Model(stories(con))
    return _cache[key]


def evaluate(con: sqlite3.Connection) -> dict:
    """Train on the earliest 70% of maps, score every state of every round on the rest."""
    all_rounds = stories(con)
    games = sorted({(r.started_at, r.key[1]) for r in all_rounds})
    test_games = {g for _, g in games[int(len(games) * (1 - TEST_FRACTION)) :]}
    train = [r for r in all_rounds if r.key[1] not in test_games]
    test = [r for r in all_rounds if r.key[1] in test_games]
    m = Model(train)
    base = m.all[0] / m.all[1]
    n = hits = 0
    brier = brier_base = loss = loss_base = 0.0
    bins: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for r in test:
        for a, d, p in visited(r)[:-1] or [START_STATE]:  # the final state usually *is* the result
            q = m.p_attack(a, d, p)
            won = r.attack_won
            n += 1
            hits += (q >= 0.5) == won
            brier += (q - won) ** 2
            brier_base += (base - won) ** 2
            loss += log_loss(q if won else 1 - q)
            loss_base += log_loss(base if won else 1 - base)
            b = min(int(q * 10), 9)
            bins[b][0] += won
            bins[b][1] += 1
    return {
        "train_rounds": len(train),
        "test_rounds": len(test),
        "test_states": n,
        "accuracy": hits / n if n else 0.0,
        "brier": brier / n if n else 0.0,
        "baseline_brier": brier_base / n if n else 0.0,
        "log_loss": loss / n if n else 0.0,
        "baseline_log_loss": loss_base / n if n else 0.0,
        "attack_win_rate": base,
        "calibration": [
            {"from": b / 10, "to": (b + 1) / 10, "won": w, "n": k}
            for b, (w, k) in sorted(bins.items())
        ],
    }
