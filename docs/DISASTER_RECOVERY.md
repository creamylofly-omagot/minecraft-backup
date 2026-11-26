# Disaster recovery from GitHub

The `progress-latest` GitHub Release contains a **sanitized** snapshot of the
live server's game progress. It is rebuilt and uploaded automatically after
each local backup (**04:00 and 16:00 UTC**).

Download the latest asset:

```bash
gh release download progress-latest --repo creamylofly-omagot/minecraft-backup \
  -p 'minecraft-progress-latest.tar.gz'
```

Direct URL:

```text
https://github.com/creamylofly-omagot/minecraft-backup/releases/download/progress-latest/minecraft-progress-latest.tar.gz
```

The release notes show the date/time of the current asset.

## Restore procedure

1. Stop the live server if one is running:
   ```bash
   sudo systemctl stop minecraft-public
   ```
2. Clone this repo for jars, scripts, and host files:
   ```bash
   git clone https://github.com/creamylofly-omagot/minecraft-backup.git /home/naze/minecraft-public
   ```
3. Extract the progress asset:
   ```bash
   mkdir -p /tmp/mc-restore
   tar -xzf minecraft-progress-latest.tar.gz -C /tmp/mc-restore
   ```
   This creates `/tmp/mc-restore/minecraft-public/`.
4. Copy the saved data over the clone:
   ```bash
   cp -a /tmp/mc-restore/minecraft-public/world /home/naze/minecraft-public/
   cp -a /tmp/mc-restore/minecraft-public/config /home/naze/minecraft-public/
   cp -a /tmp/mc-restore/minecraft-public/plugins/. /home/naze/minecraft-public/plugins/
   cp -a /tmp/mc-restore/minecraft-public/spigot.yml /home/naze/minecraft-public/
   cp -a /tmp/mc-restore/minecraft-public/bukkit.yml /home/naze/minecraft-public/
   cp -a /tmp/mc-restore/minecraft-public/ops.json /home/naze/minecraft-public/
   cp -a /tmp/mc-restore/minecraft-public/whitelist.json /home/naze/minecraft-public/
   ```
5. **Do not use the archived `server.properties` as-is.** It contains
   placeholders. Keep your private copy or restore real values from
   [`SECRETS.md`](SECRETS.md):
   - `rcon.password`
   - `management-server-secret`
   - Geyser NXS token in `plugins/Geyser-Spigot/config.yml`
   - Discord bot private config, if you re-enable the bot
   - `/etc/playit/playit.toml` and Geyser `identity.pem` from private notes
6. Fix permissions and start:
   ```bash
   chmod +x /home/naze/minecraft-public/start.sh /home/naze/minecraft-public/backup.sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now minecraft-public
   ```
7. Verify:
   ```bash
   tail -f /home/naze/minecraft-public/logs/latest.log
   ```
   Look for `Done (`, plugin enable messages, and Geyser's
   `Registered with the external signaling service`.

## What is intentionally excluded

Plugin `.jar` files (already in the repo/Releases), real secrets/tokens,
Geyser identity and token backups, the retired `sshx_watchdog.py`, Discord bot
private config, logs, cache, `.fast/`, `versions/`, and `libraries/`.

If you still have the local archives in `/home/naze/backups/minecraft-public/`,
prefer those for an identical restore; the GitHub asset is the fallback when
the server folder is gone.
