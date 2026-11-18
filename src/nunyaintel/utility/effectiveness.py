"""U3: how well does each lineup work?

Three measures per lineup:

1. **Win-rate lift (the score).** Round win % when the lineup was used vs. the team's usual
   (*baseline*) round win % on that map and side. Most lineups are used only 3-8 times, and
   with 3 uses a 100% win rate is mostly luck. So we *shrink* toward the baseline first:

       adjusted = (wins + k * baseline) / (uses + k)        (k = 10 "imaginary" rounds)

   With few uses the adjusted rate stays near the baseline; with many uses the real record
   dominates. ``score = adjusted - baseline``: positive = the team does better than usual
   when it runs this lineup. This is a standard "empirical Bayes" style estimate.

2. **Ability damage** (damaging abilities only, e.g. shock-bolt, snake-bite, razorvine). Each
   damage hit from an ability is credited to the same player's latest earlier cast of that
   ability in the round (checked: 99.9% of shock-bolt damage has such a cast).

3. **Impact window** (casts during the round only): team kills and deaths in the
   ``window_s`` seconds after the cast. Catches flashes/recon that enable kills without
   dealing damage. Buy-phase setup casts are skipped here (nothing happens right after them).

Correlation, not causation: a lineup can look good because it's used in rounds the team was
going to win anyway (e.g. on full buys). Read the score as "worth a closer look", not proof.
"""

from __future__ import annotations

import bisect
import sqlite3
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from nunyaintel.scouting.overview import side_records
from nunyaintel.scouting.team_rounds import load_team_rounds
from nunyaintel.utility.lineups import Lineup

PRIOR_ROUNDS = 10
WINDOW_S = 10.0


def shrunk_rate(wins: int, n: int, baseline: float, prior: float = PRIOR_ROUNDS) -> float:
    """Win rate pulled toward ``baseline`` as if we'd also seen ``prior`` average rounds."""
    return (wins + prior * baseline) / (n + prior)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)  # Python 3.11+ understands the trailing "Z"


@dataclass(slots=True)
class LineupScore:
    lineup: Lineup
    baseline: float
    adjusted_win_rate: float
    ability_damage: int
    in_round_casts: int
    window_kills: int
    window_deaths: int

    @property
    def score(self) -> float:
        """Adjusted win rate minus baseline (e.g. +0.06 = 6 points better than usual)."""
        return self.adjusted_win_rate - self.baseline

    @property
    def damage_per_cast(self) -> float:
        return self.ability_damage / self.lineup.casts if self.lineup.casts else 0.0

    @property
    def net_window_per_cast(self) -> float | None:
        """(kills - deaths) in the window after a cast, per in-round cast."""
        if not self.in_round_casts:
            return None
        return (self.window_kills - self.window_deaths) / self.in_round_casts


