#!/usr/bin/env python3
"""Shorten ProbablyBackpacks Geyser attachable paths for wider Bedrock support.

ProbablyBackpacks 2.4 ships Bedrock attachable files under long paths such as
`attachables/item/backpack/legacy/netherite/...attachable.json`. Some Bedrock
clients reject paths of 80+ characters. The attachable identifier is inside the
JSON, so the filename/path can be shortened without changing mappings.

The plugin regenerates its pack from the jar on every startup, so this script
patches the jar's embedded pack as well as the generated source and Geyser copy.
Run after plugin install/update; a restart is required for Geyser to reload it.
"""

from __future__ import annotations

import copy
import hashlib
import io
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JAR = ROOT / "plugins" / "ProbablyBackpacks-2.4.jar"
NESTED_PACK_NAME = "ProbablyBackpack_Geyser.zip"
PACKS = [
    ROOT / "plugins" / "ProbablyBackpacks" / "geyser" / NESTED_PACK_NAME,
    ROOT / "plugins" / "Geyser-Spigot" / "packs" / NESTED_PACK_NAME,
]
LONG_RES = [
    re.compile(
        r"^attachables/item/backpack/legacy/[^/]+/"
        r"probablybackpacks_backpack_legacy_([^/]+)\.attachable\.json$"
    ),
    re.compile(
        r"^attachables/item/upgrades/"
        r"probablybackpacks_upgrades_([^/]+)\.attachable\.json$"
    ),
]


def short_name(match: re.Match[str]) -> str:
    suffix = match.group(1)
    digest = hashlib.sha1(suffix.encode("utf-8")).hexdigest()[:8]
    safe = re.sub(r"[^a-z0-9_]", "_", suffix)
    prefix = "pb_bag" if "backpack/legacy" in match.string else "pb_up"
    return f"attachables/{prefix}_{safe}_{digest}.json"


def shorten_zip(data: bytes) -> tuple[bytes, int, int]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = zf.infolist()
        payload = {info.filename: zf.read(info.filename) for info in infos if not info.is_dir()}
        comment = zf.comment

    renamed: dict[str, str] = {}
    for name in payload:
        for pattern in LONG_RES:
            match = pattern.match(name)
            if match:
                renamed[name] = short_name(match)
                break
    remaining = sum(len(name) >= 80 for name in payload if name not in renamed)
    if not renamed:
        return data, 0, remaining

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for info in infos:
            if info.is_dir():
                continue
            new_info = copy.copy(info)
            new_info.filename = renamed.get(info.filename, info.filename)
            zout.writestr(new_info, payload[info.filename])
        zout.comment = comment
    return out.getvalue(), len(renamed), remaining


def backup_once(path: Path) -> None:
    backup = path.with_name(path.name + ".longpaths.bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def shorten_file(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    data = path.read_bytes()
    patched, changed, remaining = shorten_zip(data)
    if changed:
        backup_once(path)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(patched)
        tmp.replace(path)
    return changed, remaining


def patch_jar(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        payload = {info.filename: zf.read(info.filename) for info in infos if not info.is_dir()}
        comment = zf.comment
    if NESTED_PACK_NAME not in payload:
        return 0, 0

    patched_pack, changed, remaining = shorten_zip(payload[NESTED_PACK_NAME])
    if not changed:
        return 0, remaining

    backup_once(path)
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zout:
        for info in infos:
            if info.is_dir():
                continue
            data = patched_pack if info.filename == NESTED_PACK_NAME else payload[info.filename]
            zout.writestr(info, data)
        zout.comment = comment
    tmp.replace(path)
    return changed, remaining


def main() -> None:
    jar_changed, jar_remaining = patch_jar(JAR)
    print(f"{JAR}: patched embedded pack ({jar_changed} renamed, {jar_remaining} long paths remain)")
    total_remaining = jar_remaining
    for pack in PACKS:
        changed, remaining = shorten_file(pack)
        print(f"{pack}: renamed {changed}, remaining long paths {remaining}")
        total_remaining += remaining
    if total_remaining:
        raise SystemExit(f"{total_remaining} long paths remain after shortening")


if __name__ == "__main__":
    main()
