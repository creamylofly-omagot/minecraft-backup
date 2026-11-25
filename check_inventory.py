#!/usr/bin/env python3
import argparse
import gzip
import io
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
WORLD = BASE / "world"
PLAYERDATA = WORLD / "players" / "data"
USERCACHE = BASE / "usercache.json"

# ---- Minimal NBT parser (Java Edition / big-endian) ----

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


class NBTReader:
    def __init__(self, data: bytes):
        self.f = io.BytesIO(data)

    def _read(self, fmt):
        size = struct.calcsize(fmt)
        buf = self.f.read(size)
        if len(buf) != size:
            raise EOFError("Unexpected end of NBT data")
        return struct.unpack(fmt, buf)[0]

    def read_byte(self):
        return self._read(">b")

    def read_ubyte(self):
        return self._read(">B")

    def read_short(self):
        return self._read(">h")

    def read_int(self):
        return self._read(">i")

    def read_long(self):
        return self._read(">q")

    def read_float(self):
        return self._read(">f")

    def read_double(self):
        return self._read(">d")

    def read_string(self):
        ln = self._read(">H")
        data = self.f.read(ln)
        if len(data) != ln:
            raise EOFError("Unexpected end in string")
        try:
            return data.decode("utf-8")
        except Exception:
            return data.decode("utf-8", "replace")

    def read_payload(self, tag_type):
        if tag_type == TAG_BYTE:
            return self.read_byte()
        if tag_type == TAG_SHORT:
            return self.read_short()
        if tag_type == TAG_INT:
            return self.read_int()
        if tag_type == TAG_LONG:
            return self.read_long()
        if tag_type == TAG_FLOAT:
            return self.read_float()
        if tag_type == TAG_DOUBLE:
            return self.read_double()
        if tag_type == TAG_BYTE_ARRAY:
            ln = self.read_int()
            data = self.f.read(ln)
            if len(data) != ln:
                raise EOFError("Unexpected end in byte array")
            return list(struct.unpack(">" + "b" * ln, data)) if ln else []
        if tag_type == TAG_STRING:
            return self.read_string()
        if tag_type == TAG_LIST:
            elem_type = self.read_ubyte()
            ln = self.read_int()
            return [self.read_payload(elem_type) for _ in range(max(ln, 0))]
        if tag_type == TAG_COMPOUND:
            out = {}
            while True:
                t = self.read_ubyte()
                if t == TAG_END:
                    break
                name = self.read_string()
                out[name] = self.read_payload(t)
            return out
        if tag_type == TAG_INT_ARRAY:
            ln = self.read_int()
            data = self.f.read(4 * ln)
            if len(data) != 4 * ln:
                raise EOFError("Unexpected end in int array")
            return list(struct.unpack(">" + "i" * ln, data)) if ln else []
        if tag_type == TAG_LONG_ARRAY:
            ln = self.read_int()
            data = self.f.read(8 * ln)
            if len(data) != 8 * ln:
                raise EOFError("Unexpected end in long array")
            return list(struct.unpack(">" + "q" * ln, data)) if ln else []
        raise ValueError(f"Unknown NBT tag type: {tag_type}")

    def read_named(self):
        t = self.read_ubyte()
        if t == TAG_END:
            return ("", None)
        name = self.read_string()
        value = self.read_payload(t)
        return (name, value)


def load_nbt(path: Path):
    with gzip.open(path, "rb") as f:
        data = f.read()
    r = NBTReader(data)
    _, value = r.read_named()
    return value  # root compound


# ---- Helpers ----

