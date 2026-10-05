#!/usr/bin/env python3
"""Print one session as a compact timeline: prompts, assistant text, tool calls.

    session_trace.py <session-id-prefix> [--head 40] [--tail 20] [--grep REGEX] [--subagents]
                     [--since ISO] [--until ISO] [--full]

Each line: time, context size of that turn, kind, first ~140 chars. Runs of the
same tool call collapse to one line with a count, so a busy-wait shows as
"ReadNotifications x1099" instead of 1099 lines.

--since/--until keep only events in that window (ISO timestamps; no zone means
UTC) and print times to the second. With --subagents as well, the window covers
every subagent transcript too, merged into one timeline with each line tagged
by its agent -- the way to see what ran, in what order, around an incident.
--full prints each command and message whole instead of cutting it at 140 chars.
"""
import argparse, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path


def when(s):
    t = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)

p = argparse.ArgumentParser()
p.add_argument("id")
p.add_argument("--head", type=int, default=40)
p.add_argument("--tail", type=int, default=20)
p.add_argument("--grep")
p.add_argument("--subagents", action="store_true",
               help="also list this session's subagent transcripts; with --since/--until, trace them too")
p.add_argument("--since", type=when, help="keep events at or after this ISO time")
p.add_argument("--until", type=when, help="keep events at or before this ISO time")
p.add_argument("--full", action="store_true", help="do not truncate commands or text")
a = p.parse_args()
window = a.since is not None or a.until is not None
root = Path(os.path.expanduser("~/.claude/projects"))
hits = [f for f in root.rglob(a.id + "*.jsonl") if "subagents" not in f.parts] or list(root.rglob(a.id + "*.jsonl"))
if not hits:
    sys.exit(f"no transcript matches {a.id}")
f = hits[0]
print(f"# {f}")



def trace(f, tag=""):
    """Rows of (iso-ts, ctx, kind, text, tag) for one transcript, window-filtered."""
    rows, ctx = [], 0
    for line in f.open(errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        iso, m = d.get("timestamp") or "", d.get("message") or {}
        keep = True
        if window:
            try:
                t = when(iso)
                keep = (a.since is None or t >= a.since) and (a.until is None or t <= a.until)
            except ValueError:
                keep = False
        if d.get("type") == "assistant":
            u = m.get("usage") or {}
            ctx = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) or ctx
            if not keep:
                continue
            for b in m.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b["text"].strip():
                    rows.append((iso, ctx, "SAY", b["text"], tag))
                elif b.get("type") == "tool_use":
                    i = b.get("input") or {}
                    arg = i.get("command") or i.get("file_path") or i.get("description") or i.get("skill") or i.get("prompt") or json.dumps(i)
                    rows.append((iso, ctx, b["name"], str(arg), tag))
        elif keep and d.get("type") == "user" and not d.get("isMeta") and d.get("toolUseResult") is None:
            c = m.get("content")
            t = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")
            if t.strip() and not t.startswith("<local-command"):
                rows.append((iso, ctx, "USER", t, tag))
    return rows


subs = sorted((f.parent / f.stem / "subagents").glob("*.jsonl"))
rows = trace(f)
if window and a.subagents:
    for sub in subs:
        rows += trace(sub, sub.stem.removeprefix("agent-")[:17])
    rows.sort(key=lambda r: r[0])

collapsed = []
for r in rows:
    if (collapsed and collapsed[-1][2] == r[2] and collapsed[-1][5] == r[4] and r[2] not in ("USER", "SAY")
            and collapsed[-1][3][:40] == r[3][:40] and not a.full):
        collapsed[-1][6] += 1
    else:
        collapsed.append([r[0], r[1], r[2], r[3], None, r[4], 1])
if a.grep:
    collapsed = [r for r in collapsed if re.search(a.grep, r[3], re.I) or r[2] == "USER"]

def show(r):
    n = f" x{r[6]}" if r[6] > 1 else ""
    ts = r[0][5:19] if window else r[0][5:16]
    tag = f"[{r[5]}] " if r[5] else ""
    text = r[3].replace(chr(10), chr(10) + " " * 8) if a.full else r[3][:140].replace(chr(10), " ")
    print(f"{ts} {r[1]/1e3:5.0f}k {tag}{r[2][:18]:18s}{n} {text}")

print(f"{len(rows)} events, {len(collapsed)} after collapsing repeats")
if len(collapsed) <= a.head + a.tail:
    for r in collapsed: show(r)
else:
    for r in collapsed[:a.head]: show(r)
    print(f"... {len(collapsed) - a.head - a.tail} lines hidden; use --grep or a larger --head/--tail ...")
    for r in collapsed[-a.tail:]: show(r)
if a.subagents:
    for s in subs:
        print(f"  sub {s.stem}  {s.stat().st_size/1e3:.0f}kB")
