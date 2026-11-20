#!/bin/sh
# Copy the local extract into the container's own cache volume, then start NunyaIntel.
#
# Why: on Windows/macOS, Docker reads files in a folder mounted from the host slowly, and
# NunyaIntel scans a 1.1 GB SQLite file. A named volume lives on Docker's own (Linux) disk,
# which is fast. /seed is ./data/cache mounted read-only; a file is copied only when the
# volume doesn't have it yet or the one in /seed is newer (you rebuilt the extract).
set -e
CACHE=/app/data/cache
if [ -d /seed ]; then
  for f in nunyaintel.sqlite maps.json league_baselines.json; do
    if [ -f "/seed/$f" ] && { [ ! -f "$CACHE/$f" ] || [ "/seed/$f" -nt "$CACHE/$f" ]; }; then
      echo "Copying $f into the cache volume (first start or newer extract)..."
      cp -p "/seed/$f" "$CACHE/$f"
    fi
  done
  if [ -d /seed/minimaps ]; then
    mkdir -p "$CACHE/minimaps"
    cp -rpu /seed/minimaps/. "$CACHE/minimaps/"
  fi
fi
exec "$@"
