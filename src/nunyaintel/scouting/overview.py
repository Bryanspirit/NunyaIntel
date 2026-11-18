"""T1: team overview: maps played, round win % per side, and how rounds are won and lost.

All functions take the ``TeamRound`` list from ``load_team_rounds`` and just count, so they are
easy to test with hand-made rounds.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from nunyaintel.scouting.team_rounds import TeamRound

SIDES = ("attacker", "defender")

# VALORANT rule worth knowing when reading win types: if defenders kill every attacker *after*
# the spike is planted, they still have to defuse it, and the round ends as "bombDefused".
WIN_TYPE_LABELS = {
    "opponentEliminated": "elimination",
    "bombExploded": "spike detonated",
    "bombDefused": "spike defused",
    "timeExpired": "time ran out",
}


@dataclass(slots=True)
class SideRecord:
    won: int = 0
    played: int = 0

    @property
    def win_rate(self) -> float:
        return self.won / self.played if self.played else 0.0


@dataclass(slots=True)
class MapRecord:
    map_name: str
    games: int
    games_won: int
    rounds_won: int
    rounds_lost: int
    attack: SideRecord
    defense: SideRecord

    @property
    def round_win_rate(self) -> float:
        total = self.rounds_won + self.rounds_lost
        return self.rounds_won / total if total else 0.0


def map_records(rounds: Sequence[TeamRound]) -> list[MapRecord]:
    """Per map: games and game wins, rounds won/lost, and attack/defense round win rates.

    A game counts as won if the team won more of its rounds (matches the final score: the
    extract's round winners were verified against every map's final score).
    """
    by_game: dict[str, list[TeamRound]] = defaultdict(list)
    for r in rounds:
        by_game[r.game_id].append(r)

    records: dict[str, MapRecord] = {}
    for game_rounds in by_game.values():
        name = game_rounds[0].map_name
        rec = records.setdefault(name, MapRecord(name, 0, 0, 0, 0, SideRecord(), SideRecord()))
        won = sum(r.won for r in game_rounds)
        lost = len(game_rounds) - won
        rec.games += 1
        rec.games_won += won > lost
        rec.rounds_won += won
        rec.rounds_lost += lost
        for r in game_rounds:
            side = rec.attack if r.side == "attacker" else rec.defense
            side.played += 1
            side.won += r.won
    return sorted(records.values(), key=lambda m: (-m.games, m.map_name))


def side_records(rounds: Sequence[TeamRound]) -> dict[str, SideRecord]:
    """Round win rate per side across all the given rounds."""
    out = {side: SideRecord() for side in SIDES}
    for r in rounds:
        out[r.side].played += 1
        out[r.side].won += r.won
    return out


def win_types(rounds: Sequence[TeamRound]) -> dict[str, dict[str, Counter[str]]]:
    """``{side: {"won": Counter(win_type), "lost": Counter(win_type)}}``.

    E.g. on defense, "lost" by "bombExploded" = the opponent's plant went off.
    """
    out: dict[str, dict[str, Counter[str]]] = {
        side: {"won": Counter(), "lost": Counter()} for side in SIDES
    }
    for r in rounds:
        out[r.side]["won" if r.won else "lost"][r.win_type] += 1
    return out


def format_overview(rounds: Sequence[TeamRound]) -> str:
    lines = [
        f"{'map':<10}{'games':>6}{'won':>5}{'rounds':>9}{'round %':>9}{'atk %':>8}{'def %':>8}",
        "-" * 55,
    ]
    for m in map_records(rounds):
        lines.append(
            f"{m.map_name:<10}{m.games:>6}{m.games_won:>5}"
            f"{f'{m.rounds_won}-{m.rounds_lost}':>9}{m.round_win_rate:>9.0%}"
            f"{m.attack.win_rate:>8.0%}{m.defense.win_rate:>8.0%}"
        )
    sides = side_records(rounds)
    lines.append("-" * 55)
    lines.append(
        f"{'all':<10}{'':>20}{'':>9}{'':>0}"
        f"{sides['attacker'].win_rate:>8.0%}{sides['defender'].win_rate:>8.0%}"
    )

    lines.append("\nHow rounds end (share of that side's won / lost rounds)")
    wt = win_types(rounds)
    for side in SIDES:
        for outcome in ("won", "lost"):
            counts = wt[side][outcome]
            total = sum(counts.values())
            parts = ", ".join(
                f"{WIN_TYPE_LABELS.get(k, k)} {v / total:.0%}" for k, v in counts.most_common()
            )
            lines.append(f"  {side:<9} {outcome:<5} ({total:>3}): {parts}")
    return "\n".join(lines)
