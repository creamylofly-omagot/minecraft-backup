# Backpacks for Java + Bedrock (2026-11-26)

Installed on Paper **26.2 build 135** with Geyser/Floodgate. Java and Bedrock
players use the same backpack items; Geyser maps the custom items to Bedrock
attachables.

## Versions and why

- **CuriosPaper 2.0.1** — Modrinth project `JLMPHrRw`, version `dmu88Qpk`
  - Original SHA256: `6fbe1dd5181f49744b84434a193c9d4d6b82d7c8478ea9c91a6ab4b7abe48e51`
- **ProbablyBackpacks 2.4.1** — Modrinth project `d4Eqdm1Q`, version `g9qnB7xR`
  - Original SHA256: `f995681964979d6ad8364d9f28c07238b8e27bb8`
  - Local patched jar SHA256: `8e7983879f1587d9097d06b2c4b194e8ee3d84d152bb8767bf4fb33e6643b763`
- **ProbablyBackpacks 2.4** (replaced) — Modrinth version `WVHDU3vW`
  - Local patched jar SHA256: `56aed1b7c2e52e4a84342717dd0d7c6d735b893a383d58a50c390c94d280ddfd`

Version 2.4 was chosen instead of 2.5 because 2.4 documents support for Paper
26.2 and explicit Geyser compatibility. Version 2.5 expects CuriosPaper 3.0 /
Synthetix, which was not confirmed for this server. On 2026-11-26, 2.4 was found
to deserialize Bukkit `Wrapper` map objects as `ItemStack`s, causing every
backpack item to be dropped on load. 2.4.1 keeps the same Paper 26.2 /
CuriosPaper 2.0.1 compatibility but only unwraps actual `Wrapper` objects, fixing
that data-loss bug.

Pre-install backup: `/home/naze/backups/minecraft-public/minecraft-public-20261126-132438.tar.gz`  
Post-install backup: `/home/naze/backups/minecraft-public/minecraft-public-20261126-133927.tar.gz`  
Pre-2.4.1-fix backup: `/home/naze/backups/minecraft-public/minecraft-public-20261126-152114.tar.gz`

## Player usage

The `default` LuckPerms group has `probablybackpacks.use`.

| Command | Effect |
| --- | --- |
| `/bp` | Open your backpack (player only) |
| `/baubles` (aliases `/b`, `/bbag`) | Open the Curios accessory/back slot GUI |
| `/curios` | List CuriosPaper admin/debug commands |

Hotkey (from `plugins/ProbablyBackpacks/config.yml`): select hotbar slot **9**,
then **double-sneak** to open the backpack from the Curios back slot.

Backpack tiers and crafting shapes are in `plugins/ProbablyBackpacks/backpacks.yml`:

| Tier | Recipe | Slots |
| --- | --- | ---: |
| Leather | `STRING, LEATHER, CHEST` | 27 |
| Copper | `COPPER_INGOT` ring around a leather backpack | 45 |
| Iron | `IRON_INGOT` ring around a copper backpack | 54 |
| Gold | `GOLD_INGOT` ring around an iron backpack | 81 |
| Diamond | `DIAMOND` ring around a gold backpack | 108 |
| Netherite | Smithing: diamond backpack + netherite ingot + template | 120 |

Upgrade items (magnet, feeding, pickup, smelting, stack, etc.) are defined in
`plugins/ProbablyBackpacks/upgrades.yml`.

## Resource packs

### Java

`server.properties` now sends one required merged pack:

```text
https://github.com/creamylofly-omagot/minecraft-backup/releases/download/curiospaper-backpacks-pack/human-era-backpacks-v1.zip
```

SHA1: `7251fd2fe34a62daf1033a43204eac885ad96f28`

It combines the previous Human-Era + Glowing Ores pack with the CuriosPaper and
ProbablyBackpacks item models. Local source:
`resource-packs/Human-Era-Backpacks-v1.zip`. The old v1.0.4 pack URL remains
available for rollback but does **not** contain backpack models.

CuriosPaper is configured with `resource-pack.mode: NONE`; it does not send its
own pack. The external Human-Era pack is still copied into
`plugins/CuriosPaper/external-resource-packs/` so CuriosPaper can build a
compatible internal pack. The `pack.mcmeta` self-conflict shown by
`/curios rp conflicts` is cosmetic; the GitHub-hosted pack above is authoritative.

### Bedrock

Geyser already has:

```yaml
enable-custom-content: true
force-resource-packs: true
```

On startup the plugins copy these into Geyser:

- `plugins/Geyser-Spigot/packs/ProbablyBackpack_Geyser.zip`
- `plugins/Geyser-Spigot/packs/CuriosPaper_Geyser.zip`
- `plugins/Geyser-Spigot/custom_mappings/ProbablyBackpacks_mappings.json`
- `plugins/Geyser-Spigot/custom_mappings/CuriosPaper_mappings.json`

ProbablyBackpacks 2.4/2.4.1 ships attachable paths longer than 80 characters,
which some Bedrock clients reject. `shorten_geyser_backpack_paths.py` renamed
them to short, unique paths. Because the plugin regenerates its pack from its
jar on every start, the script patched:

1. the embedded `ProbablyBackpack_Geyser.zip` inside `plugins/ProbablyBackpacks-2.4.1.jar`;
2. `plugins/ProbablyBackpacks/geyser/ProbablyBackpack_Geyser.zip`;
3. `plugins/Geyser-Spigot/packs/ProbablyBackpack_Geyser.zip`.

Originals are kept as `*.longpaths.bak`. **After replacing or updating the
ProbablyBackpacks jar, run `python3 shorten_geyser_backpack_paths.py` and restart
once more.** The current startup has zero long-path warnings.

## Verification (2026-11-26 15:25 UTC)

- `CuriosPaper 2.0.1` and `ProbablyBackpacks 2.4.1` enabled cleanly.
- CuriosPaper loaded 9 slots and registered 25 recipes.
- Geyser loaded 131 ProbablyBackpacks mappings and 15 CuriosPaper mappings.
- Java pack download SHA1 matched the configured SHA1.
- Geyser Bedrock long-path warnings: 0.
- No `Failed to deserialize item at index` warnings after the 2.4.1 restart.
- Recovered the last readable gold-backpack snapshot from the CuriosPaper SQLite
  WAL (`minecraft:wheat` 64+64+8 and `minecraft:wheat_seeds` 64×4) into
  `probably_backpacks.inventory` before restarting.
- TPS: `20.1 / 20.1 / 20.1`; `minecraft-public`, `playit`, `minecraft-perf` active.

## Rollback

Use RCON, which avoids needing `sudo` because the unit uses `Restart=always`:

```bash
PASS="$(grep -m1 '^rcon.password=' server.properties | cut -d= -f2-)"
python3 /home/naze/rcon.py "$PASS" "save-all flush"
python3 /home/naze/rcon.py "$PASS" "stop"
```

For a plugin-only rollback, remove `plugins/CuriosPaper-2.0.1.jar` and
`plugins/ProbablyBackpacks-2.4.1.jar`, restore the v1.0.4 `resource-pack` URL and
SHA1 in `server.properties` (see `docs/RESOURCE_PACKS.md` history), then let
systemd restart the service. For a full rollback, restore the pre-install backup
above.
