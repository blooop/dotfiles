#!/usr/bin/env python3
"""Summarize Claude Code transcripts under ~/.claude/projects for a time window.

    usage_stats.py [--days 7] [--out DIR]

Prints a compact report on stdout. With --out, also writes:
  DIR/stats.json    aggregates plus per-session rows (for week-over-week diffs)
  DIR/prompts.txt   every short (<200 char) prompt the user typed, one per line,
                    prefixed with the session id — the raw material for friction
"""
import argparse, collections, json, os, re, statistics, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--days", type=float, default=7)
p.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
p.add_argument("--out")
a = p.parse_args()
cutoff = time.time() - a.days * 86400
since_iso = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(cutoff))

C = collections.Counter
IN_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
POLL_RE = re.compile(r"\bsleep\s+\d|\buntil\b|\bwhile\b.*\bsleep\b|--watch\b")
FRICTION = {  # label -> regex over short user prompts; tune as new habits show up
    "nudge: keep going / continue": r"^(keep going|continue\b|go on\b)",
    "status check: did you / have you": r"^(did you|have you|when are you|is it done|what is the status)",
    "retry after user fixed env: try now": r"^(try now|try again|what about now)|\b(i )?(logged in|authed|ran it)\b",
    "ask for plainer prose": r"\b(simple|simpler|simplif|plain|easy to (read|understand|review))",
    "unwanted CI watching": r"(don'?t|no) need to (watch|monitor)",
    "host resources: cpu/ram/crash": r"\b(cpu|ram|memory|restart(ed)?|crash(ed)?|oom)\b",
    "cross-agent handoff": r"(another|other) agent|prompt for (me|an agent)|give (it )?to (an)?other agent|take over",
    "correction": r"^(no[,. ]|nope|wrong|undo|revert|that'?s not|i meant|not that)",
    "step back / reuse": r"step back|reinvent|already exist|single source of truth",
}

def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text", ""))
            elif b.get("type") == "tool_result":
                out.append(text_of(b.get("content")))
    return "\n".join(out)

def bash_head(cmd):
    cmd = re.sub(r"^(\s*(cd \S+|[A-Z_]+=\S+|export \S+)\s*(&&|;)\s*)+", "", cmd.strip())
    cmd = re.sub(r"^(sudo|timeout \d+\w?|env)\s+", "", cmd)
    parts = cmd.split()
    if not parts:
        return "?"
    if parts[0] in ("git", "gh", "docker", "pixi", "dl", "bazel", "npm", "uv", "cargo") and len(parts) > 1:
        return " ".join(parts[:2])
    return parts[0]

def err_class(cmd, body):
    if "Blocked:" in body:                                   return "harness blocked (e.g. foreground sleep)"
    if "not a git repository" in body:                       return "wrong cwd: not a git repo"
    if re.search(r"No such file|does not exist|cannot access", body): return "missing path"
    if "timed out" in body.lower():                          return "timeout"
    if re.search(r"Exit code 14[34]", body):                 return "killed (pkill/timeout self-hit)"
    if "gh " in cmd:                                         return "gh"
    if re.search(r"\b(bazel|pytest|colcon|bm test|ctest)\b", cmd): return "build/test"
    if re.search(r"\bdl\b|docker", cmd):                     return "dl/docker"
    if "git " in cmd:                                        return "git"
    if "python" in cmd:                                      return "python snippet"
    return "other"

tools, skills, slash, bash_heads, models, sub_types = C(), C(), C(), C(), C(), C()
tool_err, bash_err, friction = C(), C(), C()
err_samples = collections.defaultdict(list)
tok, sub_tok, poll = C(), C(), C()
tok_by_model = collections.defaultdict(C)
big_results = []
short_prompts = []
interrupts = compactions = 0
over_200k = 0
sessions = []

