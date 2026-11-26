# Changelog

## 2026-11-26 (UTC)

- Added a 16:00 UTC daily backup alongside the existing 04:00 UTC backup.
- Retired the sshx watchdog and removed its `@reboot` cron entry; admin SSH now
  uses Tailscale.
- Set ImageFrame `RequireEmptyMaps: false` so players do not need blank maps.
- Refreshed README/docs and confirmed the public repo contains no live secrets.
