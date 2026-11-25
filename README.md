# Minecraft Public Server Backup

This repository is a **sanitized backup** of the live public Minecraft server at
`/home/naze/minecraft-public`, plus the host files that make it start and stay
online. It is public because the Java resource pack is downloaded directly from
a GitHub Release asset, so Java players do not need up.sb, Dropbox, or a local
web server.

**No real secrets are stored here.** See [`docs/SECRETS.md`](docs/SECRETS.md)
for every placeholder and how to restore the real values from the live machine.

## What runs

- Paper **26.2**, Java **25**, 2 GiB heap, 1 CPU / 5.1 GiB RAM
- Java + Bedrock via Geyser/Floodgate
- ViaVersion + ViaBackwards for older Java clients
- Bedrock networking via playit **Minecraft Bedrock (NetherNet)** + Geyser NXS
- Runs as systemd service `minecraft-public.service`
- Nightly local backup at 04:00 via `backup.sh`
- Chest/container audit monitor via tmux + cron
- sshx watchdog via cron
- Discord bot code is kept, but the bot is currently stopped by user request

## Join

### Java
- Public: `ambulance-exporters.tun.ply.gg:25565`
- Same Wi-Fi: `192.168.1.9:25565`

### Bedrock
- Public: `wap-ski.tun.ply.gg:19132`
- Same Wi-Fi: Geyser is NetherNet-only in this config, so use the public tunnel.

The server is open/no-whitelist and `online-mode=false` because Bedrock/Floodgate
requires it. Anyone with the address can join. Manage staff powers from
console/RCON, not by username, because Java names are not authenticated.

## Resource packs

- Java: required merged ZIP hosted on GitHub Release:
  `https://github.com/creamylofly-omagot/minecraft-backup/releases/download/v1.0.4/Human-Era-Vanilla-Glowing-Ores.zip`
  SHA1: `216575f6c190838ec7adc1003fdfa7f0df0b26e6`
- Bedrock: two forced `.mcpack` files in `plugins/Geyser-Spigot/packs/`:
  `Human-Era-Villagers-Illagers-Bedrock.mcpack` (repacked as v0.0.4 with short
  internal paths and fixed texture references) and
  `Better-Glowing-Ores-v2.3.5.mcpack` (classic-glow subpack works on Simple/Fancy)
- Full details: [`docs/RESOURCE_PACKS.md`](docs/RESOURCE_PACKS.md)

## Documentation

- [`docs/FILES.md`](docs/FILES.md) — what every file/folder does
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — start, stop, restart, verify, restore, backup
- [`docs/SECRETS.md`](docs/SECRETS.md) — placeholders and secret restore list
- [`docs/HOST_SETUP.md`](docs/HOST_SETUP.md) — systemd, cron, playit, firewall/perf scripts
- [`docs/RESOURCE_PACKS.md`](docs/RESOURCE_PACKS.md) — pack sources, SHA1, update procedure

## Performance guardrails

Do **not** lower these values further on this box:

- `view-distance=4`
- `simulation-distance=3`
- `entity-broadcast-range-percentage=60`

The server runs on one CPU core and a 5400 rpm HDD. `start.sh` warms the page
cache before launching Paper. Host tuning is in `host/minecraft-perf.sh`.

## Nightly backup

`backup.sh` saves `world`, `config`, `plugins`, `server.properties`, `spigot.yml`,
`bukkit.yml`, `ops.json`, and `whitelist.json` to
`/home/naze/backups/minecraft-public/` and keeps 7 archives.
