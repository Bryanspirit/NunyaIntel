// 3D replay stage (Three.js / WebGL). Loaded only when the 3D view is opened (code-split), so the
// ~600 KB library never slows down the rest of the app.
//
// World coordinates: the map is the unit square on the ground, x = u (right) and z = v (down the
// minimap), y = up. Every event's (u, v) from the API maps straight onto it.
//
//   ground   the minimap image as a textured plane
//   walls    raised blocks along the edges of the walkable floor (drawn from the data)
//   events   instanced meshes per kind (one draw call each, thousands of marks), faded by scale
//   tracers  kill arcs through the air, rebuilt each frame for the visible ones
//   plants   vertical light beams
//
// Heights are for readability only: kill positions in the data are 2D.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { ReplayEvent, ReplayKind } from "../api";

export interface Stage3DProps {
  mapUrl: string | null;
  floor: { grid: number; runs: [number, number, number][] } | null;
  events: ReplayEvent[]; // sorted by time
  t: number;
  mode: "live" | "buildup";
  dense: boolean; // all rounds overlaid: smaller marks, no tracers in build-up
  autoRotate: boolean;
  resetKey: number; // bump to reset the camera
  zoomKey: number; // bump to apply one zoom step
  zoomDir: 1 | -1; // 1 = in, -1 = out
}

const COLOR: Record<ReplayKind, number> = {
  kill: 0x3ddc97,
  death: 0xff4655,
  util: 0xf5c56b,
  plant: 0xffffff,
  defuse: 0x4fc3f7,
};
const FADE_S = 6;
const WALL_H = 0.03;
const KINDS: ReplayKind[] = ["kill", "death", "util", "plant", "defuse"];

function alphaFor(e: ReplayEvent, t: number, mode: "live" | "buildup", dense: boolean): number {
  const age = t - e[1];
  if (age < 0) return 0;
  if (mode === "buildup") return dense ? 0.55 : 1;
  if (e[2] === "plant" || e[2] === "defuse") return age < 40 ? 1 : 0;
  return Math.max(0, 1 - age / FADE_S);
}

