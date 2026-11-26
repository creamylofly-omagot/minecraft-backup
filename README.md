# Minecraft server (public) — nazeultrahighendserer

Open, no-whitelist Paper server at `/home/naze/minecraft-public`.

Runs as systemd unit **minecraft-public.service** (`User=naze`, `Restart=always`,
enabled at boot). The older whitelisted server remains at `/home/naze/minecraft`,
stopped and disabled.

Stack: Paper **26.2 build 135** (Java 25), Geyser + Floodgate for Bedrock,
ViaVersion + ViaBackwards for older Java clients, playit tunnels for public
access. Heap is 2 GiB on a 1-CPU / 5.1 GiB RAM host.

## Backup repository and docs

Public, sanitized backup: <https://github.com/creamylofly-omagot/minecraft-backup>

The repo stays public so Java players can download the required resource pack
from a GitHub Release. It contains **no real secrets**; see
[`docs/SECRETS.md`](docs/SECRETS.md) before restoring it anywhere.

Local copies of the repo docs are in [`docs/`](docs/):

- [`docs/FILES.md`](docs/FILES.md) — what every file/folder does
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — start, stop, restart, verify, restore
- [`docs/SECRETS.md`](docs/SECRETS.md) — placeholders and secret restore list
- [`docs/HOST_SETUP.md`](docs/HOST_SETUP.md) — systemd, cron, playit, firewall
- [`docs/RESOURCE_PACKS.md`](docs/RESOURCE_PACKS.md) — pack sources, SHA1, update procedure
- [`docs/BACKPACKS.md`](docs/BACKPACKS.md) — Java/Bedrock backpack install, pack, usage, rollback
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — dated progress log
- [`docs/DISASTER_RECOVERY.md`](docs/DISASTER_RECOVERY.md) — restore from GitHub progress release

> Note: the public repo docs are a Nov 25 snapshot plus dated progress updates.
> sshx is retired; see **Remote admin** below for the current Tailscale setup.

## Game progress backups

After each local backup (**04:00 and 16:00 UTC**), `github_progress_backup.py`
uploads a sanitized world/config snapshot to the `progress-latest` GitHub
Release at
<https://github.com/creamylofly-omagot/minecraft-backup/releases/tag/progress-latest>.
It is the disaster-recovery copy if this folder disappears. Secrets, tokens,
identity files, plugin jars, and private Discord config are stripped, so
restoring requires putting real values back. See
[`docs/DISASTER_RECOVERY.md`](docs/DISASTER_RECOVERY.md).

## Join

### Java
- Public: **ambulance-exporters.tun.ply.gg:25565**
- Same Wi-Fi: **192.168.1.9:25565**

### Bedrock
- Public: **wap-ski.tun.ply.gg:19132**
- Uses playit **Minecraft Bedrock (NetherNet)** with Geyser NXS signaling.
  Geyser is NetherNet-only in this config, so LAN RakNet is not currently
  enabled.
- If the playit tunnel changes, copy the fresh Geyser settings from the playit
  tunnel's *Configuration help* into `plugins/Geyser-Spigot/config.yml` and
  restart the server.

Remote play uses the playit relay (Singapore). The host ISP drops a few percent
of packets on that route, so remote players may see mild rubber-banding. LAN
play is unaffected.

## Access control

- Whitelist is **OFF** and `online-mode=false` (required for Bedrock/Floodgate).
- Java players are **not authenticated by Mojang**. Anyone with the address can
  join using any name, including one of yours.
- Do **not** grant staff powers by username. An op set by name can be
  impersonated. Use console/RCON instead.
- Bedrock usernames are prefixed with `.` (Floodgate), e.g. `.Gamertag`.

## RCON / console

The real RCON password is in `server.properties` (`rcon.password`). Read it
locally; do not paste it into this repo or the public backup.

```bash
PASS="$(grep -m1 '^rcon.password=' server.properties | cut -d= -f2-)"
python3 /home/naze/rcon.py "$PASS" "tps"
python3 /home/naze/rcon.py "$PASS" "save-all flush"
python3 /home/naze/rcon.py "$PASS" "stop"
```

Useful service commands:

```bash
systemctl status minecraft-public --no-pager -l
sudo systemctl restart minecraft-public
tail -f logs/latest.log
```

`sudo` may need the user password on this host. Because the unit uses
`Restart=always`, `save-all flush` followed by `stop` is a clean restart path.

## Resource packs

