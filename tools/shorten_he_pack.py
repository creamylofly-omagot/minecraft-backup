#!/usr/bin/env python3
"""Shorten internal paths in the Human Era Bedrock pack for Geyser compatibility."""
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# Applied consistently to entry names and to quoted path strings in pack files.
REPLS = [
    ("With Female Chest AnS", "WFC_A"),
    ("With Female Chest", "WFC"),
    ("Default AnS", "D_A"),
    ("assets/minecraft/optifine/random/entity", "assets/minecraft/optifine/r/e"),
    ("assets/minecraft/textures/entity", "assets/minecraft/textures/e"),
    ("zombie_villager", "zv"),
    ("profession_level", "pl"),
    ("profession", "prof"),
    ("copper_golem", "cg"),
    ("iron_golem", "ig"),
]
TEXT_EXT = (".json", ".txt", ".lang", ".md", ".yml", ".yaml", ".properties")
PATH_RE = re.compile(r'(["\'])((?:assets|textures|subpacks)/[^"\'\r\n]*)\1')


def shorten(s: str) -> str:
    for old, new in REPLS:
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
    if name == "manifest.json":
        manifest = json.loads(new_text)
        for sub in manifest.get("subpacks", []):
            if "folder_name" in sub:
                sub["folder_name"] = shorten(sub["folder_name"])
        manifest["header"]["version"] = [0, 0, 2]
        for module in manifest.get("modules", []):
            module["version"] = [0, 0, 2]
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
        for match in PATH_RE.finditer(text):
            value = match.group(2)
            candidates = [value]
            candidates += [value + ext for ext in (".png", ".texture_set.json", ".json", ".tga")]
            if value.startswith("textures/"):
                candidates.append("assets/minecraft/" + value)
                candidates += ["assets/minecraft/" + value + ext for ext in (".png", ".texture_set.json", ".json", ".tga")]
            if not any(c in entries for c in candidates):
                out.append(f"{name}: {value}")
    return out


with zipfile.ZipFile(SRC, "r") as zin:
    before_unresolved = unresolved_refs(zin)
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
    names = zout.namelist()
    long_names = [n for n in names if len(n) >= 80]
    manifest = json.loads(zout.read("manifest.json"))
    print(f"entries: {len(names)}")
    print(f"renamed entries: {sum(shorten(n) != n for n in names)}")  # informational only
    print(f"longest path: {max(map(len, names))}")
    print(f"paths >= 80 chars: {len(long_names)}")
    print(f"unresolved refs before: {len(before_unresolved)}")
    print(f"unresolved refs after:  {len(after_unresolved)}")
    print("header version:", manifest["header"]["version"])
    print("subpack folders:", [s["folder_name"] for s in manifest["subpacks"]])
    if long_names:
        for n in long_names[:10]:
            print("LONG", len(n), n)
    if len(after_unresolved) > len(before_unresolved):
        print("ERROR: rewrite introduced unresolved path references", file=sys.stderr)
        for r in after_unresolved[:20]:
            print(" ", r, file=sys.stderr)
        sys.exit(1)