export default function Replay3D(props: Stage3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const propsRef = useRef(props);
  propsRef.current = props;
  // objects that the per-frame update needs; rebuilt when the event set changes
  const sceneRef = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    meshes: Partial<Record<ReplayKind, { mesh: THREE.InstancedMesh; events: ReplayEvent[] }>>;
    beams: { mesh: THREE.InstancedMesh; events: ReplayEvent[] } | null;
    tracers: THREE.LineSegments;
    walls: THREE.InstancedMesh | null;
    ground: THREE.Mesh;
  } | null>(null);

  // ---- one-time setup: renderer, camera, controls, ground, lights, render loop ----
  useEffect(() => {
    const mount = mountRef.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0a1118, 1.6, 3.2);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 10);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; // smooth, "broadcast camera" feel
    controls.maxPolarAngle = Math.PI / 2.15; // never go under the floor
    controls.minDistance = 0.25;
    controls.maxDistance = 2.2;
    controls.autoRotateSpeed = 0.6;
    // The mouse wheel stays with the page: wheel-zoom on an embedded 3D view traps people who
    // just want to scroll past it. Zoom uses the +/- buttons (and pinch on touch screens).
    controls.enableZoom = false;

    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const sun = new THREE.DirectionalLight(0xffffff, 1.1);
    sun.position.set(-0.6, 1.4, 0.4);
    scene.add(sun);

    // ground: the minimap image on the unit square (x = u, z = v)
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshStandardMaterial({ color: 0x1b2a38, roughness: 0.95 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(0.5, 0, 0.5);
    scene.add(ground);

    const tracers = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 }),
    );
    scene.add(tracers);

    sceneRef.current = { scene, camera, controls, meshes: {}, beams: null, tracers, walls: null, ground };

    const resize = () => {
      const w = mount.clientWidth, h = mount.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();

    let frame = 0;
    const loop = () => {
      update();
      controls.autoRotate = propsRef.current.autoRotate;
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
        (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((m) => m.dispose());
      });
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, []);

  // ---- camera reset ----
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    s.camera.position.set(0.5, 0.92, 1.08); // tilted, like a broadcast establishing shot
    s.controls.target.set(0.5, 0, 0.44); // a little "up" the map, so it fills the frame
    s.controls.update();
  }, [props.resetKey]);

  // ---- zoom buttons: move the camera along its line of sight toward the target ----
  useEffect(() => {
    const s = sceneRef.current;
    if (!s || props.zoomKey === 0) return;
    const offset = s.camera.position.clone().sub(s.controls.target);
    const factor = props.zoomDir === 1 ? 0.8 : 1.25;
    const length = Math.min(s.controls.maxDistance, Math.max(s.controls.minDistance, offset.length() * factor));
    s.camera.position.copy(s.controls.target).add(offset.setLength(length));
    s.controls.update();
  }, [props.zoomKey]); // only on a button press (zoomDir changes together with zoomKey)

  // ---- ground texture ----
  useEffect(() => {
    const s = sceneRef.current;
    if (!s || !props.mapUrl) return;
    new THREE.TextureLoader().load(props.mapUrl, (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 8;
      const mat = s.ground.material as THREE.MeshStandardMaterial;
      mat.map = tex;
      mat.color.set(0xffffff);
      mat.transparent = true; // the minimap has a transparent background
      mat.needsUpdate = true;
    });
  }, [props.mapUrl]);

  // ---- walls along the edges of the walkable floor ----
  useEffect(() => {
    const s = sceneRef.current;
    if (!s || !props.floor) return;
    const { grid, runs } = props.floor;
    const floor = new Set<number>();
    for (const [row, start, len] of runs) for (let c = start; c < start + len; c++) floor.add(row * grid + c);
    const walls: [number, number][] = [];
    for (let r = 0; r < grid; r++) {
      for (let c = 0; c < grid; c++) {
        if (floor.has(r * grid + c)) continue;
        // a wall cell is an empty cell touching the floor (4-neighbourhood)
        if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dc, dr]) => floor.has((r + dr) * grid + (c + dc)))) walls.push([c, r]);
      }
    }
    if (s.walls) s.scene.remove(s.walls);
    const cell = 1 / grid;
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(cell, WALL_H, cell),
      new THREE.MeshStandardMaterial({ color: 0x3a4d60, roughness: 0.6, metalness: 0.1 }),
      walls.length,
    );
    const m = new THREE.Matrix4();
    walls.forEach(([c, r], i) => mesh.setMatrixAt(i, m.makeTranslation((c + 0.5) * cell, WALL_H / 2, (r + 0.5) * cell)));
    s.scene.add(mesh);
    s.walls = mesh;
  }, [props.floor]);

  // ---- event meshes: one instanced mesh per kind (rebuilt when the event set changes) ----
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    for (const k of KINDS) {
      const old = s.meshes[k];
      if (old) s.scene.remove(old.mesh);
    }
    if (s.beams) s.scene.remove(s.beams.mesh);
    s.meshes = {};
    for (const k of KINDS) {
      const evs = props.events.filter((e) => e[2] === k);
      if (!evs.length) continue;
      const geo = k === "kill" || k === "death" ? new THREE.OctahedronGeometry(0.006) : new THREE.SphereGeometry(0.0035, 10, 8);
      const mat = new THREE.MeshBasicMaterial({ color: COLOR[k] });
      const mesh = new THREE.InstancedMesh(geo, mat, evs.length);
      mesh.frustumCulled = false;
      s.scene.add(mesh);
      s.meshes[k] = { mesh, events: evs };
    }
    const plants = props.events.filter((e) => e[2] === "plant" || e[2] === "defuse");
    if (plants.length) {
      const beam = new THREE.InstancedMesh(
        new THREE.CylinderGeometry(0.0025, 0.0025, 1, 8),
        new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }),
        plants.length,
      );
      plants.forEach((e, i) => beam.setColorAt(i, new THREE.Color(COLOR[e[2]])));
      beam.frustumCulled = false;
      s.scene.add(beam);
      s.beams = { mesh: beam, events: plants };
    } else {
      s.beams = null;
    }
  }, [props.events]);

  // ---- per-frame update: place / scale every mark for the current moment ----
  const tmp = useRef({ m: new THREE.Matrix4(), q: new THREE.Quaternion(), p: new THREE.Vector3(), sc: new THREE.Vector3() });
  function update() {
    const s = sceneRef.current;
    if (!s) return;
    const { t, mode, dense, events } = propsRef.current;
    const { m, q, p, sc } = tmp.current;
    const shrink = dense && mode === "buildup" ? 0.6 : 1;
    for (const k of KINDS) {
      const entry = s.meshes[k];
      if (!entry) continue;
      const lift = k === "util" ? 0.022 : 0.012;
      entry.events.forEach((e, i) => {
        const a = alphaFor(e, t, mode, dense) * shrink; // fade = shrink (instances share one material)
        p.set(e[3], lift, e[4]);
        sc.setScalar(a);
        entry.mesh.setMatrixAt(i, m.compose(p, q, sc));
      });
      entry.mesh.instanceMatrix.needsUpdate = true;
    }
    if (s.beams) {
      s.beams.events.forEach((e, i) => {
        const age = t - e[1];
        const a = alphaFor(e, t, mode, dense);
        const h = a > 0 ? Math.min(1, Math.max(0, age) / 0.6) * 0.28 : 0; // the beam shoots up
        p.set(e[3], h / 2, e[4]);
        sc.set(a > 0 ? 1 : 0, Math.max(h, 0.0001), a > 0 ? 1 : 0);
        s.beams!.mesh.setMatrixAt(i, m.compose(p, q, sc));
      });
      s.beams.mesh.instanceMatrix.needsUpdate = true;
    }
    // tracers: quadratic arcs from shooter to victim, for kills visible right now
    const pos: number[] = [], col: number[] = [];
    if (!(dense && mode === "buildup")) {
      const c = new THREE.Color();
      for (const e of events) {
        if (e[1] > t) break;
        if ((e[2] !== "kill" && e[2] !== "death") || e[5] === null || e[6] === null) continue;
        const a = alphaFor(e, t, mode, dense);
        if (a <= 0.02) continue;
        const grow = Math.min(1, (t - e[1]) / 0.35);
        const [x0, z0, x1, z1] = [e[5], e[6], e[3], e[4]];
        const peak = 0.02 + Math.hypot(x1 - x0, z1 - z0) * 0.25;
        c.set(COLOR[e[2]]).multiplyScalar(a);
        const N = 10;
        let px = x0, py = 0.012, pz = z0;
        for (let j = 1; j <= N; j++) {
          const f = (j / N) * grow;
          const x = x0 + (x1 - x0) * f, z = z0 + (z1 - z0) * f, y = 0.012 + 4 * peak * f * (1 - f);
          pos.push(px, py, pz, x, y, z);
          col.push(c.r, c.g, c.b, c.r, c.g, c.b);
          px = x; py = y; pz = z;
        }
      }
    }
    const g = s.tracers.geometry;
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.computeBoundingSphere();
  }

  return <div ref={mountRef} className="replay3d" aria-label="3D replay: drag to orbit, scroll to zoom, right-drag to pan" />;
}
