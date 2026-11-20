// Run the browser tests against the made-up demo data (no licensed data), on port 4812.
// The demo extract lives in data/demo-cache, so your real data/cache is never touched.
//   1. python -m nunyaintel make-demo   (with NUNYAINTEL_CACHE=data/demo-cache)   -- done here
//   2. start the app on 4812 with that cache, run Playwright, stop the app
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const python = process.env.E2E_PYTHON
  ?? path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const env = {
  ...process.env,
  NUNYAINTEL_CACHE: path.join(root, "data", "demo-cache"),
  E2E_TEAM: "T1", E2E_MAP: "demomap", E2E_PLAYER: "T1P3",
  E2E_URL: process.env.E2E_URL ?? "http://127.0.0.1:4812",
  E2E_SERVE: "1", E2E_PYTHON: python,
};
const demo = spawnSync(python, ["-m", "nunyaintel", "make-demo"], { stdio: "inherit", env, cwd: root });
if (demo.status !== 0) process.exit(demo.status ?? 1);
const args = process.argv.slice(2).map((a) => (/\s/.test(a) ? `"${a}"` : a)); // keep "-g some words" together
const run = spawnSync("npx", ["playwright", "test", ...args], { stdio: "inherit", env, shell: true });
process.exit(run.status ?? 1);