def load_usercache():
    if not USERCACHE.exists():
        return []
    try:
        with open(USERCACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def uuid_to_name_map():
    out = {}
    for e in load_usercache():
        u = (e.get("uuid") or "").lower()
        n = e.get("name")
        if u and n:
            out[u] = n
    return out


def list_registered_players():
    # all playerdata files = registered/seen players with saved data
    names = uuid_to_name_map()
    players = []
    if PLAYERDATA.exists():
        for p in sorted(PLAYERDATA.glob("*.dat")):
            uuid = p.stem
            name = names.get(uuid.lower(), uuid)
            players.append({"name": name, "uuid": uuid, "path": str(p)})
    # sort by display name
    players.sort(key=lambda x: (x["name"].lower(), x["uuid"].lower()))
    return players


def find_players(query: str):
    q = query.lower().strip()
    cache = load_usercache()
    matches = []
    for e in cache:
        name = e.get("name", "")
        uuid = e.get("uuid", "")
        if q == name.lower() or q == uuid.lower():
            matches.append((name, uuid, "usercache-exact"))
        elif q in name.lower() or q in uuid.lower():
            matches.append((name, uuid, "usercache"))
    if PLAYERDATA.exists():
        for p in PLAYERDATA.glob("*.dat"):
            uuid = p.stem
            name = None
            for e in cache:
                if e.get("uuid", "").lower() == uuid.lower():
                    name = e.get("name")
                    break
            label = name or uuid
            if q == uuid.lower() or (name and q == name.lower()):
                if not any(m[1].lower() == uuid.lower() for m in matches):
                    matches.append((label, uuid, "file-exact"))
            elif q in uuid.lower() or (name and q in name.lower()):
                if not any(m[1].lower() == uuid.lower() for m in matches):
                    matches.append((label, uuid, "file"))
    seen = set()
    out = []
    for m in sorted(matches, key=lambda x: (0 if x[2].endswith("exact") else 1, x[0].lower())):
        if m[1].lower() in seen:
            continue
        seen.add(m[1].lower())
        out.append(m)
    return out


def item_id(item):
    return item.get("id") or item.get("Id") or "unknown"


def item_count(item):
    for k in ("count", "Count"):
        if k in item:
            v = item[k]
            try:
                return int(v)
            except Exception:
                try:
                    return int(str(v))
                except Exception:
                    return 1
    return 1


def slot_name(slot):
    try:
        s = int(slot)
    except Exception:
        return str(slot)
    if 0 <= s <= 8:
        return f"hotbar[{s}]"
    if 9 <= s <= 35:
        return f"inv[{s-9}]"
    if s == 100:
        return "armor.feet"
    if s == 101:
        return "armor.legs"
    if s == 102:
        return "armor.chest"
    if s == 103:
        return "armor.head"
    if s in (-106, 150):
        return "offhand"
    return f"slot:{s}"


def pretty_item_id(iid: str) -> str:
    s = str(iid)
    if ":" in s:
        s = s.split(":", 1)[1]
    s = s.replace("_", " ").strip()
    return s.title() if s else str(iid)


def pretty_dimension(dim):
    if dim is None:
        return None
    d = str(dim)
    mapping = {
        "minecraft:overworld": "Overworld",
        "minecraft:the_nether": "Nether",
        "minecraft:the_end": "End",
        "overworld": "Overworld",
        "the_nether": "Nether",
        "the_end": "End",
    }
    if d in mapping:
        return mapping[d]
    if ":" in d:
        d = d.split(":", 1)[1]
    return d.replace("_", " ").title()


def item_details(item):
    comps = item.get("components") or {}
    tag = item.get("tag") or {}
    details = []
    dmg = comps.get("minecraft:damage") if isinstance(comps, dict) else None
    if dmg is None and isinstance(tag, dict):
        dmg = tag.get("Damage")
    if dmg is not None:
        details.append(f"dmg {dmg}")
    # custom name best-effort
    cname = None
    if isinstance(comps, dict):
        cname = comps.get("minecraft:custom_name")
    if cname is None and isinstance(tag, dict):
        disp = tag.get("display")
        if isinstance(disp, dict):
            cname = disp.get("Name")
    if cname:
        details.append("named")
    # enchantments best-effort
    ench = None
    if isinstance(comps, dict):
        ench = comps.get("minecraft:enchantments") or comps.get("minecraft:stored_enchantments")
    if ench is None and isinstance(tag, dict):
        ench = tag.get("Enchantments") or tag.get("StoredEnchantments")
    if ench:
        details.append("enchanted")
    return details


def format_item_line(item, readable=True):
    iid = str(item_id(item))
    cnt = item_count(item)
    slot = item.get("Slot", item.get("slot", "?"))
    name = pretty_item_id(iid) if readable else iid
    details = item_details(item)
    det = f" ({', '.join(details)})" if details else ""
    if readable:
        return f"  • {slot_name(slot)} — {name} x{cnt}{det}  [{iid}]"
    return f"  - {slot_name(slot):<12} {iid} x{cnt}{det}"


def collect_container_items(items, only=None):
    rows = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        iid = str(item_id(it))
        if only and only.lower() not in iid.lower():
            continue
        slot = it.get("Slot", it.get("slot", "?"))
        rows.append((slot, it, iid))
    def sk(r):
        s = r[0]
        try:
            return (0, int(s))
        except Exception:
            return (1, str(s))
    rows.sort(key=sk)
    return rows


def load_player_data(uuid):
    dat = PLAYERDATA / f"{uuid}.dat"
    used_old = False
    if not dat.exists():
        alt = PLAYERDATA / f"{uuid}.dat_old"
        if alt.exists():
            dat = alt
            used_old = True
        else:
            return None, dat, used_old, "not_found"
    try:
        root = load_nbt(dat)
        return root, dat, used_old, None
    except Exception as e:
        return None, dat, used_old, str(e)


def analyze_player(name, uuid, only=None):
    root, dat, used_old, err = load_player_data(uuid)
    result = {
        "name": name,
        "uuid": uuid,
        "file": str(dat),
        "used_old": used_old,
        "error": err,
        "inventory": [],
        "ender": [],
        "total_matches": 0,
        "dimension": None,
        "position": None,
    }
    if err or root is None:
        return result
    inv = root.get("Inventory") or root.get("inventory") or []
    ender = root.get("EnderItems") or root.get("EnderChestInventory") or []
    result["inventory"] = collect_container_items(inv, only=only)
    result["ender"] = collect_container_items(ender, only=only)
    rows = result["inventory"] + result["ender"]
    result["total_matches"] = sum(item_count(it) for _, it, _ in rows)
    dim = root.get("Dimension")
    result["dimension"] = pretty_dimension(dim) if dim is not None else None
    pos = root.get("Pos")
    if isinstance(pos, list) and len(pos) >= 3:
        try:
            result["position"] = (float(pos[0]), float(pos[1]), float(pos[2]))
        except Exception:
            result["position"] = None
    return result


def format_player_block(r, only=None, readable=True):
    lines = []
    header = f"🔹 {r['name']}" if readable else f"Player: {r['name']}"
    lines.append(header)
    lines.append(f"UUID: {r['uuid']}")
    if r.get("used_old"):
        lines.append(f"File: {r['file']} (used .dat_old fallback)")
    if r.get("error"):
        if r["error"] == "not_found":
            lines.append("Status: playerdata file not found")
        else:
            lines.append(f"Status: error reading data ({r['error']})")
        return lines
    if r.get("dimension") or r.get("position"):
        loc_parts = []
        if r.get("dimension"):
            loc_parts.append(r["dimension"])
        if r.get("position"):
            x, y, z = r["position"]
            loc_parts.append(f"({x:.1f}, {y:.1f}, {z:.1f})")
        lines.append("Location: " + " @ ".join(loc_parts) if readable else "Last known: " + " ".join(loc_parts))
    if only:
        lines.append(f"Matching '{only}': {r['total_matches']}")
    if r["inventory"]:
        lines.append("Inventory:" if readable else "== Inventory ==")
        for _, it, _ in r["inventory"]:
            lines.append(format_item_line(it, readable=readable))
    if r["ender"]:
        lines.append("Ender Chest:" if readable else "== Ender Chest ==")
        for _, it, _ in r["ender"]:
            lines.append(format_item_line(it, readable=readable))
    if not r["inventory"] and not r["ender"]:
        if only:
            lines.append(f"No items matching '{only}'.")
        else:
            lines.append("No items found in inventory/ender chest.")
    return lines


def format_all_report(results, only=None, saved_note=True):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = []
    title = "Minecraft Inventory Check"
    if only:
        title += f" — '{only}'"
    lines.append(title)
    lines.append(f"Time: {now}")
    lines.append(f"Players checked: {len(results)}")
    if only:
        lines.append(f"Filter: item id contains \"{only}\" (e.g. diamonds, tools, blocks, etc.)")
    if saved_note:
        lines.append("Source: saved playerdata (run save-all / have players disconnect for freshest data)")
    lines.append("")

    errors = [r for r in results if r.get("error")]
    if only:
        holders = [r for r in results if not r.get("error") and r.get("total_matches", 0) > 0]
        empty = [r for r in results if not r.get("error") and r.get("total_matches", 0) == 0]
        total_found = sum(r.get("total_matches", 0) for r in holders)
        lines.append(f"Summary: {len(holders)} player(s) with matches, {len(empty)} without, total matching items: {total_found}")
        lines.append("")
        if holders:
            lines.append("=== Players with matches ===")
            for r in holders:
                lines.extend(format_player_block(r, only=only, readable=True))
                lines.append("")
        if empty:
            lines.append("=== No matches ===")
            for r in empty:
                lines.append(f"  • {r['name']} — 0")
            lines.append("")
    else:
        lines.append("=== Player inventories ===")
        for r in results:
            lines.extend(format_player_block(r, only=None, readable=True))
            lines.append("")

    if errors:
        lines.append("=== Errors ===")
        for r in errors:
            msg = "file not found" if r["error"] == "not_found" else r["error"]
            lines.append(f"  • {r['name']} ({r['uuid']}): {msg}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def chunk_text(text, limit=4000):
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    return chunks


def send_telegram(text, token, chat_id):
    if not token or not chat_id:
        raise ValueError("Missing Telegram token or chat id")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = chunk_text(text, limit=4000)
    results = []
    for i, chunk in enumerate(chunks, 1):
        prefix = f"[{i}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": prefix + chunk,
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace")
            ok = False
            try:
                ok = bool(json.loads(body).get("ok"))
            except Exception:
                ok = '"ok":true' in body
            results.append((i, ok, body))
        except Exception as e:
            err_body = ""
            if hasattr(e, "read"):
                try:
                    err_body = e.read().decode("utf-8", "replace")
                except Exception:
                    pass
            results.append((i, False, f"{e} {err_body}".strip()))
    return results


def print_player_human(r, only=None):
    # single-player detailed, readable
    print(f"Player: {r['name']}")
    print(f"UUID:   {r['uuid']}")
    print(f"File:   {r['file']}" + (" (using .dat_old fallback)" if r.get('used_old') else ""))
    if r.get("error"):
        if r["error"] == "not_found":
            print("Error: playerdata file not found.")
        else:
            print(f"Error: failed to read playerdata ({r['error']})")
        return
    print("Note: if the player is currently ONLINE, saved data can be stale until they disconnect or the server runs save-all.")
    if r["inventory"]:
        print("\n== Inventory ==")
        for _, it, _ in r["inventory"]:
            print(format_item_line(it, readable=False))
    if r["ender"]:
        print("\n== Ender Chest ==")
        for _, it, _ in r["ender"]:
            print(format_item_line(it, readable=False))
    if not r["inventory"] and not r["ender"]:
        if only:
            print(f"\nNo items matching '{only}' found.")
        else:
            print("\nNo items found.")
    if only:
        print(f"\nTotal matching '{only}': {r['total_matches']}")
    if r.get("dimension") or r.get("position"):
        print("\n== Player state ==")
        if r.get("dimension"):
            print(f"  Dimension: {r['dimension']}")
        if r.get("position"):
            x, y, z = r["position"]
            print(f"  Last position: {x:.1f}, {y:.1f}, {z:.1f}")


def main():
    ap = argparse.ArgumentParser(description="Check Minecraft player inventories from saved playerdata (.dat). Works for offline players; online players may be stale until save-all/logout.")
    ap.add_argument("player", nargs="?", help="Player name, partial name, or UUID")
    ap.add_argument("--find", "-f", help="Only show items whose id contains this text (e.g. diamond)")
    ap.add_argument("--list", "-l", action="store_true", help="List known players and UUIDs")
    ap.add_argument("--uuid", help="Use this UUID directly")
    ap.add_argument("--all", action="store_true", help="Check all registered players (all playerdata .dat files)")
    ap.add_argument("--send-telegram", action="store_true", help="Send the report to Telegram")
    ap.add_argument("--telegram-token", default=os.environ.get("TELEGRAM_BOT_TOKEN"), help="Telegram bot token (or TELEGRAM_BOT_TOKEN env)")
    ap.add_argument("--telegram-chat", default=os.environ.get("TELEGRAM_CHAT_ID"), help="Telegram chat id (or TELEGRAM_CHAT_ID env)")
    ap.add_argument("--report-file", help="Also write the generated report to this file")
    ap.add_argument("--no-save-note", action="store_true", help="Omit the note about save-all/freshness in all-player reports")
    args = ap.parse_args()

    if args.list:
        cache = load_usercache()
        print("Known players (from usercache.json):")
        for e in sorted(cache, key=lambda x: (x.get("name") or "").lower()):
            print(f"  {e.get('name','?'):<20} {e.get('uuid','?')}")
        reg = list_registered_players()
        if reg:
            print(f"\nRegistered players with saved data ({len(reg)}):")
            for p in reg:
                print(f"  {p['name']:<20} {p['uuid']}")
        print("\nUsage: python3 check_inventory.py <player|--all> [--find diamond] [--send-telegram]")
        return 0

    if args.all:
        players = list_registered_players()
        if not players:
            msg = f"No playerdata files found in {PLAYERDATA}"
            print(msg, file=sys.stderr)
            return 3
        results = [analyze_player(p["name"], p["uuid"], only=args.find) for p in players]
        report = format_all_report(results, only=args.find, saved_note=not args.no_save_note)
        print(report)
        if args.report_file:
            Path(args.report_file).write_text(report, encoding="utf-8")
            print(f"Report written to: {args.report_file}")
        if args.send_telegram:
            try:
                tg = send_telegram(report, args.telegram_token, args.telegram_chat)
            except Exception as e:
                print(f"Telegram send failed: {e}", file=sys.stderr)
                return 5
            for i, ok, body in tg:
                status = "OK" if ok else "FAILED"
                print(f"Telegram chunk {i}: {status}")
            if not all(ok for _, ok, _ in tg):
                for i, ok, body in tg:
                    if not ok:
                        print(f"  chunk {i} error: {body[:500]}", file=sys.stderr)
                return 5
        return 0

    if not args.player and not args.uuid:
        ap.print_help()
        return 1

    query = args.uuid or args.player
    matches = find_players(query) if not args.uuid else [(args.uuid, args.uuid, "direct")]
    if not matches:
        print(f"No player found matching '{query}'. Try --list to see known players.", file=sys.stderr)
        return 2

    exact = [m for m in matches if m[2].endswith("exact") or m[2] == "direct"]
    chosen = exact[0] if len(exact) == 1 else (matches[0] if len(matches) == 1 else None)
    if chosen is None:
        print(f"Multiple players match '{query}'. Be more specific:")
        for name, uuid, _ in matches[:20]:
            print(f"  {name:<20} {uuid}")
        return 2

    name, uuid, _ = chosen
    r = analyze_player(name, uuid, only=args.find)
    if r.get("error") == "not_found":
        print(f"Playerdata file not found for {name} ({uuid})\nExpected: {PLAYERDATA / (uuid + '.dat')}", file=sys.stderr)
        return 3
    if r.get("error"):
        print(f"Failed to read NBT for {name} ({uuid}): {r['error']}", file=sys.stderr)
        return 4

    print_player_human(r, only=args.find)

    if args.send_telegram:
        # send a readable single-player report
        lines = [f"Minecraft Inventory Check — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"]
        if args.find:
            lines.append(f"Filter: item id contains \"{args.find}\"")
        lines.append("")
        lines.extend(format_player_block(r, only=args.find, readable=True))
        report = "\n".join(lines).rstrip() + "\n"
        try:
            tg = send_telegram(report, args.telegram_token, args.telegram_chat)
        except Exception as e:
            print(f"\nTelegram send failed: {e}", file=sys.stderr)
            return 5
        for i, ok, _ in tg:
            print(f"\nTelegram chunk {i}: {'OK' if ok else 'FAILED'}")
        if not all(ok for _, ok, _ in tg):
            return 5
    return 0


# >>> fast-anything: check_inventory.py:analyze_player >>>
# Uses the verified Rust port. FAST_ANYTHING_DISABLE=1 runs the Python above instead.
# Undo with:  fast-anything disable check_inventory.py:analyze_player
def _fast_anything_load():
    import os, sys
    if os.environ.get("FAST_ANYTHING_DISABLE"):
        return None
    lib = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fast/lib"))
    if lib not in sys.path:
        sys.path.append(lib)
    try:
        from fa_check_inventory_py_analyze_player import analyze_player
    except ImportError:
        return None
    return analyze_player
analyze_player = _fast_anything_load() or analyze_player
del _fast_anything_load
# <<< fast-anything: check_inventory.py:analyze_player <<<

if __name__ == "__main__":
    raise SystemExit(main())
