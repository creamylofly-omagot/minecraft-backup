# Resource packs

There are two separate pack systems because Java and Bedrock use different pack
formats.

## Java: required ZIP from GitHub Release

The Java pack is one required merged ZIP:

```text
Human Era Villagers & Illagers + Vanilla Glowing Ores + Backpacks
```

Public download URL:

```text
https://github.com/creamylofly-omagot/minecraft-backup/releases/download/curiospaper-backpacks-pack/human-era-backpacks-v1.zip
```

SHA1:

```text
7251fd2fe34a62daf1033a43204eac885ad96f28
```

Local source copy in this repo:

```text
resource-packs/Human-Era-Backpacks-v1.zip
```

`server.properties` must contain:

```properties
require-resource-pack=true
resource-pack=https\://github.com/creamylofly-omagot/minecraft-backup/releases/download/curiospaper-backpacks-pack/human-era-backpacks-v1.zip
resource-pack-sha1=7251fd2fe34a62daf1033a43204eac885ad96f28
resource-pack-prompt={"text":"Human Era + Backpacks resource pack is required."}
```

Previous pack (kept for rollback, but has no backpack models):

```text
https://github.com/creamylofly-omagot/minecraft-backup/releases/download/v1.0.4/Human-Era-Vanilla-Glowing-Ores.zip
SHA1 216575f6c190838ec7adc1003fdfa7f0df0b26e6
```

The repository must stay **public**. Private GitHub Release assets require
authentication and the Minecraft client cannot log in to GitHub to download
them.

### Sources merged into the Java ZIP

- Human Era Villagers & Illagers X Fresh Animations 3.91.6 full content
  - Modrinth project `u69nu00u`
  - Version ID `V8BbkFtF`
- Vanilla Glowing Ores 0.2
  - Modrinth project `ZddTMHhl`
  - Version ID `LFfH5Trc`
- CuriosPaper 2.0.1 item resources
  - Modrinth project `JLMPHrRw`, version `dmu88Qpk`
- ProbablyBackpacks 2.4 item models
  - Modrinth project `d4Eqdm1Q`, version `WVHDU3vW`

The ZIP was rebuilt with all Human Era files preserved, its overlay entries
preserved, glowing ore models/textures added, backpack/curios item models added,
and the pack description changed.
No OptiFine/Continuity/Fusion is required.

### How to update the Java pack

1. Replace or rebuild `resource-packs/Human-Era-Backpacks-v1.zip`.
2. Compute SHA1:
   ```bash
   sha1sum resource-packs/Human-Era-Backpacks-v1.zip
   ```
3. Upload the new ZIP as a GitHub Release asset. Prefer a new tag/version so
   the URL stays stable for existing clients.
4. Update `resource-pack` and `resource-pack-sha1` in `server.properties`.
5. Restart the server and verify with:
   ```bash
   curl -fsSL -o /tmp/verify-pack.zip <release-url>
   sha1sum /tmp/verify-pack.zip
   ```

## Bedrock: forced `.mcpack` files through Geyser

Geyser force-sends packs from:

```text
plugins/Geyser-Spigot/packs/
```

Config:

```yaml
force-resource-packs: true
```

Files:

- `Human-Era-Villagers-Illagers-Bedrock.mcpack`
  - Repacked as pack version `0.0.4` with shortened internal paths so no path is
    80 characters or longer. This avoids Geyser's Bedrock path-length warnings.
  - Only directory names are shortened; all texture basenames are preserved, so
    `texture_set.json` files still match their PNGs.
  - Subpack folders were shortened (`WFC_A`, `D_A`, `WFC`, `Default`) while the
    player-facing subpack names were kept unchanged.
  - The bad Java-style `textures/entity/villager2/professions/unskilled`
    reference now points to the included generic villager texture. Vanilla-style
    `textures/...` references are deliberately left untouched so Bedrock can
    resolve them.
  - `tools/shorten_he_pack.py` documents/reproduces the transformation.
- `Better-Glowing-Ores-v2.4.0-RealLight.mcpack`
  - Ore textures are unchanged from v2.3.6, including PBR MER data for devices
    using Vibrant Visuals.
  - The manifest was bumped to version `2.4.0` so Bedrock clients fetch the new
    pack after the renderer change.
  - Longest internal path is 65 chars.

Backpack packs are added automatically by the plugins, not copied manually:

- `ProbablyBackpack_Geyser.zip` + `ProbablyBackpacks_mappings.json`
- `CuriosPaper_Geyser.zip` + `CuriosPaper_mappings.json`

`shorten_geyser_backpack_paths.py` keeps the ProbablyBackpacks attachable paths
under 80 characters. Re-run it after replacing/updating the ProbablyBackpacks
jar, then restart. See [`BACKPACKS.md`](BACKPACKS.md).

### Geyser custom block mappings

Texture-only alpha tricks do **not** work on vanilla Bedrock ore blocks with
Simple/Fancy graphics. The visible dark glow now comes from Geyser custom block
mappings, which register the ore block states as Bedrock custom blocks with a
real `minecraft:light_emission` component. This was chosen deliberately: the
ores now glow in the dark on low-end phones **and emit real block light**.

The mapping file is:

```text
plugins/Geyser-Spigot/custom_mappings/human_era_glowing_ores.json
```

Requirements:

- `gameplay.enable-custom-content: true` in `plugins/Geyser-Spigot/config.yml`
- Geyser restart after changing the mapping file
- The `.mcpack` stays in `plugins/Geyser-Spigot/packs/` with
  `force-resource-packs: true`

The mapping covers coal, copper, diamond, emerald, gold, iron, lapis, nether
gold, nether quartz, redstone/deepslate redstone, and ancient debris. Ordinary
ores use light level `6`; activated redstone ore uses `9`. Mining, drops, and
block behavior remain Java-side; only Bedrock's visual palette and light value
are overridden.

If a Bedrock client still shows broken Human Era textures or non-glowing ores
after this update, clear the cached server pack on that device and rejoin.

Low-end Bedrock phones do **not** need Vibrant Visuals, but the ores now produce
real light around them. This is a deliberate tradeoff: there is no vanilla
resource-pack-only way to make vanilla Bedrock ore materials self-lit without
either Vibrant Visuals/PBR, a shader loader, or real block light.

The Bedrock `.mcpack` files and the custom mapping JSON are also attached to the
GitHub Release for backup, but Geyser still reads them from the local Geyser
data folder on the server.
