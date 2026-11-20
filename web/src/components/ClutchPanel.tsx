// Clutches, retakes and post-plant holds: each compared with how often the league wins the same
// situation (same numbers alive, spike, time). Only gaps beyond luck (|z| >= 1.5, 10+ cases) get
// colour. Works on all maps; plant sites appear once a map is picked.

import { apiUrl } from "../api";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import { playerPage, replayAt, type Selection } from "../useSelection";
import { Panel } from "./broadcast";
import { Glossed } from "./Help";

interface Tally { n: number; won: number; expected: number; above: number; z: number; notable: boolean }
interface Clutch {
  team_id: string;
  map: string | null;
  clutch: Tally & {
    by_vs: (Tally & { vs: number })[];
    players: (Tally & { id: string; name: string })[];
    best: { key: string; map: string; player: { id: string; name: string }; vs: number; p: number; planted: boolean }[];
  };
  retake: Tally & { sites: (Tally & { site: string })[] };
  post_plant: Tally & { sites: (Tally & { site: string })[] };
}

const SMALL = 30;
const KIND_TEXT = { clutch: "clutches (last player alive)", retake: "retakes after the spike goes down", post_plant: "post-plants (holding their own plant)" };

/** "+2.3" / "−1.1" with the colour only when the gap is beyond luck. */
function Above({ t }: { t: Tally }) {
  const tone = t.notable && t.n >= SMALL ? (t.above > 0 ? "good" : "bad") : "";
  return (
    <span className={`above ${tone}`} title={`${t.z >= 0 ? "+" : ""}${t.z.toFixed(1)} standard errors`}>
      {t.above >= 0 ? "+" : "−"}{Math.abs(t.above).toFixed(1)}
    </span>
  );
}

function Row({ label, t }: { label: React.ReactNode; t: Tally }) {
  return (
    <tr>
      <td className="left">{label}</td>
      <td>{t.won} / {t.n}</td>
      <td>{t.n ? pct(t.won / t.n) : "–"}</td>
      <td className="muted">{t.n ? pct(t.expected / t.n) : "–"}</td>
      <td><Above t={t} />{t.n < SMALL && <span className="muted small-tag" title="fewer than 30: a lead, not a verdict"> small</span>}</td>
    </tr>
  );
}

const Head = ({ first }: { first: string }) => (
  <thead><tr><th className="left">{first}</th><th>Won</th><th>Rate</th><th>League</th><th>Above expected</th></tr></thead>
);

export function ClutchPanel({ selection, onNavigate, index }: {
  selection: Selection; onNavigate: (c: Partial<Selection>) => void; index: number;
}) {
  const r = useApi<Clutch>(apiUrl("/clutch", { team: selection.team, map: selection.map || undefined }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Replaying every tight round…</p>;
  const d = r.data;
  const where = d.map ? `on ${title(d.map)}` : "on all maps";
  const notable = ([
    ["clutch", d.clutch], ["retake", d.retake], ["post_plant", d.post_plant],
    ...d.retake.sites.map((s) => [`retake_${s.site}`, s] as const),
    ...d.post_plant.sites.map((s) => [`post_plant_${s.site}`, s] as const),
  ] as [string, Tally & { site?: string }][]).filter(([, t]) => t.notable);

  const describe = (key: string, t: Tally & { site?: string }) => {
    if (key.startsWith("retake_")) return `retakes on ${t.site}`;
    if (key.startsWith("post_plant_")) return `post-plants on ${t.site}`;
    return KIND_TEXT[key as keyof typeof KIND_TEXT];
  };

  return (
    <Panel title={`Clutches and retakes ${where}`} index={index}
      aside="each compared with how often the league wins the same situation: same numbers alive, spike and time">
      {notable.length > 0 ? (
        <div className="recent-summary">
          {notable.map(([key, t]) => (
            <p key={key} className={t.above > 0 ? "better" : "worse"}>
              <b>{t.above > 0 ? "▲ Better" : "▼ Worse"}</b> than the league at <Glossed text={describe(key, t)} />:{" "}
              won {t.won} of {t.n} where the league would win {t.expected.toFixed(1)}{" "}
              <span className="muted">({Math.abs(t.z).toFixed(1)} standard errors{t.n < SMALL ? ", small sample" : ""})</span>
            </p>
          ))}
        </div>
      ) : (
        <p className="recent-summary"><b>Normal in tight rounds:</b> nothing differs from the league beyond luck {where}.</p>
      )}

      <div className="grid-2">
        <div>
          <h4 className="subhead">Situations</h4>
          <table className="clutch-table">
            <Head first="" />
            <tbody>
              <Row label={<Glossed text="Clutch (last player alive)" />} t={d.clutch} />
              {d.clutch.by_vs.map((v) => <Row key={v.vs} label={<span className="indent">1v{v.vs}</span>} t={v} />)}
              <Row label={<Glossed text="Retake (they defend, spike down)" />} t={d.retake} />
              {d.retake.sites.map((s) => <Row key={s.site} label={<span className="indent">on {s.site}</span>} t={s} />)}
              <Row label={<Glossed text="Post-plant (they attack and plant)" />} t={d.post_plant} />
              {d.post_plant.sites.map((s) => <Row key={s.site} label={<span className="indent">on {s.site}</span>} t={s} />)}
            </tbody>
          </table>
          {!d.map && <p className="note">Pick a map to split retakes and post-plants by site.</p>}
        </div>
        <div>
          <h4 className="subhead">Who clutches</h4>
          {d.clutch.players.length === 0 ? <p className="muted">Too few clutches to compare players.</p> : (
            <table className="clutch-table">
              <Head first="Last player alive" />
              <tbody>
                {d.clutch.players.map((p) => (
                  <Row key={p.id} t={p}
                    label={<button className="name-link" onClick={() => onNavigate(playerPage(p.id))}>{p.name}</button>} />
                ))}
              </tbody>
            </table>
          )}
          {d.clutch.best.length > 0 && (
            <>
              <h4 className="subhead">Least likely clutches won</h4>
              <ul className="clutch-best">
                {d.clutch.best.map((e) => (
                  <li key={e.key}>
                    <button className="link" onClick={() => onNavigate({ map: e.map, ...replayAt(e.key, -3) })}>
                      {e.player.name} · 1v{e.vs}{e.planted ? " · spike down" : ""} · {title(e.map)}
                    </button>{" "}
                    <span className="muted">league wins {pct(e.p, 1)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}
