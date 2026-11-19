// Replay: a team's rounds on one map, animated on the minimap (canvas), with a scrubbable timeline.
//
// We only know positions at events (casts, shots, deaths), so the replay shows events, not moving
// players. Two views:
//   Live      events flash in and fade over a few seconds (kills draw a shooter -> victim tracer)
//   Build-up  everything stays: the time-lapse paints the team's habits onto the map
//
// Why <canvas> and not SVG: up to ~7,000 marks redrawn 60 times a second. SVG would create a DOM
// element per mark; a canvas just paints pixels, so redrawing is cheap.

import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiUrl, type MapInfo, type Replay, type ReplayEvent, type ReplayKind } from "../api";
import { PageHero, Panel } from "../components/broadcast";
import { Empty } from "../components/ui";
import { SIDE_LABEL, title, WIN_TYPE_LABEL } from "../format";
import { useReducedMotion } from "../components/motion";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

// The 3D stage pulls in Three.js (~600 KB): load it only when someone opens the 3D view.
const Replay3D = lazy(() => import("../components/Replay3D"));

const COLORS: Record<ReplayKind, string> = {
  kill: "#3ddc97", // this team got a kill
  death: "#ff4655", // this team lost a player
  util: "#f5c56b", // this team cast an ability
  plant: "#ffffff",
  defuse: "#4fc3f7",
};
const LABELS: Record<ReplayKind, string> = {
  kill: "Kills",
  death: "Deaths",
  util: "Utility",
  plant: "Plants",
  defuse: "Defuses",
};
const KINDS = Object.keys(COLORS) as ReplayKind[];
const FADE_S = 6; // live view: how long an event stays visible
const SPEEDS = [1, 2, 4, 8];

