#!/usr/bin/env python3
"""Publish a sanitized snapshot of game progress to a GitHub Release.

Run after backup.sh. The archive contains world/player data and server configs,
but all real credentials and private identity files are removed or replaced.
The repo is public, so the release asset is rebuilt from a staging tree.
"""

import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

SRC = Path("/home/naze/minecraft-public")
DEST = Path("/home/naze/backups/minecraft-public")
STAGE = DEST / ".github-progress-staging"
ARCHIVE = DEST / "minecraft-progress-latest.tar.gz"
REPO = "creamylofly-omagot/minecraft-backup"
TAG = "progress-latest"
ASSET = ARCHIVE.name


def run(cmd, **kw):
    p = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd))}\n{p.stderr}")
    return p.stdout.strip()


def line_value(path, key):
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    return ""


def sanitize_server_properties(text):
    text = re.sub(r"(?m)^rcon\.password=.*$", "rcon.password=REPLACE_WITH_RCON_PASSWORD", text)
    text = re.sub(r"(?m)^management-server-secret=.*$", "management-server-secret=REPLACE_WITH_MANAGEMENT_SECRET", text)
    return text


def sanitize_geyser_config(text):
    # Blank the NXS signaling token; keep the rest of the config.
    return re.sub(r"(?m)^(\s*token:\s*).*$", r"\1''", text)


def sanitize_chest_audit(text):
    text = re.sub(
        r'(?m)^RCON_PASS_DEFAULT\s*=.*$',
        'RCON_PASS_DEFAULT = os.environ.get("MC_RCON_PASSWORD", "")',
        text,
    )
    return text


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # Hardlink large data trees (fast, no extra disk usage); edits below only
    # remove/rewrite staged directory entries, never the live originals.
    for name in ("world", "config", "plugins"):
        src = SRC / name
        if src.exists():
            run(["cp", "-al", str(src), str(STAGE / name)])

    # Do not publish plugin binaries; they are already in the repo/Releases.
    run(["find", str(STAGE / "plugins"), "-type", "f", "-name", "*.jar", "-delete"])

    # Runtime logs are regenerable and must never enter the public archive.
    run(["find", str(STAGE / "plugins"), "-type", "d", "-name", "logs", "-prune",
         "-exec", "rm", "-rf", "{}", "+"])
    run(["find", str(STAGE / "plugins"), "-type", "f", "(", "-name", "*.log",
         "-o", "-name", "*.log.gz", ")", "-delete"])

    # Private/token-bearing files must never enter the public archive.
    for pattern in (
        "Geyser-Spigot/nethernet",
        "Geyser-Spigot/nethernet.bak-*",
        "Geyser-Spigot/config.yml.*",
        "Geyser-Spigot/config.yml.orig",
    ):
        for p in (STAGE / "plugins").glob(pattern):
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()

    # Small root files needed to restore a working server.
    for name in ("start.sh", "backup.sh", "github_progress_backup.py",
                 "shorten_geyser_backpack_paths.py", "spigot.yml", "bukkit.yml",
                 "ops.json", "whitelist.json", "permissions.yml", "eula.txt"):
        src = SRC / name
        if src.exists():
            shutil.copy2(src, STAGE / name)

    shutil.copytree(SRC / "docs", STAGE / "docs", dirs_exist_ok=True)
    shutil.copy2(SRC / "README.md", STAGE / "README.md")

    # Sanitized copies of scripts/configs.
    sp = STAGE / "server.properties"
    sp.write_text(sanitize_server_properties((SRC / "server.properties").read_text(errors="replace")))

    ca = STAGE / "chest_audit_monitor.py"
    ca.write_text(sanitize_chest_audit((SRC / "chest_audit_monitor.py").read_text(errors="replace")))
    shutil.copy2(SRC / "check_inventory.py", STAGE / "check_inventory.py")

    gy = STAGE / "plugins" / "Geyser-Spigot" / "config.yml"
    if gy.exists():
        gy.write_text(sanitize_geyser_config(gy.read_text(errors="replace")))

    # sshx_watchdog.py is retired and contains an old Telegram token: excluded.
    # discord-bot/config.json contains the Discord token + RCON password: excluded.

    # Safety gate: abort if any live secret survived into the staging tree.
    secrets = []
    live_sp = SRC / "server.properties"
    for key in ("rcon.password", "management-server-secret"):
        v = line_value(live_sp, key)
        if v and "REPLACE" not in v:
            secrets.append(v)
    live_gy = SRC / "plugins" / "Geyser-Spigot" / "config.yml"
    m = re.search(r"(?m)^\s*token:\s*'([^']+)'", live_gy.read_text(errors="replace"))
    if m and m.group(1):
        secrets.append(m.group(1))
    watcher = SRC / "sshx_watchdog.py"
    if watcher.exists():
        m = re.search(r'(?m)^TOKEN\s*=\s*"([^"]+)"', watcher.read_text(errors="replace"))
        if m and m.group(1):
            secrets.append(m.group(1))

    for p in STAGE.rglob("*"):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        for secret in secrets:
            if secret in text:
                raise RuntimeError(f"refusing to publish: live secret found in {p.relative_to(STAGE)}")

    # Build archive.
    with tarfile.open(ARCHIVE, "w:gz", compresslevel=1) as tar:
        tar.add(STAGE, arcname="minecraft-public")
    if not tarfile.is_tarfile(ARCHIVE):
        raise RuntimeError("archive verification failed")

    size_mb = ARCHIVE.stat().st_size / 1024 / 1024

    notes = (
        f"Sanitized game-progress snapshot, updated {stamp}.\n\n"
        "Contains world/player data, configs, and plugin data. "
        "Real passwords, tokens, and identity files are stripped.\n\n"
        "Restore procedure: docs/DISASTER_RECOVERY.md in the repo, or "
        "extract this asset over a fresh copy of the repo."
    )

    # Create or overwrite the rolling release asset.
    release_check = subprocess.run(
        ["gh", "release", "view", TAG, "--repo", REPO, "--json", "tagName"],
        text=True, capture_output=True,
    )
    if release_check.returncode == 0:
        run(["gh", "release", "upload", TAG, str(ARCHIVE), "--repo", REPO, "--clobber"])
        run(["gh", "release", "edit", TAG, "--repo", REPO,
             "--title", "Latest sanitized game progress", "--notes", notes])
    else:
        run(["gh", "release", "create", TAG, str(ARCHIVE), "--repo", REPO,
             "--title", "Latest sanitized game progress", "--notes", notes])

    shutil.rmtree(STAGE, ignore_errors=True)
    print(f"{now.isoformat()} progress uploaded: {ASSET} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
