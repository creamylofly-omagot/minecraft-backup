#!/usr/bin/env bash
# Nightly backup: flush world, archive world+configs+plugin data, keep 7.
set -uo pipefail
SRC=/home/naze/minecraft-public
DEST=/home/naze/backups/minecraft-public
KEEP=7
mkdir -p "$DEST"
PW=$(grep -m1 '^rcon.password=' "$SRC/server.properties" 2>/dev/null | cut -d= -f2-)
if [ -n "$PW" ]; then
  python3 /home/naze/rcon.py "$PW" "save-all flush" >/dev/null 2>&1 || true
  sleep 5
fi
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$DEST/minecraft-public-$STAMP.tar.gz"
PATHS=""
for p in world world_nether world_the_end config plugins \
         server.properties spigot.yml bukkit.yml ops.json whitelist.json; do
  [ -e "$SRC/$p" ] && PATHS="$PATHS $p"
done
tar -czf "$OUT" -C "$SRC" --exclude='plugins/*.jar' $PATHS 2>/dev/null || true
if tar -tzf "$OUT" >/dev/null 2>&1; then
  echo "$(date -Is) backup OK: $OUT $(du -h "$OUT" | cut -f1)"
else
  echo "$(date -Is) backup FAILED: $OUT" >&2
  exit 1
fi
ls -1t "$DEST"/minecraft-public-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
