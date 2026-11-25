#!/usr/bin/env python3
import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

try:
    import discord
    from discord.ext import commands, tasks
except Exception:
    print("discord.py is not installed. Create venv and install requirements first (see README.md).", file=sys.stderr)
    raise

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

# make server inventory checker importable
_SERVER_DIR = BASE_DIR.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))
try:
    import check_inventory as invcheck
except Exception:
    invcheck = None

DEFAULT_CONFIG = {
    "token": "PUT_YOUR_DISCORD_BOT_TOKEN_HERE",
    "command_prefix": "!",
    "guild_id": 0,
    "chest_channel_id": 0,
    "alert_channel_id": 0,
    "admin_user_ids": [],
    "admin_role_ids": [],
    "rcon_path": "/home/naze/rcon.py",
    "rcon_password": "",
    "rcon_python": "/usr/bin/python3",
    "minecraft_service": "minecraft-public",
    "server_dir": "/home/naze/minecraft-public",
    "coreprotect_db": "/home/naze/minecraft-public/plugins/CoreProtect/database.db",
    "state_file": str(BASE_DIR / "state.json"),
    "storage_paths": [
        "/home/naze/minecraft-public",
        "/home/naze/minecraft-public/world",
        "/home/naze/minecraft-public/plugins",
        "/home/naze/minecraft-public/logs",
    ],
    "storage_warn_percent": 90,
    "storage_check_minutes": 30,
    "chest_poll_seconds": 5,
    "status_poll_seconds": 60,
}

CONTAINER_KEYWORDS = (
    "chest", "barrel", "shulker_box", "hopper", "dispenser", "dropper",
    "furnace", "smoker", "brewing_stand", "decorated_pot",
)

# in-memory cache for du results
_DU_CACHE = {"ts": 0.0, "text": None}
_DU_CACHE_TTL = 120  # seconds


def load_config():
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing config: {CONFIG_PATH}. Copy config.example.json to config.json and edit it.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        user = json.load(f)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(user or {})
    return cfg


def human_bytes(n):
    try:
        n = int(n)
    except Exception:
        return str(n)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    if i == 0:
        return f"{int(f)} {units[i]}"
    return f"{f:.2f} {units[i]}"


def ts_fmt(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def short_mat(name):
    if not name:
        return "unknown"
    n = str(name)
    return n[len("minecraft:"):] if n.startswith("minecraft:") else n


def is_container_material(name):
    if not name:
        return False
    n = str(name).lower()
    if n.startswith("minecraft:"):
        n = n[len("minecraft:"):]
    return any(k in n for k in CONTAINER_KEYWORDS)


def disk_summary_text(target):
    try:
        usage = shutil.disk_usage(target)
        pct = (usage.used / usage.total * 100) if usage.total else 0
        return (pct, f"{human_bytes(usage.used)} / {human_bytes(usage.total)} used ({pct:.1f}%) — free {human_bytes(usage.free)}")
    except Exception as e:
        return (0.0, f"unavailable ({e})")


def _compute_storage_report(server_dir, storage_paths):
    target = server_dir or "/home/naze/minecraft-public"
    lines = []
    pct, summary = disk_summary_text(target)
    lines.append(f"Disk ({target}): {summary}")
    for p in (storage_paths or []):
        try:
            if not os.path.exists(p):
                lines.append(f"- {p}: (missing)")
                continue
            pr = subprocess.run(["du", "-sb", p], capture_output=True, text=True, timeout=25)
            if pr.returncode == 0 and pr.stdout.strip():
                size = int(pr.stdout.split()[0])
                lines.append(f"- {p}: {human_bytes(size)}")
            else:
                err = (pr.stderr or "").strip().splitlines()[-1] if pr.stderr else "unavailable"
                lines.append(f"- {p}: ({err[:60]})")
        except subprocess.TimeoutExpired:
            lines.append(f"- {p}: (timed out)")
        except Exception as e:
            lines.append(f"- {p}: (error: {e})")
    return "\n".join(lines)


def get_storage_report_cached(server_dir, storage_paths, force=False):
    now = time.time()
    if not force and _DU_CACHE["text"] is not None and (now - _DU_CACHE["ts"]) < _DU_CACHE_TTL:
        return _DU_CACHE["text"]
    text = _compute_storage_report(server_dir, storage_paths)
    _DU_CACHE["text"] = text
    _DU_CACHE["ts"] = time.time()
    return text


def chunk_text(text, limit=1900):
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks = []
    buf = ""
    for line in text.splitlines():
        if len(line) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(line), limit):
                chunks.append(line[i:i + limit])
            continue
        add = (("\n" + line) if buf else line)
        if len(buf) + len(add) > limit:
            if buf:
                chunks.append(buf)
            buf = line
        else:
            buf += add
    if buf:
        chunks.append(buf)
    return chunks or [""]


