"""T2: economy scouting: pistol rounds, what happens right after them, and buy-vs-buy results.

Terms
-----
- **Pistol round:** rounds 1 and 13; everyone starts with 800 credits.
- **Conversion:** after *winning* a pistol, did the team also win the next round (2 or 14)?
  The pistol winner is usually much richer that round, so failing to convert is costly.
- **Break:** after *losing* a pistol, did the team still win the next round (an upset)?
- **Buy matrix:** round win rate for every (own buy, opponent buy) pair. Highlights:
  *eco upsets* (team on eco/semi-eco beats a full buy) and *anti-eco losses* (team on a full buy
  loses to an eco/semi-eco).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nunyaintel.economy import ECONOMY_STATES, PISTOL_ROUNDS
from nunyaintel.scouting.overview import SIDES, SideRecord
from nunyaintel.scouting.team_rounds import TeamRound

POOR = ("eco", "semi-eco")


@dataclass(slots=True)
class PistolStats:
    pistols: dict[str, SideRecord]  # per side the team played the pistol on
    conversions: SideRecord  # rounds after a pistol win: won = converted
    breaks: SideRecord  # rounds after a pistol loss: won = broke the bonus


def pistol_stats(rounds: Sequence[TeamRound]) -> PistolStats:
    stats = PistolStats({side: SideRecord() for side in SIDES}, SideRecord(), SideRecord())
    by_round = {(r.game_id, r.round_num): r for r in rounds}
    for r in rounds:
        if r.round_num not in PISTOL_ROUNDS:
            continue
        stats.pistols[r.side].played += 1
        stats.pistols[r.side].won += r.won
        nxt = by_round.get((r.game_id, r.round_num + 1))
        if nxt is None:
            continue
        bucket = stats.conversions if r.won else stats.breaks
        bucket.played += 1
        bucket.won += nxt.won
    return stats


def buy_matrix(rounds: Sequence[TeamRound]) -> dict[tuple[str, str], SideRecord]:
    """``{(own_buy, opp_buy): SideRecord}`` for every pair that occurred."""
    matrix: dict[tuple[str, str], SideRecord] = {}
    for r in rounds:
        cell = matrix.setdefault((r.own_buy, r.opp_buy), SideRecord())
        cell.played += 1
        cell.won += r.won
    return matrix


def _combine(matrix: dict[tuple[str, str], SideRecord], own: Sequence[str], opp: Sequence[str]):
    total = SideRecord()
    for (o, p), cell in matrix.items():
        if o in own and p in opp:
            total.played += cell.played
            total.won += cell.won
    return total


def eco_upsets(matrix: dict[tuple[str, str], SideRecord]) -> SideRecord:
    """Team on eco/semi-eco vs. opponent full buy: ``won`` = upsets."""
    return _combine(matrix, POOR, ("full-buy",))


def anti_eco(matrix: dict[tuple[str, str], SideRecord]) -> SideRecord:
    """Team on full buy vs. opponent eco/semi-eco: ``played - won`` = rounds thrown away."""
    return _combine(matrix, ("full-buy",), POOR)


def format_economy(rounds: Sequence[TeamRound]) -> str:
    ps = pistol_stats(rounds)
    lines = ["Pistol rounds"]
    for side in SIDES:
        rec = ps.pistols[side]
        lines.append(f"  on {side:<9}: {rec.won}/{rec.played} won ({rec.win_rate:.0%})")
    c, b = ps.conversions, ps.breaks
    lines.append(f"  after a pistol win, won next round:  {c.won}/{c.played} ({c.win_rate:.0%})")
    lines.append(f"  after a pistol loss, won next round: {b.won}/{b.played} ({b.win_rate:.0%})")

    matrix = buy_matrix(rounds)
    up, ae = eco_upsets(matrix), anti_eco(matrix)
    lines.append("\nEconomy")
    lines.append(
        f"  eco upsets (our eco vs their full buy):  {up.won}/{up.played} ({up.win_rate:.0%})"
    )
    lost = ae.played - ae.won
    lost_rate = lost / ae.played if ae.played else 0.0
    lines.append(f"  anti-eco losses (our full buy vs eco):   {lost}/{ae.played} ({lost_rate:.0%})")

    states = [s for s in ECONOMY_STATES if s != "pistol"]
    lines.append("\nRound win % by buy (rows = us, columns = them; rounds in brackets)")
    lines.append(f"  {'':<10}" + "".join(f"{s:>14}" for s in states))
    for own in states:
        cells = []
        for opp in states:
            cell = matrix.get((own, opp))
            cells.append(f"{f'{cell.win_rate:.0%} ({cell.played})' if cell else '-':>14}")
        lines.append(f"  {own:<10}" + "".join(cells))
    return "\n".join(lines)
