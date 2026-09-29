#!/usr/bin/env python3
"""Print one session as a compact timeline: prompts, assistant text, tool calls.

    session_trace.py <session-id-prefix> [--head 40] [--tail 20] [--grep REGEX] [--subagents]

Each line: time, context size of that turn, kind, first ~140 chars. Runs of the
same tool call collapse to one line with a count, so a busy-wait shows as
"ReadNotifications x1099" instead of 1099 lines.
"""
import argparse, json, os, re, sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("id")
p.add_argument("--head", type=int, default=40)
p.add_argument("--tail", type=int, default=20)
p.add_argument("--grep")
p.add_argument("--subagents", action="store_true", help="also list this session's subagent transcripts")
a = p.parse_args()
root = Path(os.path.expanduser("~/.claude/projects"))
hits = [f for f in root.rglob(a.id + "*.jsonl") if "subagents" not in f.parts] or list(root.rglob(a.id + "*.jsonl"))
if not hits:
    sys.exit(f"no transcript matches {a.id}")
f = hits[0]
print(f"# {f}")

rows, ctx = [], 0
for line in f.open(errors="replace"):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    ts, m = (d.get("timestamp") or "")[5:16], d.get("message") or {}
    if d.get("type") == "assistant":
        u = m.get("usage") or {}
        ctx = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) or ctx
        for b in m.get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b["text"].strip():
                rows.append((ts, ctx, "SAY", b["text"]))
            elif b.get("type") == "tool_use":
                i = b.get("input") or {}
                arg = i.get("command") or i.get("file_path") or i.get("description") or i.get("skill") or i.get("prompt") or json.dumps(i)
                rows.append((ts, ctx, b["name"], str(arg)))
    elif d.get("type") == "user" and not d.get("isMeta") and d.get("toolUseResult") is None:
        c = m.get("content")
        t = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")
        if t.strip() and not t.startswith("<local-command"):
            rows.append((ts, ctx, "USER", t))

collapsed = []
for r in rows:
    if collapsed and collapsed[-1][2] == r[2] and r[2] not in ("USER", "SAY") and collapsed[-1][3][:40] == r[3][:40]:
        collapsed[-1][4] += 1
    else:
        collapsed.append([*r, 1])
if a.grep:
    collapsed = [r for r in collapsed if re.search(a.grep, r[3], re.I) or r[2] == "USER"]

def show(r):
    n = f" x{r[4]}" if r[4] > 1 else ""
    print(f"{r[0]} {r[1]/1e3:5.0f}k {r[2][:18]:18s}{n} {r[3][:140].replace(chr(10), ' ')}")

print(f"{len(rows)} events, {len(collapsed)} after collapsing repeats")
if len(collapsed) <= a.head + a.tail:
    for r in collapsed: show(r)
else:
    for r in collapsed[:a.head]: show(r)
    print(f"... {len(collapsed) - a.head - a.tail} lines hidden; use --grep or a larger --head/--tail ...")
    for r in collapsed[-a.tail:]: show(r)
if a.subagents:
    for s in sorted((f.parent / f.stem / "subagents").glob("*.jsonl")):
        print(f"  sub {s.stem}  {s.stat().st_size/1e3:.0f}kB")
