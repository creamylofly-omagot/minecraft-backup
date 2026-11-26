# Runbook

All live paths below assume the server user is `naze` and the server directory is
`/home/naze/minecraft-public`.

## Normal service commands

```bash
systemctl status minecraft-public --no-pager -l
sudo systemctl restart minecraft-public
sudo systemctl stop minecraft-public
sudo systemctl start minecraft-public
```

`sudo` may require the user password on this machine. If so, clean restart can
also be done through RCON because the unit has `Restart=always`:

```bash
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "say Restarting now"
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "save-all flush"
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "stop"
```

systemd will start it again after `RestartSec=15`.

## View logs

```bash
tail -f /home/naze/minecraft-public/logs/latest.log
tail -f /home/naze/minecraft-public/logs/service.log
```

Useful log checks after a restart:

- `Done (` — server finished starting
- `Registered with the external signaling service` — Geyser NXS/playit OK
- plugin enable messages for Geyser, Floodgate, LuckPerms, CoreProtect, etc.
- no resource pack download/load errors

## RCON examples

```bash
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "list"
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "tps"
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "plugins"
python3 /home/naze/rcon.py "$MC_RCON_PASSWORD" "save-all flush"
```

Do not put the real password in shell history or in this repo.

## Verify the GitHub-hosted Java resource pack

```bash
curl -fsSL -o /tmp/verify-pack.zip \
  https://github.com/creamylofly-omagot/minecraft-backup/releases/download/v1.0.4/Human-Era-Vanilla-Glowing-Ores.zip
sha1sum /tmp/verify-pack.zip
```

Expected SHA1:

```text
216575f6c190838ec7adc1003fdfa7f0df0b26e6
```

The public URL must stay public. If the repo is made private, Java players will
not be able to download the pack.

## Local backups

Cron entries (UTC):

```text
0 4 * * * /home/naze/minecraft-public/backup.sh >> /home/naze/minecraft-public/logs/backup.log 2>&1
0 16 * * * /home/naze/minecraft-public/backup.sh >> /home/naze/minecraft-public/logs/backup.log 2>&1
```

The 16:00 entry was added on 2026-11-26; the original 04:00 backup is kept.

Archives go to:

```text
/home/naze/backups/minecraft-public/
```

Seven archives are kept.

## Chest/container audit

Autostart entry in cron:

```text
@reboot /usr/bin/tmux new-session -d -s chest-audit 'cd /home/naze/minecraft-public && while true; do /usr/bin/python3 /home/naze/minecraft-public/chest_audit_monitor.py --interval 3 --log-file /home/naze/minecraft-public/logs/chest-audit.log; sleep 5; done'
```

Check:

```bash
tmux ls
tail -f /home/naze/minecraft-public/logs/chest-audit.log
```

## Restore onto a fresh machine

1. Clone this repo:
   ```bash
   git clone https://github.com/creamylofly-omagot/minecraft-backup.git /home/naze/minecraft-public
   ```
2. Restore secrets from `docs/SECRETS.md`.
3. Install Java 25 and make `start.sh` executable:
   ```bash
   chmod +x /home/naze/minecraft-public/start.sh /home/naze/minecraft-public/backup.sh
   ```
4. Install the host unit files from `host/` into `/etc/systemd/system/` and run:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now minecraft-public
   sudo systemctl enable --now minecraft-perf
   ```
5. Install/enable playit using `host/playit.service` and your private
   `/etc/playit/playit.toml`.
6. Restore the crontab from `host/crontab-naze.txt`.
7. Start and verify with the log checks above.

## Do not lower these

```properties
view-distance=4
simulation-distance=3
entity-broadcast-range-percentage=60
```

These are already tuned for the 1-CPU/5400rpm-HDD host.
