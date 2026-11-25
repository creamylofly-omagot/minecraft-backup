#!/usr/bin/env python3
import os, pty, select, subprocess, time, re, urllib.request, urllib.parse, signal, sys, datetime

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
NAME = "nazesshx"
LOG = "/home/naze/minecraft-public/logs/sshx-watchdog.log"
LINK_RE = re.compile(r"https://sshx\.io/s/\S+")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

child = None


def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def send_telegram(text):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
        log("telegram: sent")
        return True
    except Exception as e:
        log(f"telegram: failed: {e}")
        return False


def child_cpu_seconds(pid):
    """CPU time (user+system) already used by a live child, from /proc (Linux)."""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            fields = f.read().rsplit(") ", 1)[1].split()
        ticks = int(fields[11]) + int(fields[12])  # utime, stime (fields 14 and 15)
        return ticks / os.sysconf("SC_CLK_TCK")
    except Exception:
        return None


def kill_child():
    global child
    if not child:
        return
    try:
        child.terminate()
    except Exception:
        pass
    try:
        child.wait(timeout=5)
    except Exception:
        try:
            child.kill()
        except Exception:
            pass
        try:
            child.wait(timeout=5)
        except Exception:
            pass
    child = None


def handle_signal(signum, frame):
    log(f"signal {signum}, exiting")
    kill_child()
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def run_once():
    global child
    master, slave = pty.openpty()
    env = os.environ.copy()
    env.setdefault("TERM", "xterm-256color")
    child = subprocess.Popen(
        ["sshx", "--name", NAME],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        env=env,
    )
    os.close(slave)
    log(f"started sshx pid={child.pid}")

    buf = b""
    link_sent = None
    dead = False
    started = time.time()
    cpu_check_at = started
    cpu_at_check = child_cpu_seconds(child.pid) or 0.0

    try:
        while True:
            if child.poll() is not None:
                log(f"sshx exited rc={child.returncode}")
                break

            now = time.time()
            # An alive-but-spinning sshx used to be invisible to this watchdog.
            if now - cpu_check_at >= 15:
                cpu = child_cpu_seconds(child.pid)
                if cpu is not None:
                    used, elapsed = cpu - cpu_at_check, now - cpu_check_at
                    if now - started > 120 and used > elapsed * 0.7:
                        log(f"sshx pid={child.pid} burned {used:.1f}s CPU in {elapsed:.1f}s wall, restarting")
                        dead = True
                        break
                    cpu_at_check, cpu_check_at = cpu, now
            if link_sent is None and now - started > 90:
                log("no sshx link after 90s, restarting")
                dead = True
                break

            r, _, _ = select.select([master], [], [], 1.0)
            if master in r:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    chunk = b""
                if not chunk:
                    if child.poll() is not None:
                        log(f"sshx exited rc={child.returncode}")
                        break
                    continue
                buf += chunk
                while b"\n" in buf or b"\r" in buf:
                    # split on either \n or \r
                    idx_n = buf.find(b"\n")
                    idx_r = buf.find(b"\r")
                    idxs = [i for i in [idx_n, idx_r] if i != -1]
                    idx = min(idxs)
                    line_b = buf[:idx]
                    buf = buf[idx + 1 :]
                    # sshx colours its output; keep escape codes out of the link and the log.
                    line = ANSI_RE.sub("", line_b.decode("utf-8", errors="replace")).strip()
                    if not line:
                        continue
                    log(f"sshx: {line}")

                    m = LINK_RE.search(line)
                    if m:
                        link = m.group(0).rstrip(".,)>\"'")
                        if link != link_sent:
                            link_sent = link
                            send_telegram(f"sshx link ({NAME}): {link}")

                    low = line.lower()
                    if "session not found" in low:
                        log("detected dead session, restarting sshx")
                        dead = True
                        break
                if dead:
                    break

            # if no output for a long time, just keep waiting; sshx is quiet when healthy
    finally:
        try:
            os.close(master)
        except Exception:
            pass
        kill_child()

    return dead


def main():
    log("sshx watchdog starting")
    send_telegram(f"sshx watchdog started on {os.uname().nodename} ({NAME})")
    backoff = 3
    while True:
        try:
            dead = run_once()
        except Exception as e:
            log(f"watchdog error: {e}")
            dead = True
        if dead:
            delay = backoff
        else:
            delay = 5
        log(f"restarting sshx in {delay}s")
        time.sleep(delay)
        backoff = min(backoff * 2, 30) if dead else 3


if __name__ == "__main__":
    main()