def score_lineups(
    con: sqlite3.Connection,
    lineups: Sequence[Lineup],
    window_s: float = WINDOW_S,
    prior_rounds: float = PRIOR_ROUNDS,
) -> list[LineupScore]:
    """Score every lineup; returns them best score first."""
    if not lineups:
        return []
    members = [m for lu in lineups for m in lu.members]
    games = sorted({m.game_id for m in members})
    abilities = sorted({lu.ability for lu in lineups})
    g_marks, a_marks = ", ".join("?" * len(games)), ", ".join("?" * len(abilities))

    # --- 2. ability damage -> the caster's latest earlier cast of that ability ------------
    # All casts (not just lineup members): damage from a later, different cast must not be
    # credited to a lineup cast.
    cast_times: dict[tuple, list[tuple[datetime, str]]] = defaultdict(list)
    for s, g, r, p, ab, at, eid in con.execute(
        f"""SELECT series_id, game_id, round_num, player_id, ability, occurred_at, event_id
            FROM abilities WHERE game_id IN ({g_marks}) AND ability IN ({a_marks})""",
        [*games, *abilities],
    ):
        cast_times[s, g, r, p, ab].append((_ts(at), eid))
    for times in cast_times.values():
        times.sort()

    damage_by_cast: dict[str, int] = defaultdict(int)
    for s, g, r, p, src, at, amount in con.execute(
        f"""SELECT series_id, game_id, round_num, attacker_id, source, occurred_at, amount
            FROM damage WHERE game_id IN ({g_marks}) AND source IN ({a_marks})""",
        [*games, *abilities],
    ):
        times = cast_times.get((s, g, r, p, src))
        if not times:
            continue
        # bisect finds where this hit's time would slot into the sorted cast times;
        # the cast just before that position is the latest cast at or before the hit
        i = bisect.bisect_right(times, (_ts(at), "￿")) - 1
        if i >= 0:
            damage_by_cast[times[i][1]] += amount or 0

    # --- 3. kills / deaths in the window after each in-round cast -------------------------
    kills_by_round: dict[tuple, list[tuple[datetime, str, str]]] = defaultdict(list)
    for s, g, r, at, killer_team, victim_team in con.execute(
        f"""SELECT series_id, game_id, round_num, occurred_at, killer_team_id, victim_team_id
            FROM kills WHERE game_id IN ({g_marks})""",
        games,
    ):
        kills_by_round[s, g, r].append((_ts(at), killer_team, victim_team))

    # --- 1. baseline round win rate per (team, map, side) ---------------------------------
    baselines: dict[tuple[str, str], dict] = {}

    def baseline(team_id: str, map_name: str, side: str) -> float:
        if (team_id, map_name) not in baselines:
            rounds = load_team_rounds(con, team_id, map_name=map_name)
            baselines[team_id, map_name] = side_records(rounds)
        return baselines[team_id, map_name][side].win_rate

    scores = []
    for lu in lineups:
        base = baseline(lu.team_id, lu.map_name, lu.side)
        damage = sum(damage_by_cast.get(m.event_id, 0) for m in lu.members)
        in_round = kills = deaths = 0
        for m in lu.members:
            if m.in_buy_phase or not m.occurred_at:
                continue
            in_round += 1
            start = _ts(m.occurred_at)
            for at, killer_team, victim_team in kills_by_round[m.series_id, m.game_id, m.round_num]:
                if 0 < (at - start).total_seconds() <= window_s:
                    kills += killer_team == lu.team_id
                    deaths += victim_team == lu.team_id
        scores.append(
            LineupScore(
                lineup=lu,
                baseline=base,
                adjusted_win_rate=shrunk_rate(lu.rounds_won, lu.rounds, base, prior_rounds),
                ability_damage=damage,
                in_round_casts=in_round,
                window_kills=kills,
                window_deaths=deaths,
            )
        )
    scores.sort(key=lambda s: -s.score)
    return scores


def format_scores(scores: Sequence[LineupScore]) -> str:
    header = (
        f"{'#':>3} {'side':<9}{'agent':<10}{'ability':<17}{'rnds':>5}{'win %':>7}{'usual':>7}"
        f"{'score':>8}{'dmg/cast':>9}{'10s K-D':>9}   {'spot (x, y)':<16}"
    )
    lines = [header, "-" * len(header)]
    for i, s in enumerate(scores, 1):
        lu = s.lineup
        kd = f"{s.window_kills}-{s.window_deaths}" if s.in_round_casts else "setup"
        lines.append(
            f"{i:>3} {lu.side[:8]:<9}{lu.agent[:9]:<10}{lu.ability[:16]:<17}{lu.rounds:>5}"
            f"{lu.round_win_rate:>7.0%}{s.baseline:>7.0%}{s.score * 100:>+7.1f}p"
            f"{s.damage_per_cast:>9.0f}{kd:>9}   {f'({lu.x:.0f}, {lu.y:.0f})':<16}"
        )
    return "\n".join(lines)
