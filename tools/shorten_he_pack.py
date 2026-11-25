#!/usr/bin/env python3
"""Shorten only directory names in the Human Era Bedrock pack.

Texture basenames and vanilla-style `textures/...` references are deliberately
left untouched so texture_set JSON files and Bedrock's built-in assets keep
resolving correctly.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# Directory-only replacements (note the trailing slash).
DIR_REPLS = [
    ("With Female Chest AnS/", "WFC_A/"),
    ("With Female Chest/", "WFC/"),
    ("Default AnS/", "D_A/"),
    ("assets/minecraft/optifine/random/entity/", "assets/minecraft/optifine/r/e/"),
    ("assets/minecraft/textures/entity/", "assets/minecraft/textures/e/"),
    ("zombie_villager/", "zv/"),
    ("profession_level/", "pl/"),
    ("profession/", "prof/"),
    ("copper_golem/", "cg/"),
    ("iron_golem/", "ig/"),
]
# Manifest folder_name values have no trailing slash.
FOLDER_REPLS = {
    "With Female Chest AnS": "WFC_A",
    "With Female Chest": "WFC",
    "Default AnS": "D_A",
    "Default": "Default",
}
# Fix a bad Java-style unskilled villager reference by pointing it at the
# generic villager texture that is actually included in this pack.
CONTENT_FIXES = {
    "textures/entity/villager2/professions/unskilled": "assets/minecraft/textures/e/villager/villager",
}
PACK_VERSION = [0, 0, 4]
TEXT_EXT = (".json", ".txt", ".lang", ".md", ".yml", ".yaml", ".properties")
PATH_RE = re.compile(r'(["\'])((?:assets|subpacks)/[^"\'\r\n]*)\1')


def shorten(s: str) -> str:
    for old, new in DIR_REPLS:
        s = s.replace(old, new)
    return s


def rewrite_content(name: str, data: bytes) -> bytes:
    if not name.lower().endswith(TEXT_EXT):
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    new_text = PATH_RE.sub(lambda m: m.group(1) + shorten(m.group(2)) + m.group(1), text)
    for old, new in CONTENT_FIXES.items():
        new_text = new_text.replace(old, new)
    if name == "manifest.json":
        manifest = json.loads(new_text)
        for sub in manifest.get("subpacks", []):
            old = sub.get("folder_name")
            if old in FOLDER_REPLS:
                sub["folder_name"] = FOLDER_REPLS[old]
        manifest["header"]["version"] = PACK_VERSION
        for module in manifest.get("modules", []):
            module["version"] = PACK_VERSION
        desc = manifest["header"].get("description", "")
        if "short paths" not in desc.lower():
            manifest["header"]["description"] = (desc + " Short paths for Bedrock compatibility.").strip()
        new_text = json.dumps(manifest, indent=4, ensure_ascii=False) + "\n"
    return new_text.encode("utf-8")


def unresolved_refs(zf: zipfile.ZipFile) -> list[str]:
    entries = set(zf.namelist())
    out = []
    for name in zf.namelist():
        if not name.lower().endswith(TEXT_EXT):
            continue
        try:
            text = zf.read(name).decode("utf-8")
        except UnicodeDecodeError:
            continue
        for m in PATH_RE.finditer(text):
            value = m.group(2)
            candidates = [value]
            candidates += [value + ext for ext in (".png", ".texture_set.json", ".json", ".tga")]
            if not any(c in entries for c in candidates):
                out.append(f"{name}: {value}")
    return out


def missing_texture_set_siblings(zf: zipfile.ZipFile) -> list[str]:
    import os
    entries = set(zf.namelist())
    out = []
    for name in entries:
        if not name.endswith(".texture_set.json"):
            continue
        try:
            obj = json.loads(zf.read(name))
        except Exception:
            continue
        ts = obj.get("minecraft:texture_set", {})
        d = os.path.dirname(name)
        for key in ("color", "metalness_emissive_roughness"):
            base = ts.get(key)
            if isinstance(base, str) and not any((d + "/" + base + ext) in entries for ext in (".png", ".tga")):
                out.append(f"{name}: {key} -> {base}")
    return out


with zipfile.ZipFile(SRC, "r") as zin:
    before_unresolved = unresolved_refs(zin)
    before_missing_ts = missing_texture_set_siblings(zin)
    with zipfile.ZipFile(OUT, "w") as zout:
        for info in zin.infolist():
            new_name = shorten(info.filename)
            new_info = zipfile.ZipInfo(new_name, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.comment = info.comment
            new_info.extra = info.extra
            new_info.external_attr = info.external_attr
            new_info.create_system = info.create_system
            new_info.internal_attr = info.internal_attr
            zout.writestr(new_info, rewrite_content(info.filename, zin.read(info.filename)))

with zipfile.ZipFile(OUT, "r") as zout:
    after_unresolved = unresolved_refs(zout)
    after_missing_ts = missing_texture_set_siblings(zout)
    names = zout.namelist()
    long_names = [n for n in names if len(n) >= 80]
    manifest = json.loads(zout.read("manifest.json"))
    print(f"entries: {len(names)}")
    print(f"longest path: {max(map(len, names))}")
    print(f"paths >= 80 chars: {len(long_names)}")
    print(f"unresolved refs before/after: {len(before_unresolved)}/{len(after_unresolved)}")
    print(f"missing texture_set siblings before/after: {len(before_missing_ts)}/{len(after_missing_ts)}")
    print("header version:", manifest["header"]["version"])
    print("subpack folders:", [s["folder_name"] for s in manifest["subpacks"]])
    if long_names:
        for n in long_names[:10]:
            print("LONG", len(n), n)
    if len(after_missing_ts) > len(before_missing_ts):
        print("ERROR: rewrite introduced missing texture_set siblings", file=sys.stderr)
        for r in after_missing_ts[:20]:
            print(" ", r, file=sys.stderr)
        sys.exit(1)
