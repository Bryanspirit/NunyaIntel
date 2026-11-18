// Small display helpers shared by all pages.

export const pct = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined ? "–" : `${(x * 100).toFixed(digits)}%`;

export const secs = (x: number | null | undefined): string =>
  x === null || x === undefined ? "–" : `${x >= 0 ? "+" : ""}${x.toFixed(0)}s`;

export const title = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);
