# Resource packs

There are two separate pack systems because Java and Bedrock use different pack
formats.

## Java: required ZIP from GitHub Release

The Java pack is one required merged ZIP:

```text
Human Era Villagers & Illagers + Vanilla Glowing Ores
```

Public download URL:

```text
https://github.com/creamylofly-omagot/minecraft-backup/releases/download/v1.0.4/Human-Era-Vanilla-Glowing-Ores.zip
```

SHA1:

```text
216575f6c190838ec7adc1003fdfa7f0df0b26e6
```

Local source copy in this repo:

```text
resource-packs/Human-Era-Vanilla-Glowing-Ores.zip
```

`server.properties` must contain:

```properties
require-resource-pack=true
resource-pack=https\://github.com/creamylofly-omagot/minecraft-backup/releases/download/v1.0.4/Human-Era-Vanilla-Glowing-Ores.zip
resource-pack-sha1=216575f6c190838ec7adc1003fdfa7f0df0b26e6
resource-pack-prompt={"text":"Human Era Villagers & Illagers + Vanilla Glowing Ores resource pack is required."}
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

The ZIP was rebuilt with all Human Era files preserved, its overlay entries
preserved, glowing ore models/textures added, and the pack description changed.
No OptiFine/Continuity/Fusion is required.

### How to update the Java pack

1. Replace or rebuild `resource-packs/Human-Era-Vanilla-Glowing-Ores.zip`.
2. Compute SHA1:
   ```bash
   sha1sum resource-packs/Human-Era-Vanilla-Glowing-Ores.zip
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
- `Better-Glowing-Ores-v2.3.6.mcpack`
  - Classic glow is built into the main pack: ore pixels that have an emissive
    MER value are written with alpha `252`, which Bedrock's classic renderer
    treats as fullbright. This gives visible glow on low-end phones without
    Vibrant Visuals.
  - No subpack is required. Geyser-forced server packs do not expose subpack
    selection to Bedrock clients, so the old `night_vision_on` subpack was
    removed instead of relying on default-subpack behavior.
  - PBR MER data is retained for devices using Vibrant Visuals.
  - Longest internal path is 65 chars.

If a Bedrock client still shows broken Human Era textures or non-glowing ores
after this update, clear the cached server pack on that device and rejoin.

Low-end Bedrock phones do **not** need Vibrant Visuals. The classic glow is a
self-lit texture effect; it does not make ores emit real block light into nearby
blocks.

The Bedrock `.mcpack` files are also attached to the GitHub Release for backup,
but Geyser still reads them from the local `packs/` folder on the server.
