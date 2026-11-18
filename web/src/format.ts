// Small display helpers shared by all pages.

export const pct = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined ? "–" : `${(x * 100).toFixed(digits)}%`;

export const secs = (x: number | null | undefined): string =>
  x === null || x === undefined ? "–" : `${x >= 0 ? "+" : ""}${x.toFixed(0)}s`;

export const title = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** "dark-cover" -> "Dark Cover", "hunter's-fury" -> "Hunter's Fury" */
export const nice = (id: string): string =>
  id
    .split("-")
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");

export const SIDE_LABEL: Record<string, string> = { attacker: "Attack", defender: "Defense" };
export const SIDE_COLOR: Record<string, string> = { attacker: "#ff4655", defender: "#4fc3f7" };

export const WIN_TYPE_LABEL: Record<string, string> = {
  opponentEliminated: "Elimination",
  bombExploded: "Spike detonated",
  bombDefused: "Spike defused",
  timeExpired: "Time ran out",
};
