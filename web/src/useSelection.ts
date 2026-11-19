// The user's current selection (team, map, side, tab, since), kept in the page URL:
//   http://127.0.0.1:5173/?team=79&map=lotus&tab=scouting
// so a view can be bookmarked, shared with a teammate, or reloaded without losing it.

import { useCallback, useEffect, useState } from "react";

export type Tab = "findings" | "scouting" | "operator" | "utility" | "replay" | "predict";
export const TABS: Tab[] = ["findings", "scouting", "operator", "utility", "replay", "predict"];

export interface Selection {
  team: string; // team id
  map: string; // "" = all maps
  side: string; // "" = both sides
  since: string; // "" = all dates, else YYYY-MM-DD
  tab: Tab;
  round: string; // "" = none, else "<game_id>:<round_num>": a deep link into the Replay
  t: string; // "" = none, else seconds from the buy-phase end
}

const DEFAULTS: Selection = { team: "79", map: "", side: "", since: "", tab: "findings", round: "", t: "" };

function read(): Selection {
  const q = new URLSearchParams(window.location.search);
  const tab = q.get("tab");
  return {
    team: q.get("team") ?? DEFAULTS.team,
    map: q.get("map") ?? DEFAULTS.map,
    side: q.get("side") ?? DEFAULTS.side,
    since: q.get("since") ?? DEFAULTS.since,
    tab: TABS.includes(tab as Tab) ? (tab as Tab) : DEFAULTS.tab,
    round: q.get("round") ?? "",
    t: q.get("t") ?? "",
  };
}

export function useSelection(): [Selection, (change: Partial<Selection>) => void] {
  const [selection, setSelection] = useState<Selection>(read);

  // Browser back/forward buttons change the URL: read it again.
  useEffect(() => {
    const onPop = () => setSelection(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const update = useCallback((change: Partial<Selection>) => {
    setSelection((prev) => {
      const next = { ...prev, ...change };
      const q = new URLSearchParams();
      for (const [key, value] of Object.entries(next)) if (value) q.set(key, value);
      window.history.pushState(null, "", `?${q.toString()}`);
      return next;
    });
  }, []);

  return [selection, update];
}

/** Link target for "open this moment in the Replay". */
export const replayAt = (key: string, t: number): Partial<Selection> => ({
  tab: "replay",
  round: key,
  t: String(Math.round(t * 10) / 10),
});
