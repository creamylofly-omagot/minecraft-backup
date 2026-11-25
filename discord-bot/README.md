# Minecraft Server Discord Monitor Bot

This bot monitors your local Paper/Geyser Minecraft server and provides Discord commands for:

- **Server status** (systemd service + online players + disk summary)
- **Storage checking** (disk usage and per-path sizes) + periodic low-storage alerts
- **Chest/container monitoring** (live feed of container opens and item take/put, plus recent/audit queries) backed by **CoreProtect**
- **Minecraft console/RCON input** (run server commands from Discord, admin-only)

Files:
- `bot.py` – Discord bot
- `config.example.json` – example config
- `requirements.txt` – Python dependencies (`discord.py`)
- `state.json` – created automatically (tracks last processed CoreProtect rows for live chest feed)

> Server directory assumed: `/home/naze/minecraft-public` (Paper 26.2, service `minecraft-public`, CoreProtect installed).

---

## 1) Create the Discord bot and get a token

1. Open the Discord Developer Portal: https://discord.com/developers/applications
2. Click **New Application** → name it (e.g. `MC Monitor`) → Create.
3. Go to **Bot** (left sidebar):
   - Click **Reset Token** / **Copy** the token and save it (you’ll put it in `config.json`). Treat it like a password.
   - Under **Privileged Gateway Intents**, enable **MESSAGE CONTENT INTENT** (required because this bot uses prefix commands like `!status`).
   - (Optional) Set the bot username/icon.
4. Invite the bot to your server:
   - Go to **OAuth2 → URL Generator**.
   - **Scopes:** check `bot` (and optionally `applications.commands`).
   - **Bot Permissions:** at minimum `View Channels`, `Send Messages`, `Read Message History` (add `Embed Links` if you want, not required). For admin-only console commands, Discord permissions don’t replace the bot’s own admin check—keep the bot in trusted channels.
   - Copy the generated URL, open it, select your server, and authorize.
5. Get IDs (enable Discord **Developer Mode**: User Settings → Advanced → Developer Mode):
   - Right-click your server → **Copy Server ID** (optional `guild_id`).
   - Right-click the channel for live chest logs → **Copy Channel ID** (`chest_channel_id`).
   - Right-click a channel for storage/server alerts → **Copy Channel ID** (`alert_channel_id`, can be same as chest).
   - Right-click your user → **Copy User ID** (put in `admin_user_ids` so you can run `!mc`).

---

## 2) Install dependencies (recommended: `uv` venv)

This system has `uv` available (`/home/naze/.local/bin/uv`) but no system `pip` module. The easiest setup is a virtualenv + `uv pip`.

```bash
cd /home/naze/minecraft-public/discord-bot

# create a virtual environment
uv venv .venv

# install dependencies into it
uv pip install --python .venv/bin/python -r requirements.txt
```

> If you prefer standard venv/pip and have pip available: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

Verify:
```bash
.venv/bin/python -c "import discord; print(discord.__version__)"
```

---

## 3) Configure the bot

```bash
cd /home/naze/minecraft-public/discord-bot
cp config.example.json config.json
chmod 600 config.json   # contains secrets (bot token, RCON password)
```

Edit `config.json`:

| Field | What to set |
|---|---|
| `token` | **Required.** Your Discord bot token from step 1. |
| `command_prefix` | Command prefix (default `!`). |
| `guild_id` | Optional server/guild ID (0 = any). |
| `chest_channel_id` | Channel ID where live chest/container events are posted (0 = disabled). |
| `alert_channel_id` | Channel ID for storage warnings (0 = disabled). |
| `admin_user_ids` | List of Discord user IDs allowed to run `!mc` (console/RCON). Example: `[123456789012345678]`. |
| `admin_role_ids` | Optional role IDs allowed to run `!mc`. If both admin lists are empty, guild Administrators are allowed. |
| `rcon_path` | Path to RCON helper (default `/home/naze/rcon.py`). |
| `rcon_password` | RCON password for the server (used by `!mc`, `!players`, `!status`). Keep private. |
| `rcon_python` | Python to run the RCON helper (default `/usr/bin/python3`). |
| `minecraft_service` | systemd service name (default `minecraft-public`). |
| `server_dir` | Server root for disk checks (default `/home/naze/minecraft-public`). |
| `coreprotect_db` | CoreProtect SQLite DB (default `/home/naze/minecraft-public/plugins/CoreProtect/database.db`). |
| `state_file` | State file for live chest monitor cursor (default `discord-bot/state.json`). |
| `storage_paths` | Directories/files to size-check for `!storage`. |
| `storage_warn_percent` | Send alert when disk usage >= this percent (default 90). |
| `storage_check_minutes` | How often to check storage for alerts (default 30). |
| `chest_poll_seconds` | How often to poll CoreProtect for new chest events (default 5). |
| `status_poll_seconds` | Reserved/general polling interval (default 60). |

