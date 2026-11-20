// Best-of-3 veto simulator: who bans and picks what (from map records), the decider, and the
// series odds (overall Elo + the best-of-3 formula). Map-specific strength was tested and did
// NOT beat plain Elo on unseen matches, so it decides the veto, not the odds.

import { apiUrl } from "../api";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";
import { Panel } from "./broadcast";
import { CountUp } from "./motion";

interface PoolRow { map: string; a_rate: number; a_rounds: number; b_rate: number; b_rounds: number; edge_a: number }
interface Veto {
  a: { id: string; name: string }; b: { id: string; name: string };
  pool: PoolRow[];
  steps: { team: "a" | "b"; action: "ban" | "pick"; map: string; edge_a: number }[];
  decider: string; order: string[]; p_map: number; series_p_a: number;
  model: { test_maps: number; brier: number; accuracy: number; plain_elo_brier: number; plain_elo_accuracy: number };
}

export function VetoPanel({ selection, index, onNavigate }: { selection: Selection; index: number; onNavigate: (c: Partial<Selection>) => void }) {
  const r = useApi<Veto>(apiUrl("/veto", { team: selection.team, opponent: selection.opp }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Playing out the veto…</p>;
  const v = r.data;
  const rows = new Map(v.pool.map((p) => [p.map, p]));
  const cards = [...v.steps, { team: null, action: "decider" as const, map: v.decider, edge_a: rows.get(v.decider)?.edge_a ?? 0 }];
  const name = (t: "a" | "b" | null) => (t === "a" ? v.a.name : t === "b" ? v.b.name : "");
  return (
    <Panel title="Map veto (best of 3)" index={index}
      aside="each team bans where it's furthest behind, picks where it's furthest ahead (round win % vs. its usual)">
      <div className="veto">
        {cards.map((c, i) => (
          <button key={c.map} className={`veto-card ${c.action} ${c.team ?? ""}`} style={{ animationDelay: `${i * 90}ms` }}
            title={`Open the matchup on ${title(c.map)}`} onClick={() => onNavigate({ map: c.map })}>
            <span className="veto-step">{c.action === "decider" ? "Decider" : `${name(c.team)} ${c.action}s`}</span>
            <span className="veto-map">{title(c.map)}</span>
            <span className="veto-edge">{v.a.name} {c.edge_a >= 0 ? "+" : "−"}{Math.abs(c.edge_a * 100).toFixed(1)} pts vs usual</span>
          </button>
        ))}
      </div>
      <div className="veto-odds">
        <div>
          <b><CountUp value={v.series_p_a * 100} delay={300} format={(x) => `${x.toFixed(0)}%`} /></b>
          <span>{v.a.name} wins the series</span>
        </div>
        <div className="muted">
          {pct(v.p_map)} per map (overall Elo) → {pct(v.series_p_a)} over a best of 3: a longer series favours the stronger team.
          Maps played: {v.order.map(title).join(" → ")}.
        </div>
      </div>
      <table>
        <thead><tr><th className="left">Map</th><th>{v.a.name} round win %</th><th>{v.b.name} round win %</th><th>{v.a.name}'s edge vs usual</th></tr></thead>
        <tbody>
          {v.pool.map((p) => (
            <tr key={p.map}>
              <td className="left">{title(p.map)}</td>
              <td>{pct(p.a_rate)} <span className="muted">({p.a_rounds})</span></td>
              <td>{pct(p.b_rate)} <span className="muted">({p.b_rounds})</span></td>
              <td className={p.edge_a > 0.01 ? "good" : p.edge_a < -0.01 ? "bad" : "muted"}>{p.edge_a >= 0 ? "+" : "−"}{Math.abs(p.edge_a * 100).toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">
        Pool = the 7 most-played maps in the data's last 120 days. Round win rates are shrunk toward each team's usual rate
        (60 rounds' weight), so a few rounds can't decide a pick. <b>Why the odds ignore the maps:</b> we tested per-map
        strength on the latest {v.model.test_maps} maps. It was right {pct(v.model.accuracy, 1)} of the time (Brier {v.model.brier.toFixed(3)})
        against plain Elo's {pct(v.model.plain_elo_accuracy, 1)} ({v.model.plain_elo_brier.toFixed(3)}): past map results didn't predict new ones,
        so the veto tells you what to prepare, not who wins.
      </p>
    </Panel>
  );
}
