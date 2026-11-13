#!/usr/bin/env python3
"""Find the sessions that worked on a PR, an issue, a branch or a topic.

    session_find.py <PR or issue number | URL | text> [--days 30] [--top 8]

Prints the best matches, most mentions first: id prefix, first and last activity,
project folder, number of matching lines, and the first prompt. Feed the id to
session_trace.py. A number matches `pull/N`, `issues/N`, `#N` and `gh pr|issue … N`;
a GitHub URL is reduced to its `pull/N` or `issues/N`; other text is matched as it is,
case-insensitive. Only main-session transcripts are searched, not subagents.

It exists so that nobody greps megabytes of .jsonl by hand: five searches in the two
weeks to 2026-11-12 took 2 to 6 raw greps each.
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("what")
p.add_argument("--days", type=int, default=30, help="only transcripts changed in the last N days")
p.add_argument("--top", type=int, default=8)
a = p.parse_args()

what = a.what.strip()
url = re.search(r"github\.com/[^/\s]+/[^/\s]+/(pull|issues)/(\d+)", what)
if url:
    pattern, flags = rf"{url.group(1)}/{url.group(2)}([^0-9]|$)", ["-E"]
elif re.fullmatch(r"#?\d+", what):
    n = what.lstrip("#")
    pattern = rf"(pull|issues)/{n}([^0-9]|$)|#{n}([^0-9]|$)|gh (pr|issue) [a-z-]+ {n}([^0-9]|$)"
    flags = ["-E"]
else:
    pattern, flags = what, ["-F", "-i"]

root = Path(os.path.expanduser("~/.claude/projects"))
cutoff = time.time() - a.days * 86400
files = [f for f in root.rglob("*.jsonl")
         if "subagents" not in f.parts and f.stat().st_mtime >= cutoff]
if not files:
    sys.exit("no transcripts in the window")

counts = {}
for i in range(0, len(files), 200):  # batches keep the argv short
    out = subprocess.run(["grep", "-c", *flags, "-e", pattern, "--", *map(str, files[i:i + 200])],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        path, _, n = line.rpartition(":")
        if n.isdigit() and int(n):
            counts[path] = int(n)
if not counts:
    sys.exit(f"no session mentions {what!r} in the last {a.days} days (try --days 90)")


def first_prompt_and_start(path):
    """The first human prompt of a transcript and its timestamp."""
    with open(path, errors="replace") as fh:
        for n, line in enumerate(fh):
            if n > 400:
                break
            try:
                d = json.loads(line)
            except ValueError:
                continue
            c = (d.get("message") or {}).get("content")
            if d.get("type") != "user" or d.get("isMeta"):
                continue
            if isinstance(c, list):
                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
            if isinstance(c, str) and c.strip() and "<local-command" not in c and "<system-reminder>" not in c[:20]:
                return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()[:110], (d.get("timestamp") or "")[:16]
    return "", ""


print(f"# {len(counts)} sessions mention {what!r}; top {min(a.top, len(counts))} by matching lines")
for path, n in sorted(counts.items(), key=lambda kv: -kv[1])[:a.top]:
    f = Path(path)
    prompt, start = first_prompt_and_start(path)
    last = time.strftime("%Y-%m-%dT%H:%M", time.localtime(f.stat().st_mtime))
    print(f"{f.stem[:8]}  {start or '?':16} -> {last}  {n:5} lines  {f.parent.name[-40:]}")
    print(f"          {prompt}")