- Java: one required merged ZIP, hosted on GitHub Release **curiospaper-backpacks-pack**:
  `https://github.com/creamylofly-omagot/minecraft-backup/releases/download/curiospaper-backpacks-pack/human-era-backpacks-v1.zip`
  SHA1 `7251fd2fe34a62daf1033a43204eac885ad96f28`.
  Local source: `resource-packs/Human-Era-Backpacks-v1.zip`.
  It includes the old Human-Era + glowing-ore content plus backpack models.
- Bedrock: Geyser force-sends `Human-Era-Villagers-Illagers-Bedrock.mcpack`
  (repacked as v0.0.4 with short paths) and
  `Better-Glowing-Ores-v2.4.0-RealLight.mcpack`.
- Bedrock ore glow uses `plugins/Geyser-Spigot/custom_mappings/human_era_glowing_ores.json`
  to emit **real block light**, so it works on low-end phones with Simple/Fancy
  graphics and does not require Vibrant Visuals.
- Full sources, hashes, and update steps: [`docs/RESOURCE_PACKS.md`](docs/RESOURCE_PACKS.md).

## ImageFrame (maps)

`plugins/ImageFrame/config.yml` has:

```yaml
RequireEmptyMaps: false
```

Players **do not need blank maps** to use `/iframe create <url>`; the
`default` LuckPerms group already has the ImageFrame create/get/refresh
permissions. Original config is saved as `plugins/ImageFrame/config.yml.bak`.
Apply future config edits with `/imageframe reload` via RCON.

## Backpacks (Java + Bedrock)

CuriosPaper **2.0.1** + ProbablyBackpacks **2.4** are installed. All players have
`probablybackpacks.use`; `/bp` opens the backpack, `/baubles` opens the accessory
slots. The Java resource pack above includes the item models, and Geyser copies
the Bedrock packs/mappings automatically. Full details, checksums, hotkey,
recipes, and rollback are in [`docs/BACKPACKS.md`](docs/BACKPACKS.md).

## Remote admin (Tailscale / sshx)

- **Tailscale is the current admin path.** `tailscaled.service` runs in
  userspace mode (no root needed), enabled at boot.
  - Hostname: `nazeultrahighendserer`
  - MagicDNS: `nazeultrahighendserer.taile12673.ts.net`
  - Tailscale IP: `100.90.150.113`
  - Connect with `ssh naze@nazeultrahighendserer`
- **sshx is retired.** The watchdog was stopped and its `@reboot` cron entry
  removed. `sshx_watchdog.py` is still on disk but nothing starts it. No more
  rotating/expiring links.

## Ops scripts and performance

- `check_inventory.py`: inventory reports. `analyze_player` is enabled as a
  Rust port through `fast-anything` (~4.3× per call); check with
  `fast-anything status`.
- `chest_audit_monitor.py`: runs via tmux `chest-audit` from cron, watches
  CoreProtect container events.
- `backup.sh`: 04:00 and 16:00 UTC archives to
  `/home/naze/backups/minecraft-public/` (7 archives kept).
- Tuned for the 1-core/5400 rpm HDD host: `view-distance=4`,
  `simulation-distance=3`, `entity-broadcast-range-percentage=60`,
  tightened entity ranges in `spigot.yml`, spawn limits in `bukkit.yml`, and
  page-cache warmup in `start.sh`. See [`docs/HOST_SETUP.md`](docs/HOST_SETUP.md)
  and the `opt-backup/` folder for originals.
- TPS was 20/20/20 after tuning. The remaining ceiling is hardware (1 CPU,
  HDD) and playit relay latency, not Paper version. Paper 26.3 was tested and
  rolled back because public CoreProtect v24.1 does not support it.

## Gamerules are per-dimension

Gamerules (including `keep_inventory`) are stored separately for the Overworld,
Nether and End. To set one everywhere, run it in all three dimensions:

```bash
PASS="$(grep -m1 '^rcon.password=' server.properties | cut -d= -f2-)"
python3 /home/naze/rcon.py "$PASS" "execute in minecraft:overworld run gamerule keep_inventory true"
python3 /home/naze/rcon.py "$PASS" "execute in minecraft:the_nether run gamerule keep_inventory true"
python3 /home/naze/rcon.py "$PASS" "execute in minecraft:the_end run gamerule keep_inventory true"
```

Settings live in each world's `data/minecraft/game_rules.dat`; run `save-all`
to flush immediately.