class MonitorBot(commands.Bot):
    def __init__(self, cfg):
        intents = discord.Intents.default()
        intents.message_content = True
        prefix = cfg.get("command_prefix", "!")
        super().__init__(command_prefix=prefix, intents=intents, help_command=None, case_insensitive=True)
        self.cfg = cfg
        self.state = self.load_state()
        self._state_dirty = False
        self._last_storage_alert = 0.0
        self._chest_channel = None
        self._alert_channel = None
        self.start_time = time.time()
        self.add_commands()

    # ---------- storage brief ----------
    def storage_brief(self):
        target = self.cfg.get("server_dir") or "/home/naze/minecraft-public"
        _, txt = disk_summary_text(target)
        return f"💾 Storage: {txt}"

    def set_embed_footer(self, embed, extra=None):
        parts = [p for p in [extra, self.storage_brief()] if p]
        embed.set_footer(text=" • ".join(parts))
        return embed

    # ---------- state ----------
    def load_state(self):
        path = Path(self.cfg.get("state_file") or (BASE_DIR / "state.json"))
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return {
                "container_rowid": int(d.get("container_rowid", 0)),
                "open_rowid": int(d.get("open_rowid", 0)),
            }
        except Exception:
            return {"container_rowid": 0, "open_rowid": 0}

    def save_state(self, force=False):
        if not force and not self._state_dirty:
            return
        path = Path(self.cfg.get("state_file") or (BASE_DIR / "state.json"))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f)
            os.replace(tmp, path)
            self._state_dirty = False
        except Exception as e:
            print("save_state error:", e, file=sys.stderr)

    # ---------- auth ----------
    def is_admin(self, ctx):
        uid = getattr(ctx.author, "id", None)
        try:
            admin_users = set(int(x) for x in (self.cfg.get("admin_user_ids") or []))
        except Exception:
            admin_users = set()
        if uid in admin_users:
            return True
        try:
            role_ids = set(int(r) for r in (self.cfg.get("admin_role_ids") or []))
        except Exception:
            role_ids = set()
        if role_ids and isinstance(getattr(ctx, "author", None), discord.Member):
            if any(r.id in role_ids for r in ctx.author.roles):
                return True
        if getattr(ctx, "guild", None) and getattr(ctx.author, "guild_permissions", None):
            if ctx.author.guild_permissions.administrator:
                if not (self.cfg.get("admin_user_ids") or self.cfg.get("admin_role_ids")):
                    return True
        return False

    async def ensure_admin(self, ctx):
        if self.is_admin(ctx):
            return True
        e = discord.Embed(
            title="Permission denied",
            description="You are not allowed to use this command.\nConfigure `admin_user_ids` or `admin_role_ids` in `config.json`.",
            color=discord.Color.red(),
        )
        self.set_embed_footer(e)
        await ctx.reply(embed=e, mention_author=False)
        return False

    # ---------- helpers ----------
    async def run_shell(self, args, timeout=20):
        def _run():
            try:
                p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
                out = (p.stdout or "")
                if p.stderr:
                    out = (out + "\n" + p.stderr) if out else p.stderr
                return p.returncode, out.strip()
            except subprocess.TimeoutExpired:
                return 124, "Command timed out"
            except Exception as e:
                return 1, str(e)
        return await asyncio.to_thread(_run)

    async def rcon(self, command):
        rcon_path = self.cfg.get("rcon_path") or "/home/naze/rcon.py"
        rcon_pw = self.cfg.get("rcon_password") or ""
        rcon_py = self.cfg.get("rcon_python") or sys.executable
        if not rcon_pw:
            return 2, "RCON password not configured (rcon_password)."
        return await self.run_shell([rcon_py, rcon_path, rcon_pw, command], timeout=20)

    def db_conn(self):
        db = self.cfg.get("coreprotect_db")
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    async def resolve_channel(self, cid, cache_attr):
        ch = getattr(self, cache_attr, None)
        if ch is not None:
            return ch
        if not cid:
            return None
        try:
            cid = int(cid)
        except Exception:
            return None
        ch = self.get_channel(cid)
        if ch is None:
            try:
                ch = await self.fetch_channel(cid)
            except Exception:
                ch = None
        setattr(self, cache_attr, ch)
        return ch

    # ---------- chest monitor ----------
    def init_chest_state_if_needed(self):
        if self.state.get("container_rowid") or self.state.get("open_rowid"):
            return
        db = self.cfg.get("coreprotect_db")
        if not db or not os.path.exists(db):
            return
        try:
            con = self.db_conn()
            cur = con.cursor()
            cur.execute("select ifnull(max(rowid),0) from co_container")
            cmax = int(cur.fetchone()[0] or 0)
            cur.execute("select ifnull(max(rowid),0) from co_block where action=2")
            omax = int(cur.fetchone()[0] or 0)
            con.close()
            self.state["container_rowid"] = cmax
            self.state["open_rowid"] = omax
            self._state_dirty = True
            self.save_state(force=True)
            print(f"Chest monitor initialized: container_rowid={cmax}, open_rowid={omax}")
        except Exception as e:
            print("init_chest_state error:", e, file=sys.stderr)

    def fetch_new_chest_events(self, limit=200):
        db = self.cfg.get("coreprotect_db")
        if not db or not os.path.exists(db):
            return []
        events = []
        con = self.db_conn()
        cur = con.cursor()

        last_open = int(self.state.get("open_rowid", 0))
        cur.execute(
            """
            select b.rowid, b.time, u.user as player, m.material, b.x, b.y, b.z, w.world
            from co_block b
            left join co_user u on b.user=u.id
            left join co_material_map m on b.type=m.id
            left join co_world w on b.wid=w.id
            where b.action=2 and b.rowid > ?
            order by b.rowid asc limit ?
            """,
            (last_open, limit),
        )
        max_open = last_open
        for r in cur.fetchall():
            rid = int(r["rowid"])
            if rid > max_open:
                max_open = rid
            mat = r["material"] or "unknown"
            player = r["player"] or "unknown"
            if is_container_material(mat) and not str(player).startswith("#"):
                events.append((int(r["time"] or 0), rid,
                               f"🟦 **{player}** opened `{short_mat(mat)}` at `{r['world'] or 'world'} {r['x']},{r['y']},{r['z']}` · `{ts_fmt(r['time'])}`"))

        last_c = int(self.state.get("container_rowid", 0))
        cur.execute(
            """
            select c.rowid, c.time, u.user as player, m.material, c.amount, c.action, c.x, c.y, c.z, w.world
            from co_container c
            left join co_user u on c.user=u.id
            left join co_material_map m on c.type=m.id
            left join co_world w on c.wid=w.id
            where c.rowid > ?
            order by c.rowid asc limit ?
            """,
            (last_c, limit),
        )
        max_c = last_c
        for r in cur.fetchall():
            rid = int(r["rowid"])
            if rid > max_c:
                max_c = rid
            player = r["player"] or "unknown"
            item = short_mat(r["material"])
            amt = r["amount"] if r["amount"] is not None else "?"
            action = int(r["action"] or 0)
            if action == 0:
                icon, verb, prep = "🔻", "took", "from"
            else:
                icon, verb, prep = "🔺", "put", "into"
            events.append((int(r["time"] or 0), rid,
                           f"{icon} **{player}** {verb} `{amt}x {item}` {prep} container at `{r['world'] or 'world'} {r['x']},{r['y']},{r['z']}` · `{ts_fmt(r['time'])}`"))
        con.close()

        if max_open != self.state.get("open_rowid", 0):
            self.state["open_rowid"] = max_open
            self._state_dirty = True
        if max_c != self.state.get("container_rowid", 0):
            self.state["container_rowid"] = max_c
            self._state_dirty = True

        events.sort(key=lambda e: (e[0], e[1]))
        return [e[2] for e in events]

    # ---------- tasks ----------
    @tasks.loop(seconds=30)
    async def chest_task(self):
        if not self.cfg.get("chest_channel_id"):
            return
        try:
            lines = await asyncio.to_thread(self.fetch_new_chest_events, 200)
            if self._state_dirty:
                self.save_state()
            if not lines:
                return
            ch = await self.resolve_channel(self.cfg.get("chest_channel_id"), "_chest_channel")
            if ch is None:
                return
            buf = ""
            for line in lines:
                candidate = (buf + "\n" + line) if buf else line
                if len(candidate) > 1900:
                    if buf:
                        await ch.send(buf)
                    if len(line) > 1900:
                        for part in chunk_text(line, 1900):
                            await ch.send(part)
                        buf = ""
                    else:
                        buf = line
                else:
                    buf = candidate
            if buf:
                await ch.send(buf)
        except Exception as e:
            print("chest_task error:", e, file=sys.stderr)

    @chest_task.before_loop
    async def before_chest(self):
        await self.wait_until_ready()
        self.init_chest_state_if_needed()
        self.chest_task.change_interval(seconds=max(3, int(self.cfg.get("chest_poll_seconds", 5) or 5)))

    @tasks.loop(minutes=30)
    async def storage_alert_task(self):
        if not self.cfg.get("alert_channel_id"):
            return
        try:
            target = self.cfg.get("server_dir") or "/home/naze/minecraft-public"
            usage = shutil.disk_usage(target)
            pct = (usage.used / usage.total * 100) if usage.total else 0
            warn = float(self.cfg.get("storage_warn_percent", 90) or 90)
            if pct >= warn:
                now = time.time()
                if now - self._last_storage_alert > 3600:
                    self._last_storage_alert = now
                    ch = await self.resolve_channel(self.cfg.get("alert_channel_id"), "_alert_channel")
                    if ch:
                        e = discord.Embed(
                            title="⚠️ Storage Warning",
                            description=f"`{target}` is **{pct:.1f}%** full.\nUsed: **{human_bytes(usage.used)}** / **{human_bytes(usage.total)}** (free {human_bytes(usage.free)})\nThreshold: {warn:.0f}%",
                            color=discord.Color.orange(),
                            timestamp=datetime.now(timezone.utc),
                        )
                        self.set_embed_footer(e, extra="Use !storage for details")
                        await ch.send(embed=e)
        except Exception as e:
            print("storage_alert_task error:", e, file=sys.stderr)

    @storage_alert_task.before_loop
    async def before_storage(self):
        await self.wait_until_ready()
        self.storage_alert_task.change_interval(minutes=max(5, int(self.cfg.get("storage_check_minutes", 30) or 30)))

    async def setup_hook(self):
        self.chest_task.start()
        self.storage_alert_task.start()

    # ---------- commands ----------
    def add_commands(self):
        bot = self
        p = self.cfg.get("command_prefix", "!")

        @bot.command(name="help", aliases=["commands", "h"])
        async def help_cmd(ctx, *, topic: str = ""):
            topic = (topic or "").strip().lower().lstrip(p)
            cmds = [
                ("ping", "Show bot latency and a quick storage check.", f"{p}ping", False),
                ("status / server", "Server service state, disk/storage, and online players.", f"{p}status", False),
                ("players / list / online", "List online players (RCON) with storage check.", f"{p}players", False),
                ("storage / disk / df / storagecheck", "Detailed disk and per-path storage check.", f"{p}storage", False),
                ("chestrecent / chestlog / chests", "Show recent container transactions with storage check.", f"{p}chestrecent [n]", False),
                ("chestplayer / chestwho / audit", "Show recent container transactions for a player.", f"{p}chestplayer <player> [n]", False),
                ("inv <player> [item]", "Check a specific player's inventory (optional item filter).", f"{p}inv <player> [item]", False),
                ("inv all [item]", "Check all registered players' inventories (optional item filter).", f"{p}inv all [item]", False),
                ("inv list", "List players with saved inventory data.", f"{p}inv list", False),
                ("help / commands / h", "Show all commands and help details.", f"{p}help [command]", False),
                ("mc / rcon / console / cmd", "Run a Minecraft server command via RCON (admin-only).", f"{p}mc <command>", True),
            ]
            detail = {
                "ping": ("ping", "Shows gateway/WebSocket latency. Includes a storage check in the response.", f"{p}ping", "—", False),
                "status": ("status", "Service active state, disk/storage summary, and online players. Includes storage check.", f"{p}status", "server", False),
                "server": ("status", "Service active state, disk/storage summary, and online players. Includes storage check.", f"{p}status", "server", False),
                "players": ("players", "Runs RCON `list` to show who is online. Includes storage check.", f"{p}players", "list, online", False),
                "list": ("players", "Runs RCON `list` to show who is online. Includes storage check.", f"{p}players", "list, online", False),
                "online": ("players", "Runs RCON `list` to show who is online. Includes storage check.", f"{p}players", "list, online", False),
                "storage": ("storage", "Detailed storage check: filesystem usage and per-path sizes (`du -sb`, cached briefly). A quick storage status is also included in every command response.", f"{p}storage", "disk, df, storagecheck", False),
                "disk": ("storage", "Detailed storage check: filesystem usage and per-path sizes (`du -sb`, cached briefly). A quick storage status is also included in every command response.", f"{p}storage", "disk, df, storagecheck", False),
                "df": ("storage", "Detailed storage check: filesystem usage and per-path sizes (`du -sb`, cached briefly). A quick storage status is also included in every command response.", f"{p}storage", "disk, df, storagecheck", False),
                "storagecheck": ("storage", "Detailed storage check: filesystem usage and per-path sizes (`du -sb`, cached briefly). A quick storage status is also included in every command response.", f"{p}storage", "disk, df, storagecheck", False),
                "chestrecent": ("chestrecent", "Recent CoreProtect container transactions (took/put). Includes storage check.", f"{p}chestrecent [n]", "chestlog, chests", False),
                "chestlog": ("chestrecent", "Recent CoreProtect container transactions (took/put). Includes storage check.", f"{p}chestrecent [n]", "chestlog, chests", False),
                "chests": ("chestrecent", "Recent CoreProtect container transactions (took/put). Includes storage check.", f"{p}chestrecent [n]", "chestlog, chests", False),
                "chestplayer": ("chestplayer", "Recent container transactions for a specific player (also tries Bedrock `.` name). Includes storage check.", f"{p}chestplayer <player> [n]", "chestwho, audit", False),
                "chestwho": ("chestplayer", "Recent container transactions for a specific player (also tries Bedrock `.` name). Includes storage check.", f"{p}chestplayer <player> [n]", "chestwho, audit", False),
                "audit": ("chestplayer", "Recent container transactions for a specific player (also tries Bedrock `.` name). Includes storage check.", f"{p}chestplayer <player> [n]", "chestwho, audit", False),
                "inv": ("inv", "Check player inventories from saved playerdata (runs `save-all` best-effort for fresher data). Includes storage check.", f"{p}inv <player> [item] | {p}inv all [item] | {p}inv list", "inventory, invcheck", False),
                "inventory": ("inv", "Check player inventories from saved playerdata (runs `save-all` best-effort for fresher data). Includes storage check.", f"{p}inv <player> [item] | {p}inv all [item] | {p}inv list", "inventory, invcheck", False),
                "invcheck": ("inv", "Check player inventories from saved playerdata (runs `save-all` best-effort for fresher data). Includes storage check.", f"{p}inv <player> [item] | {p}inv all [item] | {p}inv list", "inventory, invcheck", False),
                "invall": ("inv all", "Check all registered players' inventories (optional item filter like `diamond`).", f"{p}inv all [item]", "—", False),
                "invlist": ("inv list", "List players with saved inventory data.", f"{p}inv list", "—", False),
                "mc": ("mc", "Executes a Minecraft command via RCON and returns output. **Admin only.** Includes storage check.", f"{p}mc <command>", "rcon, console, cmd", True),
                "rcon": ("mc", "Executes a Minecraft command via RCON and returns output. **Admin only.** Includes storage check.", f"{p}mc <command>", "rcon, console, cmd", True),
                "console": ("mc", "Executes a Minecraft command via RCON and returns output. **Admin only.** Includes storage check.", f"{p}mc <command>", "rcon, console, cmd", True),
                "cmd": ("mc", "Executes a Minecraft command via RCON and returns output. **Admin only.** Includes storage check.", f"{p}mc <command>", "rcon, console, cmd", True),
                "help": ("help", "Shows all commands or details for one command.", f"{p}help [command]", "commands, h", False),
                "commands": ("help", "Shows all commands or details for one command.", f"{p}help [command]", "commands, h", False),
                "h": ("help", "Shows all commands or details for one command.", f"{p}help [command]", "commands, h", False),
            }
            if topic and topic in detail:
                name, desc, usage, aliases, admin = detail[topic]
                e = discord.Embed(title=f"Command: {name}", description=desc, color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
                e.add_field(name="Usage", value=f"`{usage}`", inline=False)
                e.add_field(name="Aliases", value=f"`{aliases}`", inline=True)
                e.add_field(name="Access", value="🔒 Admin only" if admin else "Everyone", inline=True)
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return

            e = discord.Embed(
                title="Minecraft Server Bot — Commands",
                description=(
                    f"Prefix: `{p}`  •  Use `{p}help <command>` for details.\n"
                    f"**Storage check:** a quick storage/disk status is included in every command response. "
                    f"Use `{p}storage` for a detailed per-path check."
                ),
                color=discord.Color.blurple(),
                timestamp=datetime.now(timezone.utc),
            )
            e.add_field(name="📊 Monitoring & Info", value="\n".join([
                f"`{p}ping` — Bot latency (+ storage).",
                f"`{p}status` — Service state, storage/disk, and online players.",
                f"`{p}players` — Online players via RCON (+ storage).",
                f"`{p}storage` — Detailed disk and per-path storage check.",
            ]), inline=False)
            e.add_field(name="📦 Chest Audit (CoreProtect)", value="\n".join([
                f"`{p}chestrecent [n]` — Recent container transactions.",
                f"`{p}chestplayer <player> [n]` — Recent transactions for a player.",
            ]), inline=False)
            e.add_field(name="🎒 Player Inventory Check", value="\n".join([
                f"`{p}inv <player> [item]` — Check a specific player's current (saved) inventory.",
                f"`{p}inv all [item]` — Check all registered players' inventories.",
                f"`{p}inv list` — List players with saved inventory data.",
                f"(aliases: `{p}inventory`, `{p}invcheck`; optional `[item]` filter, e.g. `diamond`)",
            ]), inline=False)
            e.add_field(name="ℹ️ Help", value=f"`{p}help [command]` — Show all commands or details for one.", inline=False)
            e.add_field(name="🔒 Admin / Console", value=f"`{p}mc <command>` — Run a Minecraft server command via RCON.", inline=False)
            ch_st = "on" if bot.cfg.get("chest_channel_id") else "off"
            al_st = "on" if bot.cfg.get("alert_channel_id") else "off"
            bot.set_embed_footer(e, extra=f"Live chest feed: {ch_st} • Storage alerts: {al_st} • Service: {bot.cfg.get('minecraft_service','minecraft-public')}")
            await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="ping")
        async def ping(ctx):
            ms = round(bot.latency * 1000)
            color = discord.Color.green() if ms < 200 else (discord.Color.gold() if ms < 500 else discord.Color.red())
            e = discord.Embed(title="🏓 Pong", description=f"Gateway latency: **{ms} ms**", color=color, timestamp=datetime.now(timezone.utc))
            bot.set_embed_footer(e)
            await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="status", aliases=["server"])
        async def status(ctx):
            async with ctx.typing():
                svc = bot.cfg.get("minecraft_service", "minecraft-public")
                target = bot.cfg.get("server_dir") or "/home/naze/minecraft-public"
                (rc_svc, svc_out), (rc_list, list_out), (pct, disk_text) = await asyncio.gather(
                    bot.run_shell(["systemctl", "is-active", svc]),
                    bot.rcon("list"),
                    asyncio.to_thread(disk_summary_text, target),
                )
                state = (svc_out.splitlines()[0] if svc_out else "unknown").strip() or "unknown"
                players_txt = list_out if rc_list == 0 else "(RCON unavailable)"
                is_up = state == "active"
                color = discord.Color.green() if is_up else discord.Color.red()
                e = discord.Embed(title="🖥️ Server Status", color=color, timestamp=datetime.now(timezone.utc))
                e.add_field(name="Service", value=f"`{svc}`: **{state}**", inline=True)
                e.add_field(name="Bot Latency", value=f"`{round(bot.latency*1000)} ms`", inline=True)
                e.add_field(name="Storage (Disk)", value=disk_text, inline=False)
                pdisp = players_txt.strip() or "(no output)"
                if len(pdisp) > 900:
                    pdisp = pdisp[:900] + "\n..."
                e.add_field(name="Players", value=f"```{pdisp}```", inline=False)
                ch_st = "configured" if bot.cfg.get("chest_channel_id") else "off"
                bot.set_embed_footer(e, extra=f"Live chest feed: {ch_st} • state rows: c={bot.state.get('container_rowid',0)} o={bot.state.get('open_rowid',0)}")
            await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="players", aliases=["list", "online"])
        async def players(ctx):
            async with ctx.typing():
                rc, out = await bot.rcon("list")
            if rc != 0:
                e = discord.Embed(title="Players", description="Failed to query server.", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
                e.add_field(name="RCON error", value=f"```{(out or 'unknown')[:1000]}```", inline=False)
            else:
                body = (out or "(no output)").strip()
                e = discord.Embed(title="👥 Online Players", description=f"```{body[:1800]}```", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
            bot.set_embed_footer(e)
            await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="storage", aliases=["disk", "df", "storagecheck"])
        async def storage(ctx):
            async with ctx.typing():
                report = await asyncio.to_thread(get_storage_report_cached, bot.cfg.get("server_dir"), bot.cfg.get("storage_paths") or [])
            parts = chunk_text(report, 1000)
            color = discord.Color.blue()
            try:
                first = report.splitlines()[0] if report.splitlines() else ""
                if "%" in first and "(" in first:
                    pctv = float(first.split("(")[-1].split("%")[0])
                    warn = float(bot.cfg.get("storage_warn_percent", 90) or 90)
                    color = discord.Color.red() if pctv >= warn else (discord.Color.gold() if pctv >= warn - 10 else discord.Color.green())
            except Exception:
                pass
            total = len(parts)
            for i, part in enumerate(parts, 1):
                title = "💾 Storage Check" if total == 1 else f"💾 Storage Check ({i}/{total})"
                e = discord.Embed(title=title, description=f"```\n{part}\n```", color=color, timestamp=datetime.now(timezone.utc))
                bot.set_embed_footer(e, extra="Quick storage status is included in all commands")
                if i == 1:
                    await ctx.reply(embed=e, mention_author=False)
                else:
                    await ctx.send(embed=e)

        @bot.command(name="mc", aliases=["rcon", "console", "cmd"])
        async def mc(ctx, *, command: str = ""):
            if not await bot.ensure_admin(ctx):
                return
            command = (command or "").strip()
            if not command:
                e = discord.Embed(title="Usage", description=f"`{p}mc <minecraft command>`\nExamples: `{p}mc list`, `{p}mc say Hello`, `{p}mc save-all`", color=discord.Color.blurple())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return
            async with ctx.typing():
                rc, out = await bot.rcon(command)
            body = (out or "(no output)").strip()
            if len(body) > 1500:
                body = body[:1500] + "\n... (truncated)"
            ok = rc == 0
            e = discord.Embed(
                title=("✅ Command executed" if ok else "⚠️ Command result"),
                color=(discord.Color.green() if ok else discord.Color.orange()),
                timestamp=datetime.now(timezone.utc),
            )
            e.add_field(name="Command", value=f"`{command[:200]}`", inline=False)
            e.add_field(name="Return code", value=f"`{rc}`", inline=True)
            e.add_field(name="Output", value=f"```{body}```", inline=False)
            bot.set_embed_footer(e, extra=f"By {ctx.author}")
            await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="chestrecent", aliases=["chestlog", "chests"])
        async def chestrecent(ctx, limit: int = 10):
            try:
                limit = int(limit)
            except Exception:
                limit = 10
            limit = max(1, min(limit, 30))
            db = bot.cfg.get("coreprotect_db")
            if not db or not os.path.exists(db):
                e = discord.Embed(title="Chest Audit", description="CoreProtect database not found.", color=discord.Color.red())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return

            def _q():
                con = bot.db_conn()
                cur = con.cursor()
                cur.execute('''
                    select c.time,u.user as player,m.material,c.amount,c.action,c.x,c.y,c.z,w.world
                    from co_container c
                    left join co_user u on c.user=u.id
                    left join co_material_map m on c.type=m.id
                    left join co_world w on c.wid=w.id
                    order by c.rowid desc limit ?
                ''', (limit,))
                rows = [dict(r) for r in cur.fetchall()]
                con.close()
                return rows

            try:
                async with ctx.typing():
                    rows = await asyncio.to_thread(_q)
                if not rows:
                    e = discord.Embed(title="📦 Recent Container Transactions", description="No container transactions found.", color=discord.Color.blurple())
                    bot.set_embed_footer(e)
                    await ctx.reply(embed=e, mention_author=False)
                    return
                lines = []
                for r in rows:
                    verb = "took" if int(r['action']) == 0 else "put"
                    icon = "🔻" if int(r['action']) == 0 else "🔺"
                    lines.append(f"{icon} `{ts_fmt(r['time'])}` **{r['player']}** {verb} `{r['amount']}x {short_mat(r['material'])}` @ `{r['world']} {r['x']},{r['y']},{r['z']}`")
                desc = "\n".join(lines)
                for i, part in enumerate(chunk_text(desc, 3800), 1):
                    e = discord.Embed(title=("📦 Recent Container Transactions" if i == 1 else f"📦 Recent Container Transactions ({i})"),
                                      description=part, color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
                    bot.set_embed_footer(e, extra=f"Showing {len(rows)} most recent • source: CoreProtect")
                    if i == 1:
                        await ctx.reply(embed=e, mention_author=False)
                    else:
                        await ctx.send(embed=e)
            except Exception as ex:
                e = discord.Embed(title="Error", description=f"`{ex}`", color=discord.Color.red())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="chestplayer", aliases=["chestwho", "audit"])
        async def chestplayer(ctx, player: str = "", limit: int = 15):
            player = (player or "").strip()
            if not player:
                e = discord.Embed(title="Usage", description=f"`{p}chestplayer <player> [limit]`", color=discord.Color.blurple())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return
            try:
                limit = int(limit)
            except Exception:
                limit = 15
            limit = max(1, min(limit, 30))
            db = bot.cfg.get("coreprotect_db")
            if not db or not os.path.exists(db):
                e = discord.Embed(title="Chest Audit", description="CoreProtect database not found.", color=discord.Color.red())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return
            alt = '.' + player.lstrip('.')

            def _q():
                con = bot.db_conn()
                cur = con.cursor()
                cur.execute('''
                    select c.time,u.user as player,m.material,c.amount,c.action,c.x,c.y,c.z,w.world
                    from co_container c
                    left join co_user u on c.user=u.id
                    left join co_material_map m on c.type=m.id
                    left join co_world w on c.wid=w.id
                    where lower(u.user)=lower(?) or lower(u.user)=lower(?)
                    order by c.rowid desc limit ?
                ''', (player, alt, limit))
                rows = [dict(r) for r in cur.fetchall()]
                con.close()
                return rows

            try:
                async with ctx.typing():
                    rows = await asyncio.to_thread(_q)
                if not rows:
                    e = discord.Embed(title="📦 Player Container Audit", description=f"No container transactions found for `{player}`.", color=discord.Color.blurple())
                    bot.set_embed_footer(e)
                    await ctx.reply(embed=e, mention_author=False)
                    return
                pname = rows[0].get('player') or player
                lines = []
                for r in rows:
                    verb = "took" if int(r['action']) == 0 else "put"
                    icon = "🔻" if int(r['action']) == 0 else "🔺"
                    lines.append(f"{icon} `{ts_fmt(r['time'])}` {verb} `{r['amount']}x {short_mat(r['material'])}` @ `{r['world']} {r['x']},{r['y']},{r['z']}`")
                desc = "\n".join(lines)
                for i, part in enumerate(chunk_text(desc, 3800), 1):
                    e = discord.Embed(title=("📦 Player Container Audit" if i == 1 else f"📦 Player Container Audit ({i})"),
                                      description=f"**Player:** `{pname}`\n\n{part}", color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
                    bot.set_embed_footer(e, extra=f"Showing {len(rows)} most recent • source: CoreProtect")
                    if i == 1:
                        await ctx.reply(embed=e, mention_author=False)
                    else:
                        await ctx.send(embed=e)
            except Exception as ex:
                e = discord.Embed(title="Error", description=f"`{ex}`", color=discord.Color.red())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)

        @bot.command(name="inv", aliases=["inventory", "invcheck"])
        async def inv(ctx, target: str = "", *, rest: str = ""):
            if invcheck is None:
                e = discord.Embed(title="Inventory Check", description="Inventory check module is unavailable on the server.", color=discord.Color.red())
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return

            t = (target or "").strip()
            rest = (rest or "").strip()
            if not t:
                e = discord.Embed(
                    title="🎒 Inventory Check — Usage",
                    description=(
                        f"`{p}inv <player> [item]` — check a specific player's inventory\n"
                        f"`{p}inv all [item]` — check all registered players' inventories\n"
                        f"`{p}inv list` — list players with saved inventory data\n\n"
                        f"Examples: `{p}inv .Neysha014`, `{p}inv arkana01 diamond`, `{p}inv all diamond`\n"
                        f"Note: reads saved playerdata (best-effort `save-all` is run first for fresher online data)."
                    ),
                    color=discord.Color.blurple(),
                )
                bot.set_embed_footer(e)
                await ctx.reply(embed=e, mention_author=False)
                return

            async with ctx.typing():
                # best-effort save for fresher data
                try:
                    await bot.rcon("save-all")
                except Exception:
                    pass

                if t.lower() == "list":
                    def _list():
                        players = invcheck.list_registered_players()
                        cache = invcheck.load_usercache()
                        return players, cache
                    try:
                        players, cache = await asyncio.to_thread(_list)
                        lines = []
                        if players:
                            lines.append(f"Registered players with saved data ({len(players)}):")
                            for pl in players:
                                lines.append(f"- {pl['name']}  ({pl['uuid']})")
                        else:
                            lines.append("No playerdata files found.")
                        known_only = []
                        try:
                            pdata_uuids = {pl['uuid'].lower() for pl in players}
                            for e in cache:
                                u = (e.get('uuid') or '').lower()
                                n = e.get('name')
                                if u and u not in pdata_uuids and n:
                                    known_only.append(f"- {n}  ({e.get('uuid')})")
                        except Exception:
                            pass
                        if known_only:
                            lines.append("")
                            lines.append("Known (no saved playerdata):")
                            lines.extend(known_only)
                        text = "\n".join(lines)
                        parts = chunk_text(text, 3900)
                        for i, part in enumerate(parts, 1):
                            title = "🎒 Inventory Players" if len(parts) == 1 else f"🎒 Inventory Players ({i}/{len(parts)})"
                            e = discord.Embed(title=title, description=f"```\n{part}\n```", color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
                            bot.set_embed_footer(e, extra="Use !inv <player> or !inv all [item]")
                            if i == 1:
                                await ctx.reply(embed=e, mention_author=False)
                            else:
                                await ctx.send(embed=e)
                    except Exception as ex:
                        e = discord.Embed(title="Inventory Check", description=f"Failed to list players: `{ex}`", color=discord.Color.red())
                        bot.set_embed_footer(e)
                        await ctx.reply(embed=e, mention_author=False)
                    return

                if t.lower() == "all":
                    filt = rest or None

                    def _all():
                        players = invcheck.list_registered_players()
                        results = [invcheck.analyze_player(pl["name"], pl["uuid"], only=filt) for pl in players]
                        report = invcheck.format_all_report(results, only=filt, saved_note=False)
                        return players, results, report

                    try:
                        players, results, report = await asyncio.to_thread(_all)
                        if not players:
                            e = discord.Embed(title="🎒 All Player Inventories", description="No playerdata files found.", color=discord.Color.orange())
                            bot.set_embed_footer(e)
                            await ctx.reply(embed=e, mention_author=False)
                            return
                        header_extra = f"Players: {len(players)}" + (f" • filter: {filt}" if filt else "")
                        parts = chunk_text(report, 3900)
                        for i, part in enumerate(parts, 1):
                            title = "🎒 All Player Inventories" if len(parts) == 1 else f"🎒 All Player Inventories ({i}/{len(parts)})"
                            e = discord.Embed(title=title, description=f"```\n{part}\n```", color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
                            bot.set_embed_footer(e, extra=header_extra)
                            if i == 1:
                                await ctx.reply(embed=e, mention_author=False)
                            else:
                                await ctx.send(embed=e)
                    except Exception as ex:
                        e = discord.Embed(title="Inventory Check", description=f"Failed to check inventories: `{ex}`", color=discord.Color.red())
                        bot.set_embed_footer(e)
                        await ctx.reply(embed=e, mention_author=False)
                    return

                # specific player
                query = t
                filt = rest or None

                def _one():
                    matches = invcheck.find_players(query)
                    if not matches:
                        return None, None, matches
                    exact = [m for m in matches if m[2].endswith("exact") or m[2] == "direct"]
                    chosen = exact[0] if len(exact) == 1 else (matches[0] if len(matches) == 1 else None)
                    if chosen is None:
                        return None, None, matches
                    name, uuid, _src = chosen
                    r = invcheck.analyze_player(name, uuid, only=filt)
                    return chosen, r, matches

                try:
                    chosen, r, matches = await asyncio.to_thread(_one)
                    if not matches:
                        e = discord.Embed(title="🎒 Inventory Check", description=f"No player found matching `{query}`. Try `{p}inv list`.", color=discord.Color.orange())
                        bot.set_embed_footer(e)
                        await ctx.reply(embed=e, mention_author=False)
                        return
                    if chosen is None:
                        opts = "\n".join([f"- {m[0]} ({m[1]})" for m in matches[:15]])
                        e = discord.Embed(title="🎒 Inventory Check", description=f"Multiple players match `{query}`. Be more specific:\n```\n{opts}\n```", color=discord.Color.orange())
                        bot.set_embed_footer(e)
                        await ctx.reply(embed=e, mention_author=False)
                        return
                    name, uuid, _src = chosen
                    if r.get("error") == "not_found":
                        e = discord.Embed(title="🎒 Inventory Check", description=f"Playerdata file not found for **{name}** (`{uuid}`).", color=discord.Color.red())
                        bot.set_embed_footer(e)
                        await ctx.reply(embed=e, mention_author=False)
                        return
                    if r.get("error"):
                        e = discord.Embed(title="🎒 Inventory Check", description=f"Failed to read data for **{name}** (`{uuid}`): `{r['error']}`", color=discord.Color.red())
                        bot.set_embed_footer(e)
                        await ctx.reply(embed=e, mention_author=False)
                        return

                    lines = invcheck.format_player_block(r, only=filt, readable=True)
                    text = "\n".join(lines)
                    note = "Saved playerdata • save-all requested for fresher online data"
                    if filt:
                        note += f" • filter: {filt}"
                    parts = chunk_text(text, 3900)
                    for i, part in enumerate(parts, 1):
                        title = f"🎒 Inventory: {name}" if len(parts) == 1 else f"🎒 Inventory: {name} ({i}/{len(parts)})"
                        e = discord.Embed(title=title, description=f"```\n{part}\n```", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                        bot.set_embed_footer(e, extra=note)
                        if i == 1:
                            await ctx.reply(embed=e, mention_author=False)
                        else:
                            await ctx.send(embed=e)
                except Exception as ex:
                    e = discord.Embed(title="Inventory Check", description=f"Failed to check inventory: `{ex}`", color=discord.Color.red())
                    bot.set_embed_footer(e)
                    await ctx.reply(embed=e, mention_author=False)

    async def on_ready(self):
        print(f"Logged in as {self.user} (id={self.user.id})")
        print(f"Guilds: {[g.name for g in self.guilds]}")

    async def on_command_error(self, ctx, error):
        p = self.cfg.get('command_prefix', '!')
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            e = discord.Embed(title="Missing argument", description=f"Missing: `{error.param.name}`\nUse `{p}help` for usage.", color=discord.Color.orange())
            self.set_embed_footer(e)
            await ctx.reply(embed=e, mention_author=False)
            return
        if isinstance(error, commands.BadArgument):
            e = discord.Embed(title="Bad argument", description=f"{error}\nUse `{p}help` for usage.", color=discord.Color.orange())
            self.set_embed_footer(e)
            await ctx.reply(embed=e, mention_author=False)
            return
        if isinstance(error, commands.CommandOnCooldown):
            e = discord.Embed(title="Cooldown", description=f"Try again in {error.retry_after:.1f}s", color=discord.Color.orange())
            self.set_embed_footer(e)
            await ctx.reply(embed=e, mention_author=False)
            return
        orig = getattr(error, 'original', error)
        print("Command error:", repr(orig), file=sys.stderr)
        traceback.print_exception(type(orig), orig, orig.__traceback__, file=sys.stderr)
        try:
            e = discord.Embed(title="Error", description=f"`{type(orig).__name__}: {str(orig)[:500]}`", color=discord.Color.red())
            self.set_embed_footer(e)
            await ctx.reply(embed=e, mention_author=False)
        except Exception:
            pass


def main():
    cfg = load_config()
    token = (cfg.get("token") or "").strip()
    if not token or token == "PUT_YOUR_DISCORD_BOT_TOKEN_HERE":
        raise SystemExit("Bot token not set. Edit discord-bot/config.json and set 'token'.")
    bot = MonitorBot(cfg)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
