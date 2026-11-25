#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

DB_DEFAULT = "/home/naze/minecraft-public/plugins/CoreProtect/database.db"
STATE_DEFAULT = "/home/naze/minecraft-public/logs/chest-audit.state.json"
LOG_DEFAULT = "/home/naze/minecraft-public/logs/chest-audit.log"
RCON_DEFAULT = "/home/naze/rcon.py"
RCON_PASS_DEFAULT = os.environ.get("MC_RCON_PASSWORD", "")

CONTAINER_KEYWORDS = (
    "chest", "barrel", "shulker_box", "hopper", "dispenser", "dropper",
    "furnace", "smoker", "brewing_stand", "decorated_pot",
)


def ts_fmt(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {
            "container_rowid": int(d.get("container_rowid", 0)),
            "open_rowid": int(d.get("open_rowid", 0)),
        }
    except Exception:
        return {"container_rowid": 0, "open_rowid": 0}


def save_state(path, state):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def telegram_send(token, chat_id, text):
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()


def rcon_say(rcon_path, password, msg):
    msg = msg.replace("\n", " ")
    if len(msg) > 220:
        msg = msg[:217] + "..."
    try:
        subprocess.run([sys.executable, rcon_path, password, f"say {msg}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass


def append_log(path, line):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_container_material(name):
    if not name:
        return False
    n = str(name).lower()
    if n.startswith("minecraft:"):
        n = n[len("minecraft:"):]
    return any(k in n for k in CONTAINER_KEYWORDS)


def init_state_to_latest(cur):
    cur.execute("select ifnull(max(rowid),0) from co_container")
    c = int(cur.fetchone()[0] or 0)
    cur.execute("select ifnull(max(rowid),0) from co_block where action=2")
    o = int(cur.fetchone()[0] or 0)
    return {"container_rowid": c, "open_rowid": o}


def open_db(db_path):
    # read-only to avoid interfering with CoreProtect
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)


def fetch_opens(cur, last_rowid):
    cur.execute(
        """
        select b.rowid, b.time, u.user as player, m.material, b.x, b.y, b.z, w.world
        from co_block b
        left join co_user u on b.user=u.id
        left join co_material_map m on b.type=m.id
        left join co_world w on b.wid=w.id
        where b.action=2 and b.rowid > ?
        order by b.rowid asc
        """,
        (last_rowid,),
    )
    rows = []
    max_seen = last_rowid
    for r in cur.fetchall():
        rowid, t, player, material, x, y, z, world = r
        if rowid > max_seen:
            max_seen = rowid
        if not is_container_material(material):
            continue
        if player and str(player).startswith("#"):
            continue
        rows.append({
            "rowid": rowid, "time": t, "player": player or "unknown",
            "material": material or "unknown", "x": x, "y": y, "z": z, "world": world or "world",
        })
    return rows, max_seen


def fetch_container(cur, last_rowid):
    cur.execute(
        """
        select c.rowid, c.time, u.user as player, m.material, c.amount, c.action, c.x, c.y, c.z, w.world
        from co_container c
        left join co_user u on c.user=u.id
        left join co_material_map m on c.type=m.id
        left join co_world w on c.wid=w.id
        where c.rowid > ?
        order by c.rowid asc
        """,
        (last_rowid,),
    )
    rows = []
    max_seen = last_rowid
    for r in cur.fetchall():
        rowid, t, player, material, amount, action, x, y, z, world = r
        if rowid > max_seen:
            max_seen = rowid
        verb = "took" if int(action) == 0 else "put"
        rows.append({
            "rowid": rowid, "time": t, "player": player or "unknown",
            "item": material or "unknown", "amount": amount,
            "action": int(action), "verb": verb,
            "x": x, "y": y, "z": z, "world": world or "world",
        })
    return rows, max_seen


def format_open(e):
    return f"[CHEST] {ts_fmt(e['time'])} {e['player']} opened {e['material']} at {e['world']} {e['x']},{e['y']},{e['z']}"


def format_container(e):
    return (f"[CHEST] {ts_fmt(e['time'])} {e['player']} {e['verb']} {e['amount']}x {e['item']} "
            f"({'from' if e['action']==0 else 'into'} container at {e['world']} {e['x']},{e['y']},{e['z']})")


def main():
    ap = argparse.ArgumentParser(description="Monitor chest/container opens and item transactions (CoreProtect-backed)")
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--state", default=STATE_DEFAULT)
    ap.add_argument("--log-file", default=LOG_DEFAULT)
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--once", action="store_true", help="Process new events once and exit")
    ap.add_argument("--from-now", action="store_true", help="Initialize state to current DB end (ignore history)")
    ap.add_argument("--include-history", type=int, default=0, help="On first run, include last N existing rows")
    ap.add_argument("--rcon-say", action="store_true", help="Broadcast events in-game via RCON say")
    ap.add_argument("--rcon-path", default=RCON_DEFAULT)
    ap.add_argument("--rcon-pass", default=RCON_PASS_DEFAULT)
    ap.add_argument("--telegram-token", default=os.environ.get("TELEGRAM_BOT_TOKEN"))
    ap.add_argument("--telegram-chat", default=os.environ.get("TELEGRAM_CHAT_ID"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"DB not found: {args.db}", file=sys.stderr)
        return 2

    while True:
        try:
            con = open_db(args.db)
            cur = con.cursor()
            state = load_state(args.state)
            first = (state["container_rowid"] == 0 and state["open_rowid"] == 0 and not os.path.exists(args.state))
            if first:
                if args.from_now or args.include_history <= 0:
                    state = init_state_to_latest(cur)
                    if args.include_history <= 0:
                        save_state(args.state, state)
                else:
                    cur.execute("select ifnull(max(rowid),0) from co_container")
                    mc = int(cur.fetchone()[0] or 0)
                    cur.execute("select ifnull(max(rowid),0) from co_block where action=2")
                    mo = int(cur.fetchone()[0] or 0)
                    state = {"container_rowid": max(0, mc - args.include_history), "open_rowid": max(0, mo - args.include_history)}

            opens, open_max = fetch_opens(cur, state["open_rowid"])
            txs, cont_max = fetch_container(cur, state["container_rowid"])
            con.close()

            merged = []
            for e in opens:
                merged.append((e.get("time", 0), e["rowid"], format_open(e)))
            for e in txs:
                merged.append((e.get("time", 0), e["rowid"], format_container(e)))
            merged.sort()

            if merged:
                for _, _, line in merged:
                    if not args.quiet:
                        print(line, flush=True)
                    append_log(args.log_file, line)
                    if args.rcon_say:
                        rcon_say(args.rcon_path, args.rcon_pass, line)
                    if args.telegram_token and args.telegram_chat:
                        try:
                            telegram_send(args.telegram_token, args.telegram_chat, line)
                        except Exception:
                            pass

            new_state = {
                "open_rowid": max(int(state.get("open_rowid", 0)), int(open_max)),
                "container_rowid": max(int(state.get("container_rowid", 0)), int(cont_max)),
            }
            if new_state != state or merged:
                save_state(args.state, new_state)
            state = new_state
        except Exception as e:
            print(f"chest_audit_monitor error: {e}", file=sys.stderr)

        if args.once:
            break
        time.sleep(max(0.5, args.interval))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
