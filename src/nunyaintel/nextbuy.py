"""Next-round buy from money: what a team can afford next round, and what it will likely buy.

The older model in ``predict`` looks only at the situation (last buy, won or lost, loss streak).
This one also rebuilds the money, the way the game pays it out at the end of a round:

  credits next round  = per player: credits left after this round's buy
                        + round reward (win 3000; loss 1900 / 2400 / 2900 by loss streak)
                        + 300 if their side planted the spike (attackers only)
                        + 200 per kill this round
                        capped at 9000 per player
  gear kept           = the loadout value of every player who survived the round
                        (survivors keep their gun and armour)

The estimate isn't exact (ability purchases and other details aren't in the data: it runs
low, see ``evaluate``), so it is used in bands and the model learns from the league what each
band leads to. Prediction = the most likely buy given
  (situation, credit band, gear band) -> (situation, credits + gear band) -> situation -> all
each level shrunk toward the next broader one (K = 10 examples), as in the round model.

Overtime rounds (25+) are left out: everyone gets 5000 credits, so the buy says little.
"""

from __future__ import annotations

import os
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass

from nunyaintel import economy
from nunyaintel.predict import BUY_STATES, TEST_FRACTION

K = 10.0
BAND = 2500  # credits per band
TOP_BAND = 14  # 35k+ shares one band
WIN_REWARD = 3000
LOSS_REWARD = {1: 1900, 2: 2400, 3: 2900}
PLANT_REWARD = 300
KILL_REWARD = 200
MAX_CREDITS = 9000
OVERTIME_FROM = 25


def reward(won: bool, loss_streak: int) -> int:
    return WIN_REWARD if won else LOSS_REWARD[min(max(loss_streak, 1), 3)]


