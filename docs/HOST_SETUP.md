# Host setup

These files live outside the server folder but are required for the public
server to run the way it does.

## systemd units

### `host/minecraft-public.service`

Install as `/etc/systemd/system/minecraft-public.service`.

- User: `naze`
- WorkingDirectory: `/home/naze/minecraft-public`
- ExecStart: `/home/naze/minecraft-public/start.sh`
- `Restart=always`, `RestartSec=15`
- Output appended to `logs/service.log`
- Enabled at boot

Commands:

```bash
sudo cp host/minecraft-public.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-public
```

### `host/minecraft-perf.service`

Install as `/etc/systemd/system/minecraft-perf.service`.

- One-shot boot tuning
- Runs `/usr/local/bin/minecraft-perf.sh`
- `RemainAfterExit=yes`
- Enabled at boot

### `host/playit.service`

This is the distro/service-manager unit for the playit agent. The live agent
uses private `/etc/playit/playit.toml`. The secret file is not in this repo; see
`host/playit.toml.example` for the shape only.

## Host tuning script

Install `host/minecraft-perf.sh` as `/usr/local/bin/minecraft-perf.sh`.

It does:

- CPU governor `performance` on available cores
- `swappiness=10`
- `dirty_background_ratio=5`
- `dirty_ratio=10`
- `vfs_cache_pressure=50`
- `mq-deadline` and 8 MB readahead on `/dev/sda`
- iptables/ip6tables rules:
  - drops external access to RCON port `25575`
  - drops external access to Java port `25565` except loopback and `192.168.0.0/16`
  - public Java/Bedrock access comes through playit tunnels from loopback

Do not expose RCON publicly.

## Crontab

Install `host/crontab-naze.txt` with:

```bash
crontab -u naze host/crontab-naze.txt
```

Entries:

- 04:00 nightly `backup.sh`
- `@reboot` chest-audit tmux session
- `@reboot` sshx watchdog

## playit / Geyser networking

Java public address:

```text
ambulance-exporters.tun.ply.gg:25565
```

Bedrock public address:

```text
wap-ski.tun.ply.gg:19132
```

Bedrock uses playit **Minecraft Bedrock (NetherNet)** with Geyser NXS:

- `bedrock.transport: nethernet`
- `signaling.mode: nxs`
- `webrtc-port: 0`

If the playit tunnel changes, copy fresh settings from playit tunnel
**Configuration help -> Geyser** into `plugins/Geyser-Spigot/config.yml`, restore
the private NXS token, and restart the server.

## Old server

The older whitelisted server remains at `/home/naze/minecraft` on the live host.
Its service is stopped and disabled. Only one server can use the ports at a
time.
