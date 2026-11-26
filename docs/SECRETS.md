# Secrets and placeholders

This repository is public so GitHub Release assets can be downloaded by the
Minecraft client. Real secrets are **not** included. The live server at
`/home/naze/minecraft-public` still has the real values.

## What was sanitized

| File | Placeholder / change |
|---|---|
| `server.properties` | `rcon.password=REPLACE_WITH_RCON_PASSWORD` |
| `server.properties` | `management-server-secret=REPLACE_WITH_MANAGEMENT_SECRET` |
| `opt-backup/server.properties` | Same two placeholders |
| `chest_audit_monitor.py` | `RCON_PASS_DEFAULT = os.environ.get("MC_RCON_PASSWORD", "")` |
| `sshx_watchdog.py` | `TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")` |
| `sshx_watchdog.py` | `CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")` |
| `plugins/Geyser-Spigot/config.yml` | NXS token set to `token: ''` |
| `discord-bot/config.example.json` | `rcon_password` placeholder |
| `discord-bot/config.json` | Excluded completely; contains Discord bot token + RCON password |
| `plugins/Geyser-Spigot/config.yml.*` | Excluded backup configs; may contain old tokens |
| `plugins/Geyser-Spigot/nethernet/identity.pem` | Excluded private identity |
| `host/playit.toml.example` | Placeholder only; real `/etc/playit/playit.toml` excluded |

`sshx_watchdog.py` is retired and unused; its Telegram token/chat ID rows are
kept only to document how the old public snapshot was sanitized. Admin access
now uses Tailscale.

## Environment variables used by scripts

Create a private file on the live machine, outside this repo, for example:

```bash
sudo install -m 600 /dev/null /etc/minecraft-backup.env
```

Contents:

```env
MC_RCON_PASSWORD=<real rcon password from server.properties>
TELEGRAM_BOT_TOKEN=<telegram bot token>
TELEGRAM_CHAT_ID=<telegram chat id>
DISCORD_BOT_TOKEN=<only if re-enabling the Discord bot>
```

Then load it before running the scripts:

```bash
set -a
. /etc/minecraft-backup.env
set +a
```

## Restore rule

Never paste real secrets into a tracked file in this public repo. If you need
to restore a fresh server:

1. Copy this repo to the server.
2. Put real values back into `server.properties` from your private notes/env.
3. Put the real Geyser NXS token back into `plugins/Geyser-Spigot/config.yml`,
   or re-run the playit Geyser setup to generate a new one.
4. Restore `discord-bot/config.json` privately if you re-enable the Discord bot.
5. Keep `/etc/playit/playit.toml` and Geyser `identity.pem` outside Git.
