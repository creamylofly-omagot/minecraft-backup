# File map

This is the meaning of the important files in this repo.

## Server core

| Path | Purpose |
|---|---|
| `paper.jar` | Paper 26.2 server binary. `start.sh` runs this. |
| `start.sh` | Warms region-file page cache, then launches Paper with G1GC flags and `--nogui`. |
| `server.properties` | Main Paper network/game settings: ports, RCON, resource pack, view/sim distances. Sanitized here. |
| `bukkit.yml` | Spawn limits and monster spawn rate tuning. |
| `spigot.yml` | Entity activation/tracking ranges, despawn rates, merge radius, TNT cap tuning. |
| `commands.yml` | Command alias/config file. |
| `config/paper-world-defaults.yml` | Paper world defaults: redstone implementation, pathfinding updates, mob spawner tick. |
| `config/paper-global.yml` | Paper global settings: chunk send/load rates, IO threads, proxy and misc settings. |
| `eula.txt` | Minecraft EULA acceptance flag. |
| `ops.json` | Operator list. Live server is open; ops are managed carefully. |
| `whitelist.json` | Whitelist file. Whitelist is OFF in `server.properties`. |
| `banned-ips.json`, `banned-players.json` | Ban lists. |
| `usercache.json` | UUID/name cache. |
| `permissions.yml` | Legacy permissions file. Mostly unused; LuckPerms is active. |

## World data

| Path | Purpose |
|---|---|
| `world/` | Overworld. Contains player data, region files, game rules, advancements, etc. |
| `world_nether/`, `world_the_end/` | Present on the live server if generated; included when present. |
| `world/players/` | Player inventories, ender chests, locations, game rule state. |

## Plugins

Plugins are under `plugins/`. The JARs are included so this can be restored as a
working server, not just a config backup.

Important ones:

| Plugin | Purpose |
|---|---|
| `Geyser-Spigot` + `floodgate-spigot.jar` | Bedrock clients join the Java server; Floodgate gives Bedrock UUIDs/names. |
| `ViaVersion`, `ViaBackwards` | Older Java client support. |
| `CoreProtect` | Block/container/inventory audit database used by the audit scripts. |
| `LuckPerms` | Permissions/groups. ImageFrame permissions are granted through this, not OP. |
| `ImageFrame` | Image display frames/maps. |
| `VehicleSpeed` | Boat speed command/config. Current boat cap is `2.5`. |
| `SurvivalFarming` | Farming QoL plugin. |
| `Chunky` | Pre-generates chunks. Overworld was pre-generated around spawn. |
| `spark`, `LagFixer`, `SimpleHomeTpa`, `GSit`, `SkinsRestorer`, etc. | QoL/performance/support plugins. |
| `plugins/SimpleHomeTpa/config.yml` | `/sethome` limit; currently `max-homes: 15`. |
| `plugins/Geyser-Spigot/packs/` | Bedrock `.mcpack` files sent by Geyser. |

Excluded from the public copy: real Geyser NXS token backups, Geyser
`identity.pem`, and Geyser cache. See `docs/SECRETS.md`.

## Resource packs

| Path | Purpose |
|---|---|
| `resource-packs/Human-Era-Backpacks-v1.zip` | Current Java pack: Human Era + glowing ores + backpack/curios item models. |
| `resource-packs/Human-Era-Vanilla-Glowing-Ores.zip` | Previous Java pack, kept for rollback; no backpack models. |
| `plugins/Geyser-Spigot/packs/Human-Era-Villagers-Illagers-Bedrock.mcpack` | Bedrock Human Era pack. |
| `plugins/Geyser-Spigot/packs/Better-Glowing-Ores-v2.4.0-RealLight.mcpack` | Bedrock glowing ore textures. The dark glow comes from the Geyser custom block mapping below. |
| `plugins/Geyser-Spigot/custom_mappings/human_era_glowing_ores.json` | Registers vanilla ore block states as Bedrock custom blocks with real `light_emission` so they glow on Simple/Fancy. |

## Ops scripts

| Path | Purpose |
|---|---|
| `check_inventory.py` | Reads player/container NBT and reports inventories to Telegram. |
| `chest_audit_monitor.py` | Watches CoreProtect for chest/container opens and item take/put events. |
| `sshx_watchdog.py` | Retired/unused. Formerly kept an sshx session up and sent rotating links to Telegram; replaced by Tailscale. |
| `backup.sh` | Local archive script, run at 04:00 and 16:00 UTC. |
| `github_progress_backup.py` | Uploads a sanitized game-progress snapshot to the `progress-latest` GitHub Release after each backup. |
| `shorten_geyser_backpack_paths.py` | Patches ProbablyBackpacks Geyser attachable paths to stay under 80 characters for Bedrock. |
| `tools/rcon.py` | Small RCON client used by commands and scripts. |
| `tools/shorten_he_pack.py` | Rebuilds the Human Era Bedrock mcpack with shorter internal paths and bumped pack version. |
| `discord-bot/` | Discord bot code. Currently stopped. `config.json` excluded; `config.example.json` is sanitized. |

## Host files

| Path | Purpose |
|---|---|
| `host/minecraft-public.service` | systemd unit that starts `start.sh`, `Restart=always`. |
| `host/minecraft-perf.service` | systemd unit that runs host tuning at boot. |
| `host/minecraft-perf.sh` | CPU governor, sysctl, disk scheduler, RCON/Java firewall rules. |
| `host/playit.service` | playit agent service. |
| `host/crontab-naze.txt` | 04:00/16:00 UTC backup + progress upload, and chest audit autostart (sshx watchdog removed). |
| `host/playit.toml.example` | Example playit secret file. Real file is `/etc/playit/playit.toml` and is not backed up here. |

## Excluded regenerable/temporary paths

These are intentionally not in the public repo:

- `.fast/`, `cache/`, `versions/`, `libraries/` — regenerated by launchers/Paper
- `logs/` — runtime logs
- `__pycache__/`, `*.pyc`
- `discord-bot/.venv/`
- real secrets and token/identity files