files = [f for f in Path(a.root).rglob("*.jsonl") if f.stat().st_mtime >= cutoff]
for f in files:
    is_sub = "subagents" in f.parts
    parent = f.parts[f.parts.index("subagents") - 1] if is_sub else f.stem
    s = dict(id=f.stem, parent=parent, project=f.relative_to(a.root).parts[0], sub=is_sub,
             prompts=0, turns=0, tools=C(), tok=C(), first_prompt=None, skills=[],
             errors=0, start=None, end=None, peak_ctx=0, poll_ctx=0)
    names, seen = {}, set()
    for line in f.open(errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ts = d.get("timestamp")
        if ts and ts < since_iso:
            continue  # a long-lived file touched recently still holds old turns
        if ts:
            s["start"] = s["start"] or ts
            s["end"] = ts
        t, m = d.get("type"), d.get("message") or {}
        if t == "system" and d.get("subtype") == "compact_boundary":
            compactions += 1
        if t == "assistant":
            u = m.get("usage") or {}
            ctx = sum(u.get(k) or 0 for k in IN_KEYS)
            mid = m.get("id")
            if mid and mid not in seen and u:  # one message spans several lines; count usage once
                seen.add(mid)
                s["turns"] += 1
                mdl = m.get("model", "?")
                models[mdl] += 1
                for k in (*IN_KEYS, "output_tokens"):
                    s["tok"][k] += u.get(k) or 0
                    tok_by_model[mdl][k] += u.get(k) or 0
                s["peak_ctx"] = max(s["peak_ctx"], ctx)
                over_200k += max(0, ctx - 200_000)
            for b in m.get("content") or []:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                n, inp = b.get("name", "?"), b.get("input") or {}
                names[b.get("id")] = (n, inp)
                tools[n] += 1
                s["tools"][n] += 1
                if n == "Skill":
                    skills[inp.get("skill", "?")] += 1
                    s["skills"].append(inp.get("skill", "?"))
                elif n == "Bash":
                    cmd = inp.get("command") or ""
                    bash_heads[bash_head(cmd)] += 1
                    if POLL_RE.search(cmd) and not inp.get("run_in_background"):
                        poll["bash sleep/until/--watch"] += 1; poll["bash sleep/until/--watch ctx"] += ctx
                        s["poll_ctx"] += ctx
                elif n in ("ReadNotifications", "Monitor", "TaskOutput"):
                    poll[n] += 1; poll[n + " ctx"] += ctx
                    s["poll_ctx"] += ctx
                elif n in ("Agent", "Task"):
                    sub_types[inp.get("subagent_type") or "general-purpose"] += 1
        elif t == "user":
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    n, inp = names.get(b.get("tool_use_id"), ("?", {}))
                    body = text_of([b])
                    if b.get("is_error"):
                        tool_err[n] += 1
                        s["errors"] += 1
                        key = err_class(inp.get("command", ""), body) if n == "Bash" else n
                        if n == "Bash":
                            bash_err[key] += 1
                        if len(err_samples[key]) < 3:
                            err_samples[key].append(((inp.get("command") or "")[:90] + " => " + body[:130]).replace("\n", " "))
                    if len(body) > 20000:
                        big_results.append((len(body), n, s["id"][:8], (inp.get("command") or inp.get("file_path") or "")[:90].replace("\n", " ")))
            if d.get("isMeta") or d.get("toolUseResult") is not None or is_sub:
                continue
            txt = text_of(c).strip()
            if not txt or txt.startswith("<local-command"):
                continue
            if "[Request interrupted by user" in txt:
                interrupts += 1
                continue
            cm = re.search(r"<command-name>/?([^<]+)</command-name>", txt)
            if cm:
                slash[cm.group(1).strip()] += 1
            elif txt.startswith("<"):
                continue
            s["prompts"] += 1
            if s["first_prompt"] is None and not (cm and cm.group(1).strip() == "clear"):
                s["first_prompt"] = txt[:150].replace("\n", " ")
            if not cm and len(txt) < 200:
                one = txt.replace("\n", " ")
                short_prompts.append(f"{s['id'][:8]} {one}")
                for label, rx in FRICTION.items():
                    if re.search(rx, one, re.I):
                        friction[label] += 1
    if s["turns"] or s["prompts"]:
        for k, v in s["tok"].items():
            tok[k] += v
            if is_sub:
                sub_tok[k] += v
        sessions.append(s)

def tin(x): return sum(x.get(k, 0) for k in IN_KEYS)
def fmt(n): return f"{n/1e9:.2f}B" if n >= 1e9 else f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k" if n >= 1e3 else str(int(n))
main = [s for s in sessions if not s["sub"]]
kids = collections.defaultdict(list)
for s in sessions:
    if s["sub"]:
        kids[s["parent"]].append(s)
for s in main:
    s["family_tok"] = tin(s["tok"]) + sum(tin(k["tok"]) for k in kids[s["id"]])
    s["n_sub"] = len(kids[s["id"]])
    fp = s["first_prompt"] or ""
    cm = re.search(r"<command-name>/?([^<]+)</command-name>", fp)
    s["workflow"] = "/" + cm.group(1).strip() if cm else ("skill:" + s["skills"][0]) if s["skills"] else "freeform"

T = tin(tok)
print(f"# Claude Code usage — last {a.days:g} days (since {since_iso}Z)")
print(f"{len(main)} sessions · {len(sessions)-len(main)} subagent transcripts · {sum(s['prompts'] for s in main)} prompts · "
      f"{sum(s['turns'] for s in sessions)} assistant turns · {interrupts} interrupts · {compactions} compactions")
if main:
    print(f"median per session: {statistics.median(s['prompts'] for s in main)} prompts, {statistics.median(s['turns'] for s in main)} turns")

print(f"\n## Tokens\ninput-side {fmt(T)} = uncached {fmt(tok['input_tokens'])} + cache-write {fmt(tok['cache_creation_input_tokens'])} + cache-read {fmt(tok['cache_read_input_tokens'])} · output {fmt(tok['output_tokens'])}")
if T:
    print(f"cache-read share {tok['cache_read_input_tokens']/T:.1%} · avg context per turn {fmt(T/max(1,sum(models.values())))}")
    print(f"subagents {fmt(tin(sub_tok))} ({tin(sub_tok)/T:.0%}) · context above 200k per turn {fmt(over_200k)} ({over_200k/T:.0%})")
    pc = sum(v for k, v in poll.items() if k.endswith(" ctx"))
    print(f"polling turns {fmt(pc)} ({pc/T:.0%}): " + ", ".join(f"{k} {poll[k]} calls/{fmt(poll[k+' ctx'])}" for k in poll if not k.endswith(" ctx")))
for mdl, b in sorted(tok_by_model.items(), key=lambda x: -tin(x[1])):
    print(f"  {mdl}: {models[mdl]} turns, in {fmt(tin(b))}, out {fmt(b['output_tokens'])}")
bands = C("<50k" if s["peak_ctx"] < 5e4 else "50-150k" if s["peak_ctx"] < 1.5e5 else "150-300k" if s["peak_ctx"] < 3e5 else ">=300k" for s in main)
print("peak context per session: " + " · ".join(f"{k} {bands[k]}" for k in ("<50k", "50-150k", "150-300k", ">=300k")))
hot = [s for s in main if s["peak_ctx"] >= 3e5]
if T:
    print(f"sessions peaking >=300k: {len(hot)}, holding {fmt(sum(s['family_tok'] for s in hot))} ({sum(s['family_tok'] for s in hot)/T:.0%}) incl. their subagents")

print("\n## Workflows (by how the session started; tokens include its subagents)")
wf = collections.defaultdict(list)
for s in main:
    wf[s["workflow"]].append(s)
for k, v in sorted(wf.items(), key=lambda x: -sum(s["family_tok"] for s in x[1]))[:15]:
    tot = sum(s["family_tok"] for s in v)
    print(f"  {k:28s} n={len(v):3d}  {fmt(tot):>7} ({tot/max(T,1):4.0%})  median {fmt(statistics.median(s['family_tok'] for s in v)):>6}  subagents {sum(s['n_sub'] for s in v)}")

print("\n## Skills loaded via Skill tool"); print("  " + " · ".join(f"{k} {v}" for k, v in skills.most_common()))
print("## Slash commands typed");        print("  " + " · ".join(f"{k} {v}" for k, v in slash.most_common()))
print("## Tools (errors)");              print("  " + " · ".join(f"{k} {v}({tool_err[k]})" for k, v in tools.most_common(20)))
print("## Subagent types");              print("  " + " · ".join(f"{k} {v}" for k, v in sub_types.most_common()))
print("## Bash heads");                  print("  " + " · ".join(f"{k} {v}" for k, v in bash_heads.most_common(30)))

print(f"\n## Bash errors by class ({sum(bash_err.values())} of {tools['Bash']} calls)")
for k, v in bash_err.most_common():
    print(f"  {v:4d}  {k}")
print("## Error samples")
for k, lst in err_samples.items():
    for e in lst[:2]:
        print(f"  [{k}] {e[:200]}")

print(f"\n## Large tool results >20k chars: {len(big_results)} ({dict(C(t for _, t, _, _ in big_results))})")
for n, t, sid, what in sorted(big_results, reverse=True)[:8]:
    print(f"  {fmt(n):>5} {t:5s} {sid} {what}")

print(f"\n## Friction signals in {len(short_prompts)} short prompts (regex; read prompts.txt to confirm)")
for k, v in friction.most_common():
    print(f"  {v:4d}  {k}")

print("\n## Heaviest sessions (tokens incl. subagents)")
for s in sorted(main, key=lambda s: -s["family_tok"])[:12]:
    print(f"  {fmt(s['family_tok']):>6} peak {fmt(s['peak_ctx']):>5} turns {s['turns']:4d} prompts {s['prompts']:3d} subs {s['n_sub']:3d} "
          f"poll {fmt(s['poll_ctx']):>5} {s['id'][:8]} {s['project'][-22:]} | {(s['first_prompt'] or '')[:80]}")
print("\nTranscript of a session: find ~/.claude/projects -name '<id>*.jsonl'")

if a.out:
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "prompts.txt").write_text("\n".join(short_prompts) + "\n")
    rows = [{k: (dict(v) if isinstance(v, C) else v) for k, v in s.items()} for s in sessions]
    (out / "stats.json").write_text(json.dumps(dict(
        window_days=a.days, since=since_iso, tokens=tok, sub_tokens=sub_tok, over_200k=over_200k, poll=poll,
        tools=tools, tool_errors=tool_err, bash_errors=bash_err, skills=skills, slash=slash,
        friction=friction, models=models, sessions=rows), indent=1, default=str))
