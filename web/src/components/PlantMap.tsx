// Spike plants on the minimap: the first real use of <Minimap> (W3). W4 reuses the same
// pieces for lineups and Operator angles.

import { apiUrl, type MapInfo, type Plant } from "../api";
import { secs } from "../format";
import { useApi } from "../useApi";
import { MapDot, Minimap } from "./Minimap";

const US = "#ff4655"; // our plants (we attacked)
const THEM = "#4fc3f7"; // their plants (we defended)

interface Props {
  map: string;
  plants: Plant[];
  side: string; // "" = both, else only rounds where the scouted team was on this side
  teamName: string;
}

export function PlantMap({ map, plants, side, teamName }: Props) {
  const mapInfo = useApi<MapInfo>(apiUrl(`/maps/${map}`));
  if (mapInfo.error) return <p className="error">{mapInfo.error}</p>;
  if (!mapInfo.data) return <p className="muted">Loading map…</p>;

  const shown = plants.filter((p) => !side || p.side === side);
  return (
    <Minimap
      map={mapInfo.data}
      legend={[
        { color: US, label: `${teamName} plants` },
        { color: THEM, label: "Opponent plants" },
        { color: "#8b978f", label: "hollow = planting team lost the round", hollow: true },
      ]}
    >
      {shown.map((p, i) => {
        const color = p.by_us ? US : THEM;
        // "won" in the data is from the scouted team's view; the planter won if they're "us"
        // and we won, or "them" and we lost
        const planterWon = p.by_us === p.won;
        return (
          <MapDot
            key={i}
            u={p.u}
            v={p.v}
            color={color}
            hollow={!planterWon}
            title={`${p.by_us ? teamName : "Opponent"} planted ${p.site} at ${secs(p.time_s)}, ${
              planterWon ? "won" : "lost"
            } the round`}
          />
        );
      })}
    </Minimap>
  );
}
