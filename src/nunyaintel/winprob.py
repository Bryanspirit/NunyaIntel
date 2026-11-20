"""Live round win chance: who wins the round from here?

The state of a round at any moment is (attackers alive, defenders alive, spike planted). We
count, over many rounds, how often the attack went on to win from each state, then read the
chance at every kill and plant of a round to draw a win-chance line.

Rare states (say 1 v 4 with the spike down) have few examples, so each state's rate is shrunk
toward a broader group, the same empirical-Bayes idea as the lineup scores:
  (a, d, planted, time band) -> (a, d, planted) -> man advantage (a - d, planted)
  -> planted or not -> all rounds

Time matters: a 2 v 2 with 5 s left plays differently from one with 60 s. The time band is
  before the plant  R0..R4 = 0-20, 20-40, 40-60, 60-80, 80+ s after the buy phase ends
  after the plant   P0..P3 = 0-10, 10-20, 20-30, 30+ s after the plant (the spike: 45 s)
taken when the state begins (at the kill or plant that created it).

Revives (Sage) are not in the data, so a side can show 6 deaths; alive counts stop at 0.
"""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from nunyaintel.predict import TEST_FRACTION, log_loss

K = 10.0  # shrinkage strength: a state needs ~10 rounds before its own rate dominates
START_STATE = (5, 5, 0)
START_BAND = "R0"
LATE_BANDS = {"R3", "R4", "P2", "P3"}  # 60 s+ into the round, or 20 s+ after the plant


def band(t_round: float | None, t_plant: float | None) -> str | None:
    """Time band for a moment: seconds after the buy phase / after the plant (see above)."""
    if t_plant is not None:
        return f"P{min(max(int(t_plant // 10), 0), 3)}"
    if t_round is None:
        return None
    return f"R{min(max(int(t_round // 20), 0), 4)}"


def _secs(a: str, b: str) -> float:
    return (datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()


@dataclass
class RoundStory:
    key: tuple[str, str, int]
    started_at: str  # the map's start: used to split train / test by time
    attack_team: str
    attack_won: bool
    buy_end: str | None
    # (occurred_at, attackers alive, defenders alive, planted, what happened)
    steps: list[tuple[str, int, int, int, str]] = field(default_factory=list)
    bands: list[str | None] = field(default_factory=list)  # time band of each step


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
        plant_at = None
        for at, what in sorted(happenings.get(key, [])):
            if what == "attacker died":
                a = max(0, a - 1)
            elif what == "defender died":
                d = max(0, d - 1)
            else:
                planted = 1
                plant_at = plant_at or at
            story.steps.append((at, a, d, planted, what))
            try:
                t_round = _secs(at, story.buy_end) if story.buy_end else None
                t_plant = _secs(at, plant_at) if plant_at else None
            except ValueError:
                t_round = t_plant = None
            story.bands.append(band(t_round, t_plant))
    return sorted(rounds.values(), key=lambda r: (r.started_at, r.key))


def visited(story: RoundStory) -> list[tuple[int, int, int]]:
    """The states a round passed through, in order, starting from 5 v 5."""
    out = [START_STATE]
    for _, a, d, p, _ in story.steps:
        if (a, d, p) != out[-1]:
            out.append((a, d, p))
    return out


def moments(story: RoundStory) -> list[tuple[int, int, int, str | None]]:
    """Like ``visited`` but with the time band each state began in: (a, d, planted, band)."""
    out = [(*START_STATE, START_BAND)]
    for (_, a, d, p, _), b in zip(story.steps, story.bands, strict=True):
        if (a, d, p) != out[-1][:3]:
            out.append((a, d, p, b))
    return out


class Model:
    """Counts of (attack wins, rounds) per state and per broader group."""

    def __init__(self, train: list[RoundStory]):
        self.timed: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.state: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.adv: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.plant: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        self.all = [0, 0]
        for r in train:
            for a, d, p, b in set(moments(r)):  # each state counts once per round
                for table, key in (
                    (self.timed, (a, d, p, b)),
                    (self.state, (a, d, p)),
                    (self.adv, (a - d, p)),
                    (self.plant, p),
                ):
                    table[key][0] += r.attack_won
                    table[key][1] += 1
            self.all[0] += r.attack_won
            self.all[1] += 1

    def p_attack(self, a: int, d: int, planted: int, band: str | None = None) -> float:
        """Chance the attack wins the round from this state (and time band, if given)."""
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
            self.timed.get((a, d, planted, band)) if band else None,
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
    n = hits = hits_untimed = 0
    late = [0, 0.0, 0.0]  # moments, Brier with time, Brier without
    brier = brier_base = brier_untimed = loss = loss_base = 0.0
    bins: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for r in test:
        # the final state usually *is* the result, so it isn't scored
        for a, d, p, b in moments(r)[:-1] or [(*START_STATE, START_BAND)]:
            q = m.p_attack(a, d, p, b)
            q0 = m.p_attack(a, d, p)  # same moment, no time: what the time band adds
            won = r.attack_won
            n += 1
            hits += (q >= 0.5) == won
            hits_untimed += (q0 >= 0.5) == won
            brier += (q - won) ** 2
            brier_untimed += (q0 - won) ** 2
            if b in LATE_BANDS:  # where the clock should matter most
                late[0] += 1
                late[1] += (q - won) ** 2
                late[2] += (q0 - won) ** 2
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
        "accuracy_without_time": hits_untimed / n if n else 0.0,
        "brier_without_time": brier_untimed / n if n else 0.0,
        "late_moments": late[0],
        "late_brier": late[1] / late[0] if late[0] else 0.0,
        "late_brier_without_time": late[2] / late[0] if late[0] else 0.0,
        "baseline_brier": brier_base / n if n else 0.0,
        "log_loss": loss / n if n else 0.0,
        "baseline_log_loss": loss_base / n if n else 0.0,
        "attack_win_rate": base,
        "calibration": [
            {"from": b / 10, "to": (b + 1) / 10, "won": w, "n": k}
            for b, (w, k) in sorted(bins.items())
        ],
    }
