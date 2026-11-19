// <Minimap>: the map's minimap image with an SVG drawing layer on top.
//
// Coordinates: the API sends every point as (u, v) in 0..1 on the minimap image (u = right,
// v = down; converted from game coordinates on the server). The SVG uses viewBox 0..1000, so a
// point is drawn at (u * 1000, v * 1000) and everything scales with the image at any size.
// Verified: Lotus's A/B/C "Site" callouts land on the three site patches of the image.
//
// Usage:
//   <Minimap map={mapInfo} legend={[...]}>
//     <MapDot u={p.u} v={p.v} color="red" title="A plant, round won" />
//     <MapArrow u={a.u} v={a.v} u2={a.target_u} v2={a.target_v} color="cyan" />
//   </Minimap>

import { useState, type CSSProperties, type ReactNode } from "react";
import type { MapInfo } from "../api";

const SIZE = 1000; // viewBox size; u, v in 0..1 are scaled by this

export interface LegendItem {
  color: string;
  label: string;
  hollow?: boolean;
}

interface MinimapProps {
  map: MapInfo;
  children?: ReactNode;
  legend?: LegendItem[];
  /** start with callout labels visible */
  showCallouts?: boolean;
}

export function Minimap({ map, children, legend = [], showCallouts = false }: MinimapProps) {
  const [labels, setLabels] = useState(showCallouts);

  return (
    <figure className="minimap">
      <div className="minimap-frame">
        {map.minimap_url ? (
          <img src={map.minimap_url} alt={`${map.name} minimap`} draggable={false} />
        ) : (
          <div className="minimap-missing">No minimap image for {map.name}</div>
        )}
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${map.name} overlay`}>
          {children}
          {labels &&
            map.callouts.map((c) => (
              <text key={c.name} className="callout" x={c.u * SIZE} y={c.v * SIZE} textAnchor="middle">
                {c.name}
              </text>
            ))}
        </svg>
      </div>
      <figcaption>
        {legend.map((item) => (
          <span key={item.label} className="legend-item">
            <svg width="12" height="12" viewBox="0 0 12 12">
              <circle cx="6" cy="6" r="4.5" fill={item.hollow ? "none" : item.color} stroke={item.color}
                strokeWidth="1.5" />
            </svg>
            {item.label}
          </span>
        ))}
        <label className="legend-toggle">
          <input type="checkbox" checked={labels} onChange={(e) => setLabels(e.target.checked)} />
          callouts
        </label>
      </figcaption>
    </figure>
  );
}

interface DotProps {
  u: number;
  v: number;
  color: string;
  /** hollow = outline only (e.g. round lost) */
  hollow?: boolean;
  /** radius in viewBox units (1000 = full width) */
  r?: number;
  /** tooltip shown on hover */
  title?: string;
  opacity?: number;
  /** entrance delay in ms (staggered animation) */
  delay?: number;
  /** makes the mark clickable (e.g. "open this round in the Replay") */
  onClick?: () => void;
}

export function MapDot({ u, v, color, hollow = false, r = 7, title, opacity = 0.85, delay = 0, onClick }: DotProps) {
  // className "pop" + --delay: dots pop in one after another (broadcast.css; off for reduced motion)
  return (
    <circle cx={u * SIZE} cy={v * SIZE} r={r} fill={hollow ? "none" : color} stroke={color}
      strokeWidth={hollow ? 2.5 : 1} opacity={opacity} className={onClick ? "pop clickable" : "pop"} onClick={onClick}
      style={{ "--delay": `${delay}ms` } as CSSProperties}>
      {title && <title>{title}</title>}
    </circle>
  );
}

interface ArrowProps {
  u: number;
  v: number;
  u2: number;
  v2: number;
  color: string;
  width?: number;
  title?: string;
  opacity?: number;
  delay?: number;
  onClick?: () => void;
}

/** A line from (u, v) to (u2, v2) with an arrowhead at the end and a dot at the start. */
export function MapArrow({ u, v, u2, v2, color, width = 3, title, opacity = 0.9, delay = 0, onClick }: ArrowProps) {
  const [x1, y1, x2, y2] = [u * SIZE, v * SIZE, u2 * SIZE, v2 * SIZE];
  // Arrowhead = a triangle at the tip. (dx, dy) is the unit vector along the line; (-dy, dx)
  // is perpendicular to it, which gives the two back corners of the triangle.
  const length = Math.hypot(x2 - x1, y2 - y1) || 1;
  const [dx, dy] = [(x2 - x1) / length, (y2 - y1) / length];
  const head = width * 4;
  const back = [x2 - dx * head, y2 - dy * head];
  const corners = [
    [x2, y2],
    [back[0] - dy * head * 0.5, back[1] + dx * head * 0.5],
    [back[0] + dy * head * 0.5, back[1] - dx * head * 0.5],
  ];
  return (
    <g opacity={opacity} onClick={onClick} className={onClick ? "clickable" : undefined}>
      {title && <title>{title}</title>}
      {/* pathLength=1 lets CSS "draw" the line from 0 to 1 regardless of its real length */}
      <line x1={x1} y1={y1} x2={back[0]} y2={back[1]} stroke={color} strokeWidth={width} strokeLinecap="round"
        pathLength={1} className="draw" style={{ "--delay": `${delay}ms` } as CSSProperties} />
      <polygon points={corners.map((c) => c.join(",")).join(" ")} fill={color} className="pop"
        style={{ "--delay": `${delay + 500}ms` } as CSSProperties} />
      <circle cx={x1} cy={y1} r={width * 2} fill={color} className="pop"
        style={{ "--delay": `${delay}ms` } as CSSProperties} />
    </g>
  );
}
