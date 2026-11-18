// Scouting (T1/T2/T3). So far: header, per-map table and (with a map selected) the plant map.
// W4 adds economy, sites, setups and opening duels.

import { apiUrl, type Scout } from "../api";
import { PlantMap } from "../components/PlantMap";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

export function ScoutingPage({ selection }: { selection: Selection }) {
  const { data, error, loading } = useApi<Scout>(
    apiUrl("/scout", { team: selection.team, map: selection.map, since: selection.since }),
  );

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">{loading ? "Loading…" : ""}</p>;
  if (!data.maps) return <p className="muted">No rounds for {data.team.name} with these filters.</p>;

  return (
    <section className={loading ? "stale" : ""}>
      <h2>
        {data.team.name}
        {selection.map && ` on ${title(selection.map)}`}
      </h2>
      <p className="muted">
        {data.games} maps · {data.rounds} rounds · {data.first?.slice(0, 10)} → {data.last?.slice(0, 10)}
      </p>

      <table>
        <thead>
          <tr>
            <th>Map</th>
            <th>Games</th>
            <th>Won</th>
            <th>Rounds</th>
            <th>Round %</th>
            <th>Attack %</th>
            <th>Defense %</th>
          </tr>
        </thead>
        <tbody>
          {data.maps.map((m) => (
            <tr key={m.map}>
              <td>{title(m.map)}</td>
              <td>{m.games}</td>
              <td>{m.games_won}</td>
              <td>
                {m.rounds_won}–{m.rounds_lost}
              </td>
              <td>{pct(m.round_win_rate)}</td>
              <td>{pct(m.attack.win_rate)}</td>
              <td>{pct(m.defense.win_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selection.map && data.sites && (
        <>
          <h3>Spike plants</h3>
          <PlantMap map={selection.map} plants={data.sites.plants} side={selection.side} teamName={data.team.name} />
        </>
      )}
    </section>
  );
}
