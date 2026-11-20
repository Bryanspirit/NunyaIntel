// "Who wins rounds": each player's round wins added per 100 rounds (from the win-chance model),
// split into what their kills earned, what their deaths cost, and plants / defuses.

import { apiUrl, type ImpactRow } from "../api";
import { useApi } from "../useApi";
import { playerPage, type Selection } from "../useSelection";
import { Panel } from "./broadcast";
import { Empty } from "./ui";

const signed = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}`;

export function ImpactPanel({ selection, index, onNavigate }: { selection: Selection; index: number; onNavigate: (c: Partial<Selection>) => void }) {
  const r = useApi<{ players: ImpactRow[] }>(apiUrl("/impact", { team: selection.team, map: selection.map }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Adding up every kill's swing…</p>;
  const rows = r.data.players.filter((p) => p.rounds >= 20);
  const peak = Math.max(1, ...rows.map((p) => Math.abs(p.per_100)));
  return (
    <Panel title="Who wins rounds" index={index}
      aside="round wins added per 100 rounds: every kill, death, plant and defuse, valued by how much it moved the win chance">
      {rows.length === 0 ? <Empty>Not enough rounds.</Empty> : (
        <table className="impact">
          <thead>
            <tr><th className="left">Player</th><th>Rounds</th><th className="left">Round wins added / 100</th>
              <th>From kills</th><th>From deaths</th><th>Plants / defuses</th><th>Per kill</th><th>League rank</th></tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id}>
                <td className="left"><button className="name-link" onClick={() => onNavigate(playerPage(p.player_id))}>{p.name}</button></td>
                <td>{p.rounds}</td>
                <td className="left">
                  <span className="impact-bar">
                    <span className={p.per_100 >= 0 ? "pos" : "neg"} style={{ width: `${(Math.abs(p.per_100) / peak) * 50}%` }} />
                  </span>
                  <b className={p.rounds < 200 ? "" : p.per_100 >= 0 ? "good" : "bad"}>{signed(p.per_100)}</b>
                </td>
                <td>{signed(p.kills_per_100)}</td>
                <td>{signed(p.deaths_per_100)}</td>
                <td>{signed(p.objectives_per_100)}</td>
                <td>{(p.per_kill * 100).toFixed(1)}%</td>
                <td>{p.rank ? `#${p.rank} of ${p.ranked}` : <span className="muted">under 200 rounds</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="note impact-note">
        +2 = about two extra round wins every 100 rounds compared with an average player in the same spots. "Per kill" =
        how much one kill moves the win chance on average: opening and clutch kills count for more than a kill in a 5v1.
        It describes what happened (the model is fitted on all rounds) and doesn't adjust for team strength.
      </p>
    </Panel>
  );
}
