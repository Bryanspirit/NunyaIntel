"""``nunyaintel doctor``: check everything needed to run NunyaIntel, and say how to fix gaps.

Each check returns OK, WARN (works, but something is missing or slow) or FAIL (something
won't work), plus a one-line fix. Output is plain ASCII so it prints correctly in any
console, including Windows.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

OK, WARN, FAIL = "ok", "warn", "FAIL"
MARK = {OK: "[ok]  ", WARN: "[warn]", FAIL: "[FAIL]"}
MIN_PYTHON = (3, 14)
MIN_NODE = (22, 12)
DEFAULT_PORT = 4811


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def check_python() -> Check:
    version = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info[:2] < MIN_PYTHON:
        return Check("Python", FAIL, f"{version} (need 3.14+ for compression.zstd)",
                     "Install Python 3.14+ and recreate .venv")  # fmt: skip
    return Check("Python", OK, f"{version} at {sys.executable}")


def check_packages() -> Check:
    missing = [m for m in ("fastapi", "uvicorn") if importlib.util.find_spec(m) is None]
    if missing:
        return Check("Python packages", FAIL, f"missing: {', '.join(missing)}",
                     'pip install -e ".[dev]"')  # fmt: skip
    return Check("Python packages", OK, "fastapi, uvicorn installed")


DATA_REPO_URL = "https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git"
# A sparse checkout must include meta/ (teams, players, maps). The data repo's own README
# example lists only val/ and val-ability-supplements/, which would leave it out.
SPARSE_FIX = "cd <data repo>; git sparse-checkout set val val-ability-supplements meta"


def _series_count(root) -> int:
    with open(root / "val" / "series.csv", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def check_data_repo() -> Check:
    from nunyaintel.config import stl_data_dir

    root = stl_data_dir()
    if not (root / "val" / "series.csv").exists():
        return Check(
            "GRID data repo", FAIL, f"not found at {root}",
            f"git clone {DATA_REPO_URL} next to this project, or set STL_DATA_DIR",
        )  # fmt: skip
    missing = [
        part
        for part, path in (
            ("meta/", root / "meta" / "games.csv"),
            ("val-ability-supplements/", root / "val-ability-supplements"),
        )
        if not path.exists()
    ]
    if missing:
        return Check("GRID data repo", FAIL,
                     f"{root} is missing {', '.join(missing)} (partial sparse checkout?)",
                     SPARSE_FIX)  # fmt: skip
    return Check("GRID data repo", OK, f"{root} ({_series_count(root)} VALORANT series)")


def check_extract() -> Check:
    from nunyaintel.data.extract import DEFAULT_DB, SCHEMA_VERSION

    if not DEFAULT_DB.exists():
        return Check("Local extract", FAIL, f"{DEFAULT_DB} not built",
                     "nunyaintel build-cache   (~7 min, ~1 GB)")  # fmt: skip
    try:
        con = sqlite3.connect(f"file:{DEFAULT_DB.as_posix()}?mode=ro", uri=True)
        info = dict(con.execute("SELECT key, value FROM build_info").fetchall())
        con.close()
    except sqlite3.Error as exc:
        return Check("Local extract", FAIL, f"unreadable ({exc})", "nunyaintel build-cache")
    version = int(info.get("schema_version", 0))
    if version != SCHEMA_VERSION:
        return Check("Local extract", FAIL,
                     f"schema v{version}, code expects v{SCHEMA_VERSION}",
                     "nunyaintel build-cache   (rebuild for the new schema)")  # fmt: skip
    size_mb = DEFAULT_DB.stat().st_size / 1e6
    failed = info.get("series_failed") or ""
    detail = (
        f"schema v{version}, {info.get('series_parsed')} series, {size_mb:.0f} MB, "
        f"built {info.get('built_at', '?')}"
    )
    if failed:
        return Check("Local extract", WARN, f"{detail}; failed: {failed}", "nunyaintel build-cache")
    try:
        from nunyaintel.config import stl_data_dir

        available = _series_count(stl_data_dir())
    except OSError:
        available = None
    parsed = int(info.get("series_parsed") or 0)
    if available and parsed < available:
        return Check("Local extract", WARN,
                     f"{detail}: partial ({parsed} of {available} series), results will be thin",
                     "nunyaintel build-cache   (all series)")  # fmt: skip
    return Check("Local extract", OK, detail)


def check_maps() -> Check:
    from nunyaintel.maps import DEFAULT_PATH

    if DEFAULT_PATH.exists():
        names = [m["displayName"] for m in json.loads(DEFAULT_PATH.read_text("utf-8"))["data"]]
        return Check("Map callouts", OK, f"{DEFAULT_PATH.name} ({len(names)} maps)")
    return Check("Map callouts", WARN, "not downloaded yet",
                 "downloads automatically on first use (needs internet once)")  # fmt: skip


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.strip().lstrip("v").split(".")[:2])


def check_node() -> Check:
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        return Check("Node.js + npm", FAIL, "not found (only needed to build the web app)",
                     "Install Node.js 22.12+ from nodejs.org")  # fmt: skip
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    if _version_tuple(version) < MIN_NODE:
        return Check("Node.js + npm", FAIL, f"node {version} (need 22.12+)",
                     "Install Node.js 22.12+")  # fmt: skip
    return Check("Node.js + npm", OK, f"node {version}")


def check_web_build() -> Check:
    from nunyaintel.config import WEB_DIST

    if (WEB_DIST / "index.html").exists():
        return Check("Web app build", OK, str(WEB_DIST))
    return Check("Web app build", WARN, "not built (the API still works on its own)",
                 "nunyaintel serve --build")  # fmt: skip


def check_port(port: int = DEFAULT_PORT) -> Check:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex(("127.0.0.1", port)) == 0
    if not in_use:
        return Check(f"Port {port}", OK, "free")
    try:  # is it us?
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meta", timeout=2) as r:
            version = json.load(r).get("version")
        return Check(f"Port {port}", OK, f"NunyaIntel {version} is already running here")
    except Exception:
        return Check(f"Port {port}", WARN, "in use by another program",
                     f"nunyaintel serve --port {port + 10}")  # fmt: skip


CHECKS: list[Callable[[], Check]] = [
    check_python,
    check_packages,
    check_data_repo,
    check_extract,
    check_maps,
    check_node,
    check_web_build,
    check_port,
]


def run(checks: list[Callable[[], Check]] = CHECKS) -> tuple[list[Check], int]:
    """Run all checks (a crashing check counts as FAIL). Returns (results, exit code)."""
    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as exc:  # a broken check must not hide the others
            results.append(Check(fn.__name__.removeprefix("check_"), FAIL, f"error: {exc}"))
    return results, 1 if any(r.status == FAIL for r in results) else 0


def report(results: list[Check]) -> str:
    lines = ["NunyaIntel doctor", ""]
    for r in results:
        lines.append(f"{MARK[r.status]} {r.name:<16} {r.detail}")
        if r.fix and r.status != OK:
            lines.append(f"{'':7}{'':<16} fix: {r.fix}")
    fails = sum(r.status == FAIL for r in results)
    warns = sum(r.status == WARN for r in results)
    lines.append("")
    if fails:
        lines.append(f"{fails} problem(s) to fix before running. See 'fix:' lines above.")
    else:
        extra = f" ({warns} warning(s))" if warns else ""
        lines.append(f"Ready{extra}: nunyaintel serve --build --open")
    return "\n".join(lines)


def main() -> int:
    results, code = run()
    print(report(results))
    return code


if __name__ == "__main__":
    sys.exit(main())
