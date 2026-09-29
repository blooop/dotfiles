#!/usr/bin/env python3
"""Log herdr focus and agent-status events to a daily JSONL file.

The usage-review skill reads this for the timing metrics the Claude
transcripts cannot give: how long an agent sits blocked or idle before you
look at it, how many agents work at once, how often focus moves.

Two socket connections, because herdr resets a connection that sends a second
`events.subscribe` after the first one started:

  - `global`: focus, pane lifecycle and agent detection. Stays up.
  - `status`: `pane.agent_status_changed`, which herdr only offers per pane.
    Rebuilt with the current pane list whenever a pane appears, closes or
    becomes an agent. The new one opens before the old one closes, so no
    change is missed; the duplicates that overlap causes are dropped by only
    logging a status that differs from the last one seen for that pane.

Each (re)build also logs a `panes` snapshot, which carries the pane -> Claude
session_id mapping (`agent_session.value`) that joins this log to
~/.claude/telemetry/claude-*.jsonl.

Started by the plugin's [[startup]] hook on every server start and handoff; a
flock keeps it to one logger. It never writes to herdr, only subscribes and
lists. It exits after ten minutes with no connection, and the next
server start brings it back.
"""

import fcntl
import json
import os
import select
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

SOCK = os.environ.get("HERDR_SOCKET_PATH") or os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "herdr", "herdr.sock"
)
OUT = os.environ.get("CLAUDE_TELEMETRY_DIR") or os.path.expanduser("~/.claude/telemetry")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "herdr-telemetry")
GIVE_UP_S = 600
last_connect = time.monotonic()

GLOBAL = [
    "pane.focused", "tab.focused", "workspace.focused",
    "pane.created", "pane.closed", "pane.exited", "pane.agent_detected",
    "tab.created", "tab.closed", "workspace.created", "workspace.closed",
]
REBUILD_ON = {"pane_created", "pane_closed", "pane_exited", "pane_agent_detected"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def emit(rec):
    rec = {"ts": now(), **rec}
    path = os.path.join(OUT, f"herdr-{rec['ts'][:10]}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")


def subscribe(subs, tag):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(SOCK)
    req = {"id": f"telemetry-{tag}", "method": "events.subscribe", "params": {"subscriptions": subs}}
    s.sendall((json.dumps(req) + "\n").encode())
    f = s.makefile("rb")
    ack = json.loads(f.readline() or b"{}")
    if ack.get("result", {}).get("type") != "subscription_started":
        s.close()
        raise ConnectionError(f"{tag}: {ack}")
    s.settimeout(None)
    return s, f


def panes():
    out = subprocess.run(["herdr", "pane", "list"], capture_output=True, text=True, timeout=10).stdout
    return json.loads(out)["result"]["panes"]


def snapshot(last_status):
    ps = panes()
    keep = ("pane_id", "tab_id", "workspace_id", "agent", "agent_status", "cwd", "focused")
    rows = []
    for p in ps:
        row = {k: p.get(k) for k in keep}
        row["session"] = (p.get("agent_session") or {}).get("value")
        rows.append(row)
        if p.get("agent_status"):
            last_status.setdefault(p["pane_id"], p["agent_status"])
    emit({"ev": "panes", "data": rows})
    return [p["pane_id"] for p in ps]


def run():
    last_status = {}
    global last_connect
    g, gf = subscribe([{"type": t} for t in GLOBAL], "global")
    last_connect = time.monotonic()
    emit({"ev": "logger_connected", "data": {"version": herdr_version(), "protocol": protocol()}})
    st = stf = None
    rebuild = True
    try:
        while True:
            if rebuild:
                ids = snapshot(last_status)
                new = subscribe([{"type": "pane.agent_status_changed", "pane_id": i} for i in ids], "status") if ids else None
                if st:
                    st.close()
                st, stf = new if new else (None, None)
                rebuild = False
            files = [gf] + ([stf] if stf else [])
            ready, _, _ = select.select(files, [], [], 3600)
            if not ready:
                rebuild = True  # hourly snapshot keeps the session mapping fresh
                continue
            for f in ready:
                line = f.readline()
                if not line:
                    if f is gf:
                        raise ConnectionError("global stream closed")
                    st = stf = None
                    rebuild = True
                    continue
                msg = json.loads(line)
                # herdr sends pane_focused but pane.agent_status_changed; one spelling
                # keeps the log and its readers simple.
                ev, data = (msg.get("event") or "").replace(".", "_"), msg.get("data") or {}
                if ev == "pane_agent_status_changed":
                    pid, status = data.get("pane_id"), data.get("agent_status")
                    if last_status.get(pid) == status:
                        continue
                    last_status[pid] = status
                elif ev in REBUILD_ON:
                    rebuild = True
                    if ev in ("pane_closed", "pane_exited"):
                        last_status.pop(data.get("pane_id"), None)
                if ev:
                    emit({"ev": ev, "data": data})
    finally:
        for s in (g, st):
            if s:
                s.close()


def herdr_version():
    try:
        return subprocess.run(["herdr", "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None


def protocol():
    try:
        out = subprocess.run(["herdr", "api", "schema", "--json"], capture_output=True, text=True, timeout=10).stdout
        return json.loads(out).get("protocol")
    except Exception:
        return None


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(STATE, exist_ok=True)
    lock = open(os.path.join(STATE, "lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0  # another logger has it; after a handoff it reconnects by itself
    lock.write(str(os.getpid()))
    lock.flush()
    last_error = None
    while True:
        try:
            run()
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:300]
            if err != last_error:  # a dead server would otherwise log this every 5 s
                last_error = err
                try:
                    emit({"ev": "logger_error", "data": {"error": err}})
                except OSError:
                    pass
        if time.monotonic() - last_connect > GIVE_UP_S:
            return 0
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
