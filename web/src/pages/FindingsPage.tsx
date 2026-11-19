// Key findings (P3): the landing view. The server ranks findings by how unusual and how
// reliable they are vs. the league (z-score), so the most important facts come first.

import { apiUrl, type Finding, type Findings } from "../api";
import { Empty } from "../components/ui";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import type { Selection, Tab } from "../useSelection";

const KIND_LABEL = { strength: "Strength", weakness: "Weakness", tendency: "Tendency" } as const;

interface Props {
  selection: Selection;
  onNavigate: (change: Partial<Selection>) => void;
}

export function FindingsPage({ selection, onNavigate }: Props) {
  const { data, error, loading } = useApi<Findings>(
    apiUrl("/findings", { team: selection.team, map: selection.map, since: selection.since }),
  );

  if (error) return <p className="error">{error}</p>;
  if (!data) {
    return (
      <p className="muted">
        {loading ? "Comparing with the league… (the first time after a fresh build takes about a minute)" : ""}
      </p>
    );
  }
  if (data.rounds === 0) return <Empty>No rounds for {data.team.name} with these filters.</Empty>;

  const go = (f: Finding) => onNavigate({ tab: f.tab as Tab, map: f.map ?? selection.map });

  return (
    <section className={loading ? "stale" : ""}>
      <h2>Key findings: {data.team.name}</h2>
      <p className="muted">
        {data.maps} maps · {data.rounds} rounds · compared with every team in the data. Most unusual (and best-supported) first.
      </p>

      <div className="findings">
        {data.league.map((f) => (
          <FindingCard key={f.key} f={f} onDetails={() => go(f)} />
        ))}
      </div>

      {data.map && data.map_findings.length > 0 && (
        <>
          <h3>
            On {title(data.map)}
            {!data.map_was_chosen && <span className="muted"> (their most-played map; pick a map to change)</span>}
          </h3>
          <div className="findings">
            {data.map_findings.map((f) => (
              <FindingCard key={f.key} f={f} onDetails={() => go(f)} />
            ))}
          </div>
        </>
      )}

      <p className="note">
        How findings are ranked: each rate is compared with the league using a z-score (how many standard errors the team is
        from the league average, given its sample size). So 15 of 50 beats 3 of 4, even though 3 of 4 is the bigger
        percentage. "Tendency" = within normal variation, shown for context.
      </p>
    </section>
  );
}

function FindingCard({ f, onDetails }: { f: Finding; onDetails: () => void }) {
  return (
    <article className={`finding ${f.kind}`}>
      <div className="finding-top">
        <span className={`kind ${f.kind}`}>{KIND_LABEL[f.kind]}</span>
        {f.rank !== null && f.ranked_teams !== null && (
          <span className="muted">
            #{f.rank} of {f.ranked_teams}
          </span>
        )}
      </div>
      <h4>{f.headline}</h4>
      <p className="finding-detail">{f.detail}</p>
      {f.league_rate !== null && <CompareBar team={f.rate} league={f.league_rate} />}
      <button className="link" onClick={onDetails}>
        Details →
      </button>
    </article>
  );
}

/** Team rate vs. league rate on one 0–100% track. */
function CompareBar({ team, league }: { team: number; league: number }) {
  return (
    <div className="compare" title={`team ${pct(team)} vs league ${pct(league, 1)}`}>
      <div className="compare-track">
        <span className="compare-team" style={{ width: `${team * 100}%` }} />
        <span className="compare-league" style={{ left: `${league * 100}%` }} />
      </div>
      <div className="compare-legend muted">
        <span>team {pct(team)}</span>
        <span>league {pct(league, 1)}</span>
      </div>
    </div>
  );
}
