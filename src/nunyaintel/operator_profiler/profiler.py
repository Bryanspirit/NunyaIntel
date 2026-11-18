"""Profile who buys the Operator, where they hold, and how impactful it is."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OperatorProfile:
    player_id: str
    rounds_with_op: int = 0
    op_kills: int = 0
    first_bloods_with_op: int = 0

    @property
    def kills_per_op_round(self) -> float:
        return self.op_kills / self.rounds_with_op if self.rounds_with_op else 0.0


# TODO: buy rates by economy state, common angles held per map/side, opening duel success.