def band(credits: float) -> int:
    return min(max(int(credits // BAND), 0), TOP_BAND)


@dataclass(slots=True, frozen=True)
class Turn:
    """One team at the end of one round, and what it bought next round."""

    game_id: str
    team_id: str
    round_num: int  # the round just played; the prediction is for round_num + 1
    started_at: str
    last_buy: str
    won: bool
    loss_streak: int  # 0 after a win, capped at 3
    credits: int  # estimated team credits at the start of the next round
    kept: int  # loadout value of the survivors
    next_buy: str
    next_pool: int  # actual credits left + loadout value next round (checks the estimate)

    @property
    def situation(self) -> tuple[str, bool, int]:
        return (self.last_buy, self.won, self.loss_streak)


_cache: dict[tuple, list[Turn]] = {}


def _stamp(con: sqlite3.Connection) -> tuple:
    path = con.execute("PRAGMA database_list").fetchone()[2] or ":memory:"
    return (path, os.path.getmtime(path) if os.path.exists(path) else id(con))


def turns(con: sqlite3.Connection) -> list[Turn]:
    """Every (team, round) with its money estimate and the next round's real buy, cached."""
    key = _stamp(con)
    if key in _cache:
        return _cache[key]
    gear: dict[tuple, dict[str, tuple[int, int]]] = defaultdict(dict)
    for g, n, t, p, money, value in con.execute(
        """SELECT game_id, round_num, team_id, player_id, MAX(money), MAX(loadout_value)
           FROM loadouts GROUP BY game_id, round_num, team_id, player_id"""
    ):
        gear[g, n, t][p] = (money or 0, value or 0)
    kills: Counter[tuple] = Counter()
    dead: set[tuple] = set()
    for g, n, killer, victim in con.execute(
        "SELECT game_id, round_num, killer_id, victim_id FROM kills"
    ):
        kills[g, n, killer] += 1
        dead.add((g, n, victim))
    # unpack each row: the app's connection returns sqlite3.Row objects, which never equal
    # a plain (game, round) tuple, so set(rows) would silently find no plants at all
    planted = {
        (g, n)
        for g, n in con.execute(
            "SELECT game_id, round_num FROM objectives WHERE action = 'plantBomb'"
        )
    }
    rounds = con.execute(
        """SELECT r.game_id, r.round_num, r.attack_team_id, r.defense_team_id,
                  r.winner_team_id, g.started_at
           FROM rounds r JOIN meta_games g ON g.game_id = r.game_id
           WHERE r.winner_team_id IS NOT NULL AND r.attack_team_id IS NOT NULL
           ORDER BY g.started_at, r.game_id, r.round_num"""
    ).fetchall()
    out: list[Turn] = []
    streak: dict[tuple, int] = defaultdict(int)
    for g, n, att, dfn, winner, started in rounds:
        for team in (att, dfn):
            won = winner == team
            if n in economy.PISTOL_ROUNDS:
                streak[g, team] = 0  # the loss bonus starts over each half
            streak[g, team] = 0 if won else streak[g, team] + 1
            now, nxt = gear.get((g, n, team)), gear.get((g, n + 1, team))
            if not now or not nxt or n + 1 in economy.PISTOL_ROUNDS or n + 1 >= OVERTIME_FROM:
                continue
            plant = PLANT_REWARD if team == att and (g, n) in planted else 0
            pay = reward(won, streak[g, team]) + plant
            credits = sum(
                min(MAX_CREDITS, money + pay + KILL_REWARD * kills[g, n, p])
                for p, (money, _) in now.items()
            )
            kept = sum(value for p, (_, value) in now.items() if (g, n, p) not in dead)
            out.append(Turn(
                g, team, n, started or "",
                economy.classify_buy(n, sum(v for _, v in now.values())),
                won, min(streak[g, team], 3), credits, kept,
                economy.classify_buy(n + 1, sum(v for _, v in nxt.values())),
                sum(m + v for m, v in nxt.values()),
            ))  # fmt: skip
    _cache.clear()
    _cache[key] = out
    return out


class Model:
    """Next-buy counts per level, from broad (all rounds) to narrow (situation and money)."""

    def __init__(self, train: list[Turn]):
        self.levels: list[dict[tuple, Counter[str]]] = [defaultdict(Counter) for _ in range(4)]
        for t in train:
            keys = self._keys(t.situation, t.credits, t.kept)
            for level, key in zip(self.levels, keys, strict=True):
                level[key][t.next_buy] += 1

    @staticmethod
    def _keys(situation: tuple, credits: float, kept: float) -> list[tuple]:
        return [(), (situation,), (situation, band(credits + kept)),
                (situation, band(credits), band(kept))]  # fmt: skip

    def chances(self, situation: tuple, credits: float, kept: float) -> dict[str, float]:
        """Chance of each buy next round (a distribution over BUY_STATES)."""
        p = {s: 1 / len(BUY_STATES) for s in BUY_STATES}
        for level, key in zip(self.levels, self._keys(situation, credits, kept), strict=True):
            c = level.get(key)
            if not c:
                continue
            n = sum(c.values())
            p = {s: (c[s] + K * p[s]) / (n + K) for s in BUY_STATES}
        return p

    def support(self, situation: tuple, credits: float, kept: float) -> tuple[int, int]:
        """(past rounds, level) of the narrowest level that has any. Level 2+ uses the money;
        below that no past round had this money in this situation."""
        keys = self._keys(situation, credits, kept)
        for depth in range(len(keys) - 1, -1, -1):
            if keys[depth] in self.levels[depth]:
                return sum(self.levels[depth][keys[depth]].values()), depth
        return 0, 0


def likeliest(p: dict[str, float]) -> str:
    return max(BUY_STATES, key=lambda s: p.get(s, 0.0))


_model_cache: dict[tuple, Model] = {}


def model(con: sqlite3.Connection) -> Model:
    key = _stamp(con)
    if key not in _model_cache:
        _model_cache.clear()
        _model_cache[key] = Model(turns(con))
    return _model_cache[key]


def _split(all_turns: list[Turn]) -> tuple[list[Turn], list[Turn]]:
    dates = {t.game_id: t.started_at for t in all_turns}
    ordered = sorted(dates, key=lambda g: (dates[g], g))
    test = set(ordered[int(len(ordered) * (1 - TEST_FRACTION)) :])
    train = [t for t in all_turns if t.game_id not in test]
    return train, [t for t in all_turns if t.game_id in test]


def evaluate(con: sqlite3.Connection) -> dict:
    """Train on the earliest 70% of maps, predict every next buy on the rest.

    Compared with the situation-only model (same rounds, same split) and with always
    guessing the most common buy.
    """
    train, test = _split(turns(con))
    if not train or not test:
        return {"test_rounds": 0, "accuracy": 0.0, "situation_accuracy": 0.0,
                "baseline": "full-buy", "baseline_accuracy": 0.0, "per_class": {},
                "median_error": 0, "median_bias": 0}  # fmt: skip
    m = Model(train)
    by_sit: dict[tuple, Counter[str]] = defaultdict(Counter)
    for t in train:
        by_sit[t.situation][t.next_buy] += 1
    majority = Counter(t.next_buy for t in train).most_common(1)[0][0]
    hits = sit_hits = base = 0
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for t in test:
        guess = likeliest(m.chances(t.situation, t.credits, t.kept))
        sit = by_sit.get(t.situation)
        sit_guess = sit.most_common(1)[0][0] if sit else majority
        hits += guess == t.next_buy
        sit_hits += sit_guess == t.next_buy
        base += majority == t.next_buy
        per_class[t.next_buy][0] += guess == t.next_buy
        per_class[t.next_buy][1] += 1
    errors = [t.credits + t.kept - t.next_pool for t in test]
    n = len(test)
    return {
        "test_rounds": n,
        "accuracy": hits / n,
        "situation_accuracy": sit_hits / n,
        "baseline": majority,
        "baseline_accuracy": base / n,
        "per_class": {c: {"right": r, "n": k} for c, (r, k) in per_class.items()},
        "median_error": int(statistics.median(abs(e) for e in errors)),  # team credits
        "median_bias": int(statistics.median(errors)),  # negative: the estimate runs low
    }


def forecast(
    con: sqlite3.Connection, last_buy: str, won: bool, loss_streak: int, credits: int, kept: int
) -> dict:
    """What a team buys next round in this situation with this much money (Predict page)."""
    m = model(con)
    situation = (last_buy, won, 0 if won else min(max(loss_streak, 1), 3))
    p = m.chances(situation, credits, kept)
    n, depth = m.support(situation, credits, kept)
    return {"chances": p, "likeliest": likeliest(p), "support": n, "uses_money": depth >= 2}


def game_calls(con: sqlite3.Connection, game_id: str) -> dict[tuple[int, str], dict]:
    """{(round, team): call} for one map: the buy predicted for that round before it started,
    from the previous round's end. Uses the model trained on every map (it has seen this
    one, so the per-match hit rate is a little flattering; ``evaluate`` is the honest score).
    """
    m = model(con)
    calls = {}
    for t in turns(con):
        if t.game_id != game_id:
            continue
        p = m.chances(t.situation, t.credits, t.kept)
        guess = likeliest(p)
        calls[t.round_num + 1, t.team_id] = {
            "buy": guess, "p": round(p[guess], 3), "credits": t.credits, "kept": t.kept,
            "right": guess == t.next_buy,
        }  # fmt: skip
    return calls
