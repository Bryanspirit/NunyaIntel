"""Pre-commit guard: refuse to commit licensed hackathon data (see the data repo's LICENSE.md)."""

import re
import subprocess
import sys

BLOCKED = re.compile(
    r"\.(zst|jsonl|parquet|sqlite|duckdb)$|stl-hackathon-2026-grid-starter|(^|/)meta/.*\.csv$|"
    r"(^|/)series\.csv$",
    re.IGNORECASE,
)

staged = subprocess.run(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    capture_output=True, text=True, check=True,
).stdout.splitlines()
bad = [p for p in staged if BLOCKED.search(p)]
if bad:
    print("Blocked: these staged files look like licensed hackathon data:", *bad, sep="\n  ")
    print("Unstage them (git restore --staged <file>). The data must never be committed.")
    sys.exit(1)
