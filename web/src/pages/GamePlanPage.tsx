// Game plan: written advice for playing one opponent. Every line shows its evidence (with counts)
// and a link to the view that proves it. Print it (or save as PDF) for a coach's sheet.

import { Glossed } from "../components/Help";
import { apiUrl, type GamePlan, type GamePlanItem, type Meta } from "../api";
import { OpponentPicker } from "../components/OpponentPicker";
import { PageHero } from "../components/broadcast";
import { Reveal } from "../components/motion";
import { Empty } from "../components/ui";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

type Nav = (change: Partial<Selection>) => void;

const SECTIONS: { key: GamePlanItem["section"]; title: string; blurb: string }[] = [
  { key: "veto", title: "Map veto", blurb: "where we're furthest ahead / behind" },
  { key: "map", title: "Site plan", blurb: "attack their weakest hold, stack their favourite site" },
  { key: "playstyle", title: "Their playstyle", blurb: "how they hit and open rounds on this map, where it's unusual" },
  { key: "exploit", title: "Exploit", blurb: "their weaknesses vs. the league" },
  { key: "respect", title: "Respect", blurb: "their strengths vs. the league" },
  { key: "utility", title: "Expect this utility", blurb: "their most-used lineups on the map" },
  { key: "operator", title: "Their Operator", blurb: "who holds it and how often" },
  { key: "clutch", title: "Tight rounds", blurb: "retakes, post-plants and clutches, against the league in the same situations" },
  { key: "economy", title: "Their economy", blurb: "a buy habit unlike the league's" },
  { key: "watch", title: "Watch our own leaks", blurb: "what a scouting opponent will find on us" },
];

export function GamePlanPage({ selection, meta, onNavigate }: { selection: Selection; meta: Meta | null; onNavigate: Nav }) {
  const r = useApi<GamePlan>(apiUrl("/gameplan", { team: selection.team, opponent: selection.opp, map: selection.map }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Writing the game plan…</p>;
  const { a, b, map, map_was_chosen, elo, head_to_head, items } = r.data;
  let order = 0;

  return (
    <section className="gameplan" key={`${a.id}|${b.id}|${map}`}>
      <PageHero kicker={`Game plan${map ? ` · ${title(map)}` : ""}`} title={`${a.name} vs ${b.name}`}
        stats={[
          { label: "Elo: chance to win a map", value: elo.p_a_wins_map, kind: "pct" },
          { label: `Head-to-head maps won (of ${head_to_head.maps})`, value: head_to_head.won,
            tone: head_to_head.maps === 0 ? undefined : head_to_head.won * 2 >= head_to_head.maps ? "good" : "bad" },
        ]}
      />
      <div className="plan-bar no-print">
        <OpponentPicker meta={meta} selection={selection} current={b.name} onNavigate={onNavigate} />
        <button className="chip" onClick={() => onNavigate({ tab: "matchup", opp: b.id })}>⇄ Full matchup report</button>
        <button className="chip active" onClick={() => window.print()}>🖨 Print / save as PDF</button>
      </div>
      {!map_was_chosen && map && (
        <p className="muted">No map picked, so the site plan is for the suggested pick, {title(map)}. Choose a map above to change it.</p>
      )}

      {items.length === 0 && <Empty>Not enough data on these two teams for a plan.</Empty>}
      {SECTIONS.map((sec) => {
        const rows = items.filter((i) => i.section === sec.key);
        if (rows.length === 0) return null;
        return (
          <div key={sec.key} className={`plan-section plan-${sec.key}`}>
            <h3 className="plan-head">{sec.title} <span className="muted">{sec.blurb}</span></h3>
            {rows.map((it) => (
              <Reveal key={it.advice} as="article" className="plan-item" delay={100 + order++ * 60}>
                <div className="plan-advice">
                  <Glossed text={it.advice} />
                  {it.small && <span className="bigstat-small plan-small">small sample</span>}
                </div>
                <div className="plan-evidence">
                  {it.evidence}
                  <button className="link no-print" onClick={() => onNavigate({ ...it.view, round: "", t: "" })}>see it →</button>
                </div>
              </Reveal>
            ))}
          </div>
        );
      })}
      <p className="note plan-foot">
        Advice is generated from tested numbers: league comparisons are z-scores against all {meta?.teams.length ?? ""} teams'
        rounds; "small sample" = fewer than 30 rounds behind it, treat as a lead. Elo map chance: {pct(elo.p_a_wins_map)}.
      </p>
    </section>
  );
}