**Important:** `!mc` lets authorized users execute arbitrary Minecraft/server commands via RCON (e.g. `stop`, `op`, `ban`). Only put trusted user/role IDs in `admin_user_ids`/`admin_role_ids`, and keep `config.json` readable only by you (`chmod 600`).

---

## 4) Test run

```bash
cd /home/naze/minecraft-public/discord-bot
.venv/bin/python bot.py
```

You should see something like:
```
Logged in as <BotName> (id=...)
Guilds: [...]
```

In Discord (in a channel the bot can read/send), try:
- `!ping`
- `!status`
- `!players`
- `!storage`
- `!chestrecent 10`
- `!chestplayer <name> 10`
- `!mc list` (admin only)

Stop with `Ctrl+C`.

**Live chest feed:** when `chest_channel_id` is set, the bot polls CoreProtect and posts new events since it started (it initializes its cursor to the current DB end on first run, so it won’t spam old history). Events include:
- container opens (e.g. chest/barrel/shulker opened) — from CoreProtect player interactions
- item **took/put** with amount and item — from CoreProtect container transactions

---

## 5) Run persistently (keep it running)

### Option A: tmux (simple)

```bash
tmux new-session -d -s mc-discord-bot 'cd /home/naze/minecraft-public/discord-bot && ./.venv/bin/python bot.py'
```

- Reattach: `tmux attach -t mc-discord-bot`
- Detach: `Ctrl-b` then `d`
- View recent output without attaching: `tmux capture-pane -pt mc-discord-bot -S -80`
- Stop: `tmux kill-session -t mc-discord-bot`

> `tmux` keeps the bot running when you close your terminal/SSH session, but it will **not** auto-start after a reboot.

### Option B: systemd service (auto-start on boot)

Create `/etc/systemd/system/mc-discord-bot.service` (requires sudo/root):

```ini
[Unit]
Description=Minecraft Discord Monitor Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=naze
WorkingDirectory=/home/naze/minecraft-public/discord-bot
ExecStart=/home/naze/minecraft-public/discord-bot/.venv/bin/python /home/naze/minecraft-public/discord-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mc-discord-bot
sudo systemctl status mc-discord-bot
sudo journalctl -u mc-discord-bot -f
```

(Use the method appropriate for your environment; if `sudo` is unavailable/non-interactive, use the tmux option.)

---

## 6) Commands reference

| Command | Description | Access |
|---|---|---|
| `!ping` | Bot latency. | Everyone |
| `!status` / `!server` | Service state, disk summary, online players (RCON `list`). | Everyone |
| `!players` / `!list` / `!online` | Online players via RCON. | Everyone |
| `!storage` / `!disk` / `!df` | Detailed disk + configured path sizes. | Everyone |
| `!chestrecent [n]` | Last `n` container transactions (default 10, max 30). | Everyone |
| `!chestplayer <name> [n]` / `!audit <name>` | Last `n` container transactions for a player (tries exact and Bedrock `.`-prefixed name). | Everyone |
| `!mc <command>` / `!rcon <command>` / `!console <command>` | Run a Minecraft command via RCON (e.g. `!mc say Hello`, `!mc whitelist list`, `!mc save-all`). | **Admin only** |

---

## 7) Notes & troubleshooting

- **CoreProtect required for chest monitoring.** The bot reads `coreprotect_db` (read-only). Container open events rely on `player-interactions: true` and item take/put on `item-transactions: true` in CoreProtect (both are enabled on this server). History/queries (`!chestrecent`, `!chestplayer`) and the live feed come from this data.
- **RCON dependency.** `!mc`, `!players`, and player info in `!status` call `rcon.py` with `rcon_password`. If RCON is unreachable/auth fails, those parts will show an error but other features still work.
- **Storage sizes.** `!storage` computes per-path sizes with `du` (can take a moment on large worlds). Periodic alerts use overall disk usage of `server_dir`.
- **No backfill spam.** On first run the live chest monitor starts from the current end of the CoreProtect log; delete/reset `state.json` (or adjust its rowids) if you want different behavior.
- **Token/intents issues.** If the bot comes online but doesn’t respond to commands, confirm **MESSAGE CONTENT INTENT** is enabled in the Developer Portal and the bot has permission to read/send in the channel.
- **Logs.** When run in tmux, check `tmux capture-pane -pt mc-discord-bot -S -200`. When run as a systemd service, check `journalctl -u mc-discord-bot -f`.
- **Security.** Protect `config.json` (token + RCON password). Restrict `!mc` admins. Consider running the bot in a private/staff channel.

## Quick setup summary

```bash
cd /home/naze/minecraft-public/discord-bot
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp config.example.json config.json && chmod 600 config.json
# edit config.json: set token, chest_channel_id, alert_channel_id, admin_user_ids
tmux new-session -d -s mc-discord-bot 'cd /home/naze/minecraft-public/discord-bot && ./.venv/bin/python bot.py'
```
