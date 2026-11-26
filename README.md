# Minecraft Public Server Backup

This repository is a **sanitized backup** of the live public Minecraft server at
`/home/naze/minecraft-public`, plus the host files that make it start and stay
online. It is public because the Java resource pack is downloaded directly from
a GitHub Release asset, so Java players do not need up.sb, Dropbox, or a local
web server.

**No real secrets are stored here.** See [`docs/SECRETS.md`](docs/SECRETS.md)
for every placeholder and how to restore the real values from the live machine.

> Docs are a sanitized snapshot plus dated progress updates. The old sshx
> watchdog is retired; admin SSH now uses Tailscale.

## Game progress backups

After each local backup (**04:00 and 16:00 UTC**), a sanitized world/config
snapshot is uploaded to the `progress-latest` GitHub Release. It is the
disaster-recovery copy if the server folder is lost. See
[`docs/DISASTER_RECOVERY.md`](docs/DISASTER_RECOVERY.md). Secrets are stripped,
so restoring it requires putting the real values back from private notes.

## What runs

- Paper **26.2**, Java **25**, 2 GiB heap, 1 CPU / 5.1 GiB RAM
- Java + Bedrock via Geyser/Floodgate
- ViaVersion + ViaBackwards for older Java clients
- Bedrock networking via playit **Minecraft Bedrock (NetherNet)** + Geyser NXS
- Runs as systemd service `minecraft-public.service`
- Local backups at 04:00 and 16:00 UTC via `backup.sh`
- Chest/container audit monitor via tmux + cron
- sshx retired; admin SSH via Tailscale (userspace service)
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
  `Better-Glowing-Ores-v2.4.0-RealLight.mcpack`
- Bedrock ore glow uses Geyser custom mappings in
  `plugins/Geyser-Spigot/custom_mappings/human_era_glowing_ores.json`. It works
  on Simple/Fancy by emitting real block light; it is not a texture-only glow.
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


## Progress update — 2026-11-26

- Added a second daily local backup at **16:00 UTC**; the existing 04:00 UTC
  backup is kept. Both write to `/home/naze/backups/minecraft-public/`.
- Admin SSH moved to **Tailscale**. The rotating sshx watchdog and its
  `@reboot` cron entry were retired; no more expiring links.
- ImageFrame now has `RequireEmptyMaps: false`, so players can create image
  maps without carrying blank maps.
- Docs refreshed for the current server state; see `docs/CHANGELOG.md`.
- The public repo remains sanitized: no real passwords, tokens, or identity
  files are included.

Date applied: **2026-11-26 (UTC)**.
