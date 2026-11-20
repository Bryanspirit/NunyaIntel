// Playstyle fingerprint on one map: when the team plants (fast / default / late), how it opens
// rounds, how often it fakes, and how early fights start on its defense, each vs. the league.
// Only differences beyond luck (|z| >= 1.5) get colour; the rest are labelled "like the league".

import { apiUrl } from "../api";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";
import { Panel } from "./broadcast";
import { Glossed } from "./Help";

type Pace = "fast" | "default" | "late" | "no plant";
interface Rate { hits: number; n: number; rate: number | null; league_rate?: number | null; z?: number; notable?: boolean }
interface Side {
  attack_rounds: number;
  pace: Record<Pace, { share: number; n: number; won: number; win_rate: number | null }>;
  median_plant_s: number | null;
  plant_hist: number[];
  median_first_contact_s: number | null;
  rates: Record<"fast" | "late" | "no_plant" | "first_kill" | "fake" | "early_fight", Rate>;
  fake_win_rate: number | null;
}
interface Playstyle { map: string; team: Side; league: Side; thresholds: { fast: number; late: number; early_fight: number } }

const PACES: Pace[] = ["fast", "default", "late", "no plant"];
const PACE_COLOR: Record<Pace, string> = { fast: "#ff4655", default: "#f5c56b", late: "#4fc3f7", "no plant": "#5b6b78" };

const RATE_TEXT: Record<keyof Side["rates"], string> = {
  fast: "attack rounds with a fast plant (under 35 s)",
  late: "attack rounds with a late plant (after 70 s)",
  no_plant: "attack rounds with no plant",
  first_kill: "attack rounds where they get the first kill",
  fake: "planted rounds that were fakes (utility on another site)",
  early_fight: "defense rounds with a fight in the first 15 s",
};

export function PlaystylePanel({ selection, teamName, index }: { selection: Selection; teamName: string; index: number }) {
  const r = useApi<Playstyle>(selection.map ? apiUrl("/playstyle", { team: selection.team, map: selection.map }) : null);
  if (!selection.map) return null;
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Reading their timings…</p>;
  const { team, league } = r.data;
  const notable = (Object.keys(team.rates) as (keyof Side["rates"])[]).filter((k) => team.rates[k].notable);
  return (
    <Panel title={`Playstyle on ${title(selection.map)}`} index={index}
      aside={`${team.attack_rounds} attack rounds · time = seconds after the buy phase · compared with every team on this map`}>
      {notable.length > 0 ? (
        <div className="recent-summary">
          {notable.map((k) => {
            const t = team.rates[k];
            return (
              <p key={k}>
                <b className={t.z! > 0 ? "hi" : "lo"}>{t.z! > 0 ? "▲ More" : "▼ Fewer"}</b>{" "}
                <Glossed text={RATE_TEXT[k]} />: {pct(t.rate ?? 0)} vs league {pct(t.league_rate ?? 0)}
                {" "}<span className="muted">({t.hits} of {t.n}; {Math.abs(t.z!).toFixed(1)} standard errors)</span>
              </p>
            );
          })}
        </div>
      ) : (
        <p className="recent-summary"><b>Plays this map at a normal pace:</b> nothing differs from the league beyond luck.</p>
      )}

      <div className="grid-2">
        <div>
          <h4 className="subhead">When they plant</h4>
          {[["team", teamName, team], ["league", "League", league]].map(([key, label, side]) => (
            <div key={key as string} className="pace-row">
              <span className="pace-label">{label as string}</span>
              <span className="pace-bar">
                {PACES.map((p) => (
                  <span key={p} style={{ width: `${(side as Side).pace[p].share * 100}%`, background: PACE_COLOR[p] }}
                    title={`${p}: ${pct((side as Side).pace[p].share)} of attack rounds, won ${pct((side as Side).pace[p].win_rate ?? 0)}`} />
                ))}
              </span>
            </div>
          ))}
          <div className="pace-legend">
            {PACES.map((p) => (
              <span key={p}><i style={{ background: PACE_COLOR[p] }} />{p === "fast" ? "fast < 35 s" : p === "default" ? "default 35–70 s" : p === "late" ? "late > 70 s" : "no plant"}</span>
            ))}
          </div>
          <table>
            <thead><tr><th className="left">Hit</th><th>{teamName}</th><th>…won</th><th>League</th><th>…won</th></tr></thead>
            <tbody>
              {PACES.map((p) => (
                <tr key={p}>
                  <td className="left">{p}</td>
                  <td>{pct(team.pace[p].share)} <span className="muted">({team.pace[p].n})</span></td>
                  <td>{team.pace[p].win_rate === null ? "–" : pct(team.pace[p].win_rate)}</td>
                  <td>{pct(league.pace[p].share)}</td>
                  <td>{league.pace[p].win_rate === null ? "–" : pct(league.pace[p].win_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h4 className="subhead">Plant times <span className="muted">(bars: {teamName} · outline: league)</span></h4>
          <PlantHist team={team.plant_hist} league={league.plant_hist} />
          <div className="ps-stats">
            <span><b>{team.median_plant_s?.toFixed(0) ?? "–"} s</b> median plant <span className="muted">(league {league.median_plant_s?.toFixed(0)} s)</span></span>
            <span><b>{team.median_first_contact_s?.toFixed(0) ?? "–"} s</b> first contact on attack <span className="muted">(league {league.median_first_contact_s?.toFixed(0)} s)</span></span>
          </div>
          <table>
            <thead><tr><th className="left">Rate</th><th>{teamName}</th><th>League</th><th>vs league</th></tr></thead>
            <tbody>
              {(["first_kill", "fake", "early_fight", "no_plant"] as const).map((k) => {
                const t = team.rates[k];
                return (
                  <tr key={k}>
                    <td className="left"><Glossed text={RATE_TEXT[k]} /></td>
                    <td>{t.rate === null ? "–" : pct(t.rate)} <span className="muted">({t.hits}/{t.n})</span></td>
                    <td>{t.league_rate == null ? "–" : pct(t.league_rate)}</td>
                    <td className={t.notable ? "hi-cell" : "muted"}>{t.notable ? `${t.z! > 0 ? "+" : ""}${t.z!.toFixed(1)} SE` : "like the league"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <p className="note">
        A fake = most of their pre-plant utility near a site went to one site (2+ casts within 20 m) but they planted the other.
        Defense "fight in the first 15 s" = early aggression or being rushed. "Like the league" = within 1.5 standard errors.
      </p>
    </Panel>
  );
}

function PlantHist({ team, league }: { team: number[]; league: number[] }) {
  const W = 600, H = 120, n = team.length, peak = Math.max(...team, ...league, 0.01);
  const bw = W / n, y = (v: number) => H - 14 - (v / peak) * (H - 22);
  const outline = league.map((v, i) => `${i ? "L" : "M"} ${i * bw} ${y(v)} L ${(i + 1) * bw} ${y(v)}`).join(" ");
  return (
    <svg className="plant-hist" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      {team.map((v, i) => <rect key={i} x={i * bw + 1} y={y(v)} width={bw - 2} height={H - 14 - y(v)} className="ph-bar" />)}
      <path d={outline} className="ph-league" />
      {[35, 70].map((s) => <line key={s} x1={(s / 5) * bw} x2={(s / 5) * bw} y1={0} y2={H - 14} className="half-line" />)}
      {[0, 30, 60, 90].map((s) => <text key={s} x={(s / 5) * bw + 2} y={H - 2} className="ph-axis">{s}s</text>)}
    </svg>
  );
}
