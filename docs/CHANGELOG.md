# Changelog

## 2026-11-26 (UTC)

- Added a 16:00 UTC daily backup alongside the existing 04:00 UTC backup.
- Retired the sshx watchdog and removed its `@reboot` cron entry; admin SSH now
  uses Tailscale.
- Set ImageFrame `RequireEmptyMaps: false` so players do not need blank maps.
- Refreshed README/docs and confirmed the public repo contains no live secrets.
- Added automatic sanitized game-progress snapshots to the `progress-latest`
  GitHub Release after each 04:00/16:00 UTC local backup, plus restore docs.
- Installed CuriosPaper 2.0.1 + ProbablyBackpacks 2.4 for Java/Bedrock backpacks.
  Updated the required Java pack to the `curiospaper-backpacks-pack` Release,
  added `docs/BACKPACKS.md`, and patched Geyser attachable paths so no Bedrock
  pack file exceeds 80 characters. Verified clean startup, 25 recipes, 146
  Geyser mappings, TPS 20.1, and a fresh post-install backup.
- Hardened the progress sanitizer to exclude plugin logs and include
  `shorten_geyser_backpack_paths.py` in the recovery snapshot.
- Fixed a sanitizer bug that rewrote the live Geyser config through a hardlink
  and blanked its private NXS token. Bedrock registration is restored at
  `wap-ski.tun.ply.gg:19132`.
- Diagnosed and fixed backpack item loss. ProbablyBackpacks 2.4 converted the
  Bukkit `Wrapper.map` value itself into an `ItemStack` during deserialization,
  so every stored item failed to load and the slot became empty. Replaced it with
  2.4.1, which only unwraps real `Wrapper` objects, and re-patched the Geyser
  attachable paths. Recovered the last readable gold-backpack snapshot from the
  CuriosPaper WAL before restarting. No deserialize warnings after the fix; TPS
  remains 20.1.