const fmtTime = (t: number) => {
  const s = Math.abs(Math.round(t));
  return `${t < 0 ? "−" : ""}${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export function ReplayPage({ selection, teamName }: { selection: Selection; teamName: string }) {
  if (!selection.map) return <Empty>Pick a map to replay how {teamName} plays it.</Empty>;
  return <ReplayForMap key={`${selection.team}|${selection.map}|${selection.side}`} selection={selection} teamName={teamName} />;
}

function ReplayForMap({ selection, teamName }: { selection: Selection; teamName: string }) {
  const data = useApi<Replay>(apiUrl("/replay", { team: selection.team, map: selection.map, side: selection.side, since: selection.since }));
  const mapInfo = useApi<MapInfo>(apiUrl(`/maps/${selection.map}`));
  if (data.error || mapInfo.error) return <p className="error">{data.error ?? mapInfo.error}</p>;
  if (!data.data || !mapInfo.data) return <p className="muted">Loading every event of every round…</p>;
  if (data.data.rounds.length === 0) return <Empty>No rounds for {teamName} on {title(selection.map)} with these filters.</Empty>;
  return <Player replay={data.data} map={mapInfo.data} teamName={teamName} selection={selection} />;
}

function Player({ replay, map, teamName, selection }: { replay: Replay; map: MapInfo; teamName: string; selection: Selection }) {
  const reduced = useReducedMotion();
  const [t, setT] = useState(-5);
  const [playing, setPlaying] = useState(false); // never autoplay
  const [speed, setSpeed] = useState(2);
  const [mode, setMode] = useState<"live" | "buildup">("live");
  const [round, setRound] = useState<number | "all">("all");
  const [layers, setLayers] = useState<Record<ReplayKind, boolean>>({ kill: true, death: true, util: true, plant: true, defuse: true });
  const [hover, setHover] = useState<{ x: number; y: number; e: ReplayEvent } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [view, setView] = useState<"2d" | "3d">("2d");
  const [autoRotate, setAutoRotate] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const [zoom, setZoom] = useState<{ key: number; dir: 1 | -1 }>({ key: 0, dir: 1 });
  // floor outline for the 3D walls: fetched only once the 3D view is opened
  const floor = useApi<{ grid: number; runs: [number, number, number][] }>(
    view === "3d" ? apiUrl(`/maps/${replay.map}/floor`) : null,
  );
  const tRef = useRef(t);
  tRef.current = t;

  // events for the chosen round(s) and layers, already sorted by time (server sorts)
  const events = useMemo(
    () => replay.events.filter((e) => (round === "all" || e[0] === round) && layers[e[2]]),
    [replay.events, round, layers],
  );
  const roundInfo = round === "all" ? null : replay.rounds[round];
  const tEnd = round === "all" ? replay.t_max : Math.min(replay.t_max, Math.max(...events.map((e) => e[1]), 10) + 3);

  // ---- the animation loop: advance the clock while playing ----
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      const next = tRef.current + ((now - last) / 1000) * speed;
      last = now;
      if (next >= tEnd) {
        setT(tEnd);
        setPlaying(false);
        return;
      }
      setT(next);
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, tEnd]);

  // ---- draw the current moment onto the canvas ----
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1; // crisp on high-DPI screens
    if (canvas.width !== Math.round(rect.width * dpr)) {
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
    }
    const ctx = canvas.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = rect.width;
    ctx.clearRect(0, 0, W, rect.height);
    const many = round === "all";
    for (const e of events) {
      const [, et, kind, u, v, us, vs] = e;
      if (et > t) break; // sorted by time: nothing later is visible yet
      const age = t - et;
      let alpha: number;
      if (mode === "buildup") alpha = many ? 0.35 : 0.85;
      else if (kind === "plant" || kind === "defuse") alpha = age < 40 ? 1 : 0; // plants stay a while
      else alpha = Math.max(0, 1 - age / FADE_S);
      if (alpha <= 0) continue;
      const x = u * W, y = v * W;
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = ctx.fillStyle = COLORS[kind];
      if ((kind === "kill" || kind === "death") && us !== null && vs !== null && (mode === "live" || !many)) {
        // tracer from shooter to victim, drawn out over the first 0.35 s
        const grow = Math.min(1, age / 0.35);
        const sx = us * W, sy = vs * W;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + (x - sx) * grow, sy + (y - sy) * grow);
        ctx.stroke();
      }
      if (kind === "kill" || kind === "death") {
        const r = many && mode === "buildup" ? 3 : 6;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r);
        ctx.moveTo(x + r, y - r); ctx.lineTo(x - r, y + r);
        ctx.stroke();
      } else if (kind === "util") {
        ctx.beginPath();
        ctx.arc(x, y, many && mode === "buildup" ? 2 : 4, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // plant / defuse: a diamond with a pulse ring in the live view
        const s = 8;
        ctx.beginPath();
        ctx.moveTo(x, y - s); ctx.lineTo(x + s, y); ctx.lineTo(x, y + s); ctx.lineTo(x - s, y);
        ctx.closePath();
        ctx.fill();
        if (mode === "live" && !reduced && age < 3) {
          ctx.globalAlpha = alpha * (1 - age / 3);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(x, y, s + age * 14, 0, Math.PI * 2);
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
  }, [events, t, mode, round, reduced]);

  useEffect(draw, [draw]);
  useEffect(() => {
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, [draw]);

  // ---- keyboard: Space = play/pause, arrows = step 1 s ----
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.target as HTMLElement)?.tagName === "INPUT" || (ev.target as HTMLElement)?.tagName === "SELECT") return;
      if (ev.code === "Space") { ev.preventDefault(); setPlaying((p) => !p); }
      if (ev.code === "ArrowRight") setT((x) => Math.min(tEnd, x + 1));
      if (ev.code === "ArrowLeft") setT((x) => Math.max(replay.t_min, x - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tEnd, replay.t_min]);

  // ---- hover: nearest visible event within 12 px ----
  const onMove = (ev: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = ev.currentTarget.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    let best: ReplayEvent | null = null, bestD = 12 * 12;
    for (const e of events) {
      if (e[1] > t) break;
      if (mode === "live" && e[2] !== "plant" && e[2] !== "defuse" && t - e[1] > FADE_S) continue;
      const dx = e[3] * rect.width - mx, dy = e[4] * rect.width - my, d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = e; }
    }
    setHover(best ? { x: mx, y: my, e: best } : null);
  };

  // counts so far (the scoreboard under the map)
  const counts = useMemo(() => {
    const c: Record<ReplayKind, number> = { kill: 0, death: 0, util: 0, plant: 0, defuse: 0 };
    for (const e of events) { if (e[1] > t) break; c[e[2]]++; }
    return c;
  }, [events, t]);

  const start = () => { if (t >= tEnd - 0.1) setT(round === "all" ? -5 : replay.t_min); setPlaying(true); };

  return (
    <section>
      <PageHero
        kicker={`Replay · ${title(replay.map)}${selection.side ? ` · ${SIDE_LABEL[selection.side]}` : ""}`}
        title={teamName}
        stats={[
          { label: "Rounds", value: replay.rounds.length },
          { label: "Events", value: replay.events.length },
          { label: "Kills", value: replay.events.filter((e) => e[2] === "kill").length, tone: "good" },
          { label: "Deaths", value: replay.events.filter((e) => e[2] === "death").length, tone: "bad" },
        ]}
      />

      <Panel title={roundInfo ? `Round ${roundInfo.round} vs ${roundInfo.opponent}` : `All ${replay.rounds.length} rounds, overlaid`} index={0}
        aside="Space = play/pause · ← → = 1 s · hover a mark for details · click the strip to jump">
        <div className="replay">
          <div className="replay-stage">
            <div className="view-bar">
              <div className="seg">
                <button className={view === "2d" ? "on" : ""} onClick={() => setView("2d")}>2D</button>
                <button className={view === "3d" ? "on" : ""} onClick={() => setView("3d")}>3D</button>
              </div>
              {view === "3d" && (
                <>
                  <button className={autoRotate ? "chip active" : "chip"} onClick={() => setAutoRotate(!autoRotate)}>
                    ⟳ Broadcast camera
                  </button>
                  <button className="chip" onClick={() => setZoom((z) => ({ key: z.key + 1, dir: 1 }))} aria-label="Zoom in">＋</button>
                  <button className="chip" onClick={() => setZoom((z) => ({ key: z.key + 1, dir: -1 }))} aria-label="Zoom out">－</button>
                  <button className="chip" onClick={() => setResetKey((k) => k + 1)}>Reset view</button>
                  <span className="muted view-hint">drag to orbit · right-drag to pan · ＋/－ to zoom</span>
                </>
              )}
            </div>
            <div className={view === "3d" ? "minimap-frame stage3d" : "minimap-frame"}>
              {view === "3d" ? (
                <Suspense fallback={<div className="minimap-missing">Loading 3D…</div>}>
                  <Replay3D mapUrl={map.minimap_url} floor={floor.data} events={events} t={t} mode={mode}
                    dense={round === "all"} autoRotate={autoRotate && !reduced} resetKey={resetKey}
                    zoomKey={zoom.key} zoomDir={zoom.dir} />
                </Suspense>
              ) : (
                <>
                  {map.minimap_url && <img src={map.minimap_url} alt={`${map.name} minimap`} draggable={false} />}
                  <canvas ref={canvasRef} className="replay-canvas" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
                </>
              )}
              <div className="replay-clock">
                {fmtTime(t)}
                <span>{t < 0 ? "buy phase" : "round time"}</span>
              </div>
              {view === "2d" && hover && (
                <div className="replay-tip" style={{ left: hover.x + 14, top: hover.y + 10 }}>
                  <b style={{ color: COLORS[hover.e[2]] }}>{LABELS[hover.e[2]].replace(/s$/, "")}</b> at {fmtTime(hover.e[1])}
                  <div>{hover.e[7]}</div>
                  {round === "all" && <div className="muted">{describe(replay, hover.e[0])}</div>}
                </div>
              )}
            </div>
            <div className="replay-score">
              {KINDS.map((k) => (
                <span key={k} style={{ color: COLORS[k] }}><b>{counts[k]}</b> {LABELS[k]}</span>
              ))}
            </div>
          </div>

          <div className="replay-controls">
            <div className="replay-buttons">
              <button className="play" onClick={() => (playing ? setPlaying(false) : start())} aria-label={playing ? "Pause" : "Play"}>
                {playing ? "❚❚" : "▶"}
              </button>
              <button onClick={() => { setPlaying(false); setT(round === "all" ? -5 : replay.t_min); }}>↺ Restart</button>
              <label>
                Speed
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
                  {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
                </select>
              </label>
            </div>

            <input className="scrubber" type="range" min={replay.t_min} max={tEnd} step={0.1} value={t}
              onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }} aria-label="Round time" />
            <DensityStrip events={events} tMin={replay.t_min} tMax={tEnd} t={t} onSeek={(x) => { setPlaying(false); setT(x); }} />

            <div className="replay-options">
              <div className="seg">
                <button className={mode === "live" ? "on" : ""} onClick={() => setMode("live")}>Live</button>
                <button className={mode === "buildup" ? "on" : ""} onClick={() => setMode("buildup")}>Build-up</button>
              </div>
              <div className="layers">
                {KINDS.map((k) => (
                  <label key={k} style={{ color: COLORS[k] }}>
                    <input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} />
                    {LABELS[k]}
                  </label>
                ))}
              </div>
              <label className="round-pick">
                Round
                <select value={round} onChange={(e) => {
                  const v = e.target.value === "all" ? "all" : Number(e.target.value);
                  setRound(v); setPlaying(false); setT(v === "all" ? -5 : replay.t_min);
                }}>
                  <option value="all">All rounds (time-lapse)</option>
                  {replay.rounds.map((r) => (
                    <option key={r.i} value={r.i}>{describe(replay, r.i)}</option>
                  ))}
                </select>
              </label>
            </div>
            {roundInfo && (
              <p className={`round-result ${roundInfo.won ? "won" : "lost"}`}>
                {roundInfo.won ? "Won" : "Lost"} · {WIN_TYPE_LABEL[roundInfo.win_type] ?? roundInfo.win_type} · {SIDE_LABEL[roundInfo.side]} · {roundInfo.own_buy}
              </p>
            )}
            <p className="note">
              Positions are known only when something happens (a cast, a shot, a death), so this replays events, not moving
              players. Time 0:00 = the end of the buy phase; negative = setup during the buy phase.
            </p>
          </div>
        </div>
      </Panel>
    </section>
  );
}

function describe(replay: Replay, i: number): string {
  const r = replay.rounds[i];
  return `${r.date} vs ${r.opponent} · R${r.round} · ${SIDE_LABEL[r.side]} · ${r.won ? "W" : "L"}`;
}

/** When the action happens: kills (up) and deaths (down) per 2 s, with the playhead. Click to jump. */
function DensityStrip({ events, tMin, tMax, t, onSeek }: { events: ReplayEvent[]; tMin: number; tMax: number; t: number; onSeek: (t: number) => void }) {
  const BIN = 2;
  const n = Math.ceil((tMax - tMin) / BIN);
  const kills = new Array(n).fill(0), deaths = new Array(n).fill(0);
  for (const e of events) {
    const b = Math.floor((e[1] - tMin) / BIN);
    if (b < 0 || b >= n) continue;
    if (e[2] === "kill") kills[b]++;
    else if (e[2] === "death") deaths[b]++;
  }
  const peak = Math.max(1, ...kills, ...deaths);
  const x = (v: number) => ((v - tMin) / (tMax - tMin)) * 600;
  return (
    <svg className="density" viewBox="0 0 600 60" preserveAspectRatio="none"
      onClick={(ev) => {
        const r = ev.currentTarget.getBoundingClientRect();
        onSeek(tMin + ((ev.clientX - r.left) / r.width) * (tMax - tMin));
      }}>
      <line x1={x(0)} x2={x(0)} y1={0} y2={60} className="density-zero" />
      {kills.map((k, i) => <rect key={`k${i}`} x={(i * 600) / n} y={30 - (k / peak) * 28} width={600 / n - 0.5} height={(k / peak) * 28} fill={COLORS.kill} />)}
      {deaths.map((d, i) => <rect key={`d${i}`} x={(i * 600) / n} y={30} width={600 / n - 0.5} height={(d / peak) * 28} fill={COLORS.death} />)}
      <line x1={x(t)} x2={x(t)} y1={0} y2={60} className="density-head" />
    </svg>
  );
}
