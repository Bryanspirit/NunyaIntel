// Round win % for every (our buy, their buy) pair, as a heat table.
// Cell colour: green above 50%, red below; faint when there are few rounds.

import type { Rec } from "../api";
import { pct } from "../format";

const STATES = ["eco", "semi-eco", "semi-buy", "full-buy"]; // pistol rounds are shown separately

type Cell = { own: string; opp: string } & Rec;

function background(cell: Cell): string {
  const strength = Math.min(1, cell.played / 20); // fade cells with few rounds
  const delta = cell.win_rate - 0.5;
  const rgb = delta >= 0 ? "61, 220, 151" : "255, 107, 107";
  return `rgba(${rgb}, ${(Math.abs(delta) * 1.6 * strength).toFixed(2)})`;
}

export function BuyMatrix({ cells, team }: { cells: Cell[]; team: string }) {
  const lookup = new Map(cells.map((c) => [`${c.own}|${c.opp}`, c]));
  return (
    <table className="matrix">
      <thead>
        <tr>
          <th className="left">
            {team} ↓ / opponent →
          </th>
          {STATES.map((s) => (
            <th key={s}>{s}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {STATES.map((own) => (
          <tr key={own}>
            <td className="left">{own}</td>
            {STATES.map((opp) => {
              const cell = lookup.get(`${own}|${opp}`);
              return cell ? (
                <td key={opp} className="cell" style={{ background: background(cell) }}
                  title={`${cell.won}/${cell.played} rounds won`}>
                  {pct(cell.win_rate)} <span className="muted">({cell.played})</span>
                </td>
              ) : (
                <td key={opp} className="muted">–</td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
