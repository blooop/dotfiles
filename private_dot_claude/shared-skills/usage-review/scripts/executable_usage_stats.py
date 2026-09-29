#!/usr/bin/env python3
"""Summarize Claude Code usage for a time window: transcripts, telemetry, experiments.

    usage_stats.py [--days 7] [--out DIR] [--digest [--daily-dir D]] [--month] [--refresh-cache]
                   [--root DIR] [--telemetry DIR] [--dl-events PATH] [--ledger PATH] [--cache DIR]

Two layers. This script is the transcript ingest: it keeps a cache of flat JSONL rows, one
per assistant turn and one per human prompt, under --cache (rebuilt per transcript only
when its mtime changes), and it prints the report's text sections. The metrics are SQL:
../sql/sources.sql loads every log (hooks, herdr, devlaunch/aid, the cache) into DuckDB,
and each ../sql/metrics/<name>.sql returns one row with a `value`. All of them, for every
window, run in one `duckdb` call. A new metric is a new .sql file, with no Python change.

Prints a compact report on stdout. With --out, also writes:
  DIR/stats.json        aggregates, per-session rows and a flat `metrics` dict
                        (name -> number or null; every metric is per day, a share
                        or a percentile, so windows of any length compare)
  DIR/prompts.txt       every short (<200 char) prompt the user typed, one per line,
                        prefixed with the session id — the raw material for friction
  DIR/prompts_full.txt  every prompt the telemetry hook saw, full length, newlines
                        escaped, prefixed with id8 and local HH:MM

--digest: window = yesterday (local) unless --days is given; prints <= 25 lines
comparing the window with the median of the 7 days before it, and writes it to
--daily-dir/<date>.txt. --month: 30-day window plus the ledger's month and a
count of ad-hoc queries under the reviews dir. --refresh-cache: update the cache
and exit (`usage-db` runs it before it opens DuckDB).
"""
import argparse, collections, datetime as dt, glob, json, os, re, statistics, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace

C = collections.Counter
IN_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
POLL_RE = re.compile(r"\bsleep\s+\d|\buntil\b|\bwhile\b.*\bsleep\b|--watch\b")
POLL_TOOLS = ("ReadNotifications", "Monitor", "TaskOutput")
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
HOME = os.path.expanduser("~")
SQL = Path(__file__).resolve().parent.parent / "sql"

def slug(label): return re.sub(r"\W+", "_", label.split(":")[0].lower()).strip("_")

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

POLL_RANK = {"settle": 0, "tool": 1, "watch": 2, "loop": 3}  # a turn with several polls takes the worst
def poll_kind(name, inp):
    """settle (foreground sleep <= 10 s), loop (until/while, or sleep > 10 s), watch (--watch),
    tool (Monitor/TaskOutput/ReadNotifications), or None. Background Bash never polls."""
    if name in POLL_TOOLS:
        return "tool"
    cmd = inp.get("command") or ""
    if name != "Bash" or inp.get("run_in_background") or not POLL_RE.search(cmd):
        return None
    if re.search(r"--watch\b", cmd):
        return "watch"
    if re.search(r"\buntil\b|\bwhile\b", cmd):
        return "loop"
    unit = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}
    secs = max((float(n) * unit[u] for n, u in re.findall(r"\bsleep\s+(\d+(?:\.\d+)?)([smhd]?)\b", cmd)), default=0)
    return "loop" if secs > 10 else "settle"

# --- time helpers: epochs everywhere; "local" means the host's TZ -----------------
def epoch(iso):
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None
def local_day(t): return time.strftime("%Y-%m-%d", time.localtime(t))
def midnight(t, back=0):  # local midnight of t's day, minus `back` days (DST-safe)
    d = dt.date.fromtimestamp(t) - dt.timedelta(days=back)
    return dt.datetime.combine(d, dt.time()).timestamp()

def read_jsonl(path):
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    yield d
    except OSError:
        return

# --- transcript cache: the rows sql/sources.sql reads as `turns`, `prompts`, `compactions` ----
def ingest(f, root):
    """All rows of one transcript file, every timestamp (the SQL windows them)."""
    is_sub = "subagents" in f.parts
    base = dict(session=f.stem, parent=f.parts[f.parts.index("subagents") - 1] if is_sub else f.stem,
                project=f.relative_to(root).parts[0])
    rows, turn_of, names, ts = [], {}, {}, None
    for line in f.open(errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue  # a truncated line: the file is still being written
        if not isinstance(d, dict):
            continue
        ts = d.get("timestamp") or ts
        if not ts:
            continue
        t, m = d.get("type"), d.get("message") or {}
        if t == "system" and d.get("subtype") == "compact_boundary":
            rows.append(dict(kind="compact", ts=ts, **base))
        if t == "assistant":
            mid = m.get("id") or id(d)  # one message spans several lines; one row per message
            row = turn_of.get(mid)
            if row is None:
                u = m.get("usage") or {}
                ctx = sum(u.get(k) or 0 for k in IN_KEYS)
                row = turn_of[mid] = dict(kind="turn", ts=ts, **base, model=m.get("model", "?"),
                    input=u.get("input_tokens") or 0, cache_write=u.get("cache_creation_input_tokens") or 0,
                    cache_read=u.get("cache_read_input_tokens") or 0, output=u.get("output_tokens") or 0,
                    context=ctx, over_200k=max(0, ctx - 200_000), tools=[], skills=[], tool_errors=[],
                    is_poll=False, poll_kind=None)
                rows.append(row)
            for b in m.get("content") or []:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                n, inp = b.get("name", "?"), b.get("input") or {}
                names[b.get("id")] = (n, row)
                row["tools"].append(n)
                if n == "Skill":
                    row["skills"].append(inp.get("skill", "?"))
                pk = poll_kind(n, inp)
                if pk and POLL_RANK[pk] >= POLL_RANK.get(row["poll_kind"], -1):
                    row["is_poll"], row["poll_kind"] = True, pk
        elif t == "user":
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                        n, row = names.get(b.get("tool_use_id"), ("?", None))
                        if row is not None:
                            row["tool_errors"].append(n)
            if d.get("isMeta") or d.get("toolUseResult") is not None or is_sub:
                continue
            txt = text_of(c).strip()
            if not txt or txt.startswith("<local-command"):
                continue
            intr = "[Request interrupted by user" in txt
            cm = re.search(r"<command-name>/?([^<]+)</command-name>", txt)
            if txt.startswith("<") and not cm and not intr:
                continue
            one = txt.replace("\n", " ")
            fr = [slug(k) for k, rx in FRICTION.items() if re.search(rx, one, re.I)] if not (cm or intr) and len(txt) < 200 else []
            rows.append(dict(kind="prompt", ts=ts, **base, text=txt, len=len(txt), friction=fr,
                             is_interrupt=intr, is_command=bool(cm)))
    return rows

_REPO = {}
def repo_of(cwd):
    """Git toplevel basename if cwd exists here, else its last part; /workspaces/<name> -> name."""
    if not cwd:
        return "?"
    if cwd not in _REPO:
        m = re.match(r"/workspaces/([^/]+)", cwd)
        p = Path(cwd)
        if m:
            r = m.group(1)
        elif "/.claude/worktrees/" in cwd:  # an agent worktree belongs to the clone it came from
            r = repo_of(cwd.split("/.claude/worktrees/")[0])
        elif p.is_dir():
            r = next((q.name for q in (p, *p.parents) if str(q) != HOME and (q / ".git").exists()), p.name)
        else:
            r = p.name
        _REPO[cwd] = r or cwd
    return _REPO[cwd]

CWD_RE = re.compile(r'"cwd":\s*("(?:[^"\\]|\\.)*")')
def refresh_cache(root, cache, tdir):
    """Re-ingest each transcript whose mtime changed; drop rows of deleted ones; rewrite the
    cwd -> repo map for every cwd in the hook logs (SQL cannot look for a .git)."""
    root, tx = Path(root), Path(cache) / "transcripts"
    keep = set()
    for f in root.rglob("*.jsonl"):
        c = tx / f.relative_to(root); keep.add(c)
        mt = f.stat().st_mtime_ns
        if c.exists() and c.stat().st_mtime_ns == mt:
            continue
        c.parent.mkdir(parents=True, exist_ok=True)
        tmp = c.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in ingest(f, root)))
        os.utime(tmp, ns=(mt, mt)); tmp.replace(c)
    for c in tx.rglob("*.jsonl") if tx.exists() else ():
        if c not in keep:
            c.unlink()
    cwds = set()
    for f in Path(tdir).glob("claude-*.jsonl"):
        for m in CWD_RE.finditer(f.read_text(errors="replace")):
            cwds.add(json.loads(m.group(1)))
    text = "".join(json.dumps(dict(cwd=c, repo=repo_of(c))) + "\n" for c in sorted(cwds))
    rp = Path(cache) / "repos.jsonl"
    if not rp.exists() or rp.read_text() != text:
        rp.parent.mkdir(parents=True, exist_ok=True); rp.write_text(text)

# --- transcripts, for the report's text sections -------------------------------------------
def scan(root, t0, t1):
    """One pass over transcripts touched since t0, keeping lines in [t0, t1), for the text
    sections of the report. The metrics read the transcript cache instead (ingest())."""
    since_iso, until_iso = (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) for t in (t0, t1))
    tools, skills, slash, bash_heads, models, sub_types = C(), C(), C(), C(), C(), C()
    tool_err, bash_err, friction = C(), C(), C()
    err_samples = collections.defaultdict(list)
    tok, sub_tok, poll = C(), C(), C()
    tok_by_model = collections.defaultdict(C)
    big_results, short_prompts, sessions = [], [], []
    interrupts = compactions = over_200k = 0
    files = [f for f in Path(root).rglob("*.jsonl") if f.stat().st_mtime >= t0]
    for f in files:
        is_sub = "subagents" in f.parts
        parent = f.parts[f.parts.index("subagents") - 1] if is_sub else f.stem
        s = dict(id=f.stem, parent=parent, project=f.relative_to(root).parts[0], sub=is_sub,
                 prompts=0, turns=0, tools=C(), tok=C(), first_prompt=None, skills=[],
                 errors=0, start=None, end=None, peak_ctx=0, poll_ctx=0)
        names, seen = {}, set()
        for line in f.open(errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = d.get("timestamp")
            if ts and not since_iso <= ts < until_iso:
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
                    pk = poll_kind(n, inp)
                    if pk:  # stats.json `poll` keeps its old keys; the kinds are in turns.poll_kind
                        k = n if pk == "tool" else "bash sleep/until/--watch"
                        poll[k] += 1; poll[k + " ctx"] += ctx
                        s["poll_ctx"] += ctx
                    if n == "Skill":
                        skills[inp.get("skill", "?")] += 1
                        s["skills"].append(inp.get("skill", "?"))
                    elif n == "Bash":
                        bash_heads[bash_head(inp.get("command") or "")] += 1
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
    return SimpleNamespace(**{k: v for k, v in locals().items() if k not in ("f", "s", "d", "b", "c", "m", "names", "seen", "line")})


# --- the SQL layer ------------------------------------------------------------------------------
def metric_files(): return sorted((SQL / "metrics").glob("*.sql"))
def report_files(): return sorted((SQL / "reports").glob("*.sql"))
def body(f): return re.sub(r";\s*\Z", "", Path(f).read_text().strip())
def title(f): return next((l[2:].strip() for l in Path(f).read_text().splitlines() if l.startswith("--")), "")
def lit(s): return "'" + str(s).replace("'", "''") + "'"
def at(t): return f"to_timestamp({float(t)!r})"

def duck(script):
    """Run a script in one `duckdb` process; return each SELECT's rows, in order."""
    p = subprocess.run(["duckdb", "-bail", "-json", ":memory:"], input=script, capture_output=True, text=True)
    if p.returncode or "Error" in p.stderr:
        raise RuntimeError(f"duckdb: {p.stderr.strip()[:2000]}")
    out, dec, s, i = [], json.JSONDecoder(), p.stdout, 0
    while True:
        while i < len(s) and s[i].isspace():
            i += 1
        if i >= len(s):
            return out
        v, i = dec.raw_decode(s, i)
        out.append(v)

def evaluate(src, windows, reports=(), queries=(), metrics=None):
    """src: telemetry_dir, dl_events, cache_dir (paths), now, load_from (epochs).
    windows: [(t0, t1, days)]. Every metric runs in every window; the reports and extra
    `queries` run in the first. Returns ([{metric: value}] per window, {report: rows}, [rows])."""
    sets = [f"SET VARIABLE {k} = {at(v) if k in ('now', 'load_from') else lit(v)};" for k, v in src.items() if v is not None]
    union = "\nUNION ALL\n".join(f"SELECT {lit(f.stem)} AS name, (SELECT value FROM (\n{body(f)}\n))::DOUBLE AS value"
                                 for f in (metrics or metric_files()))
    def win(t0, t1, days):
        return [f"SET VARIABLE t0 = {at(t0)};", f"SET VARIABLE t1 = {at(t1)};", f"SET VARIABLE days = {float(days)!r};"]
    lines = [*sets, (SQL / "sources.sql").read_text(), "CREATE TEMP TABLE _m (win INTEGER, name VARCHAR, value DOUBLE);"]
    for i, w in enumerate(windows):
        lines += [*win(*w), f"INSERT INTO _m SELECT {i}, name, value FROM (\n{union}\n);"]
    lines += win(*windows[0])
    lines += [body(f) + ";" for f in reports] + [q.rstrip(";") + ";" for q in queries]
    lines.append("SELECT win, name, value FROM _m ORDER BY win, name;")
    res = duck("\n".join(lines))
    if len(res) != len(reports) + len(queries) + 1:
        raise RuntimeError(f"duckdb returned {len(res)} results, expected {len(reports) + len(queries) + 1}")
    per = [{} for _ in windows]
    for r in res[-1]:
        per[r["win"]][r["name"]] = r["value"]
    return per, {Path(f).stem: rows for f, rows in zip(reports, res)}, res[len(reports):-1]

def cell(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.4g}"
    return str(v)
def table(rows, indent="  "):
    if not rows:
        return [indent + "(no rows)"]
    cols = list(rows[0])
    cells = [[cell(r[c]) for c in cols] for r in rows]
    w = [max(len(c), *(len(x[i]) for x in cells)) for i, c in enumerate(cols)]
    num = [all(isinstance(r[c], (int, float)) or r[c] is None for r in rows) for c in cols]
    fmt_row = lambda xs: indent + "  ".join(x.rjust(w[i]) if num[i] else x.ljust(w[i]) for i, x in enumerate(xs)).rstrip()
    return [fmt_row(cols)] + [fmt_row(x) for x in cells]

# --- experiment ledger ---------------------------------------------------------------------
def verdict(e, metrics):
    """on-track when the metric moved from baseline the way `direction` wants; + target met."""
    v, b, tg = metrics.get(e.get("metric")), e.get("baseline"), e.get("target")
    if v is None or not isinstance(b, (int, float)):
        return "no-data"
    sign = -1 if e.get("direction") == "down" else 1
    out = "on-track" if (v - b) * sign > 0 else "off-track"
    if isinstance(tg, (int, float)) and (v - tg) * sign >= 0:
        out += ", target met"
    return out

def fmt(n): return f"{n/1e9:.2f}B" if n >= 1e9 else f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k" if n >= 1e3 else str(int(n))
def fm(name, v):
    if v is None:
        return "-"
    if name.endswith(("_share", "_rate")):
        return f"{v:.1%}"
    return fmt(v) if abs(v) >= 1e4 else f"{v:.3g}"

def experiment_lines(ledger, metrics, today):
    out = []
    for e in ledger:
        if e.get("status") != "running":
            continue
        n = e.get("metric", "?")
        due = " · DUE" if (e.get("check") or "9999") <= today else ""
        out.append(f"  {e.get('id', '?')} {n} {e.get('direction', '?')}: now {fm(n, metrics.get(n))} vs baseline "
                   f"{fm(n, e.get('baseline'))} -> target {fm(n, e.get('target'))} · {verdict(e, metrics)}{due} (check {e.get('check')})")
    return out or ["  no running experiments"]

# --- output ----------------------------------------------------------------------------------
def tin(x): return sum(x.get(k, 0) for k in IN_KEYS)

def report(r, a, since_iso, ev):
    tok, sub_tok, poll, models, sessions = r.tok, r.sub_tok, r.poll, r.models, r.sessions
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
          f"{sum(s['turns'] for s in sessions)} assistant turns · {r.interrupts} interrupts · {r.compactions} compactions")
    if main:
        print(f"median per session: {statistics.median(s['prompts'] for s in main)} prompts, {statistics.median(s['turns'] for s in main)} turns")

    print(f"\n## Tokens\ninput-side {fmt(T)} = uncached {fmt(tok['input_tokens'])} + cache-write {fmt(tok['cache_creation_input_tokens'])} + cache-read {fmt(tok['cache_read_input_tokens'])} · output {fmt(tok['output_tokens'])}")
    if T:
        print(f"cache-read share {tok['cache_read_input_tokens']/T:.1%} · avg context per turn {fmt(T/max(1,sum(models.values())))}")
        print(f"subagents {fmt(tin(sub_tok))} ({tin(sub_tok)/T:.0%}) · context above 200k per turn {fmt(r.over_200k)} ({r.over_200k/T:.0%})")
        pc = sum(v for k, v in poll.items() if k.endswith(" ctx"))
        print(f"polling turns {fmt(pc)} ({pc/T:.0%}): " + ", ".join(f"{k} {poll[k]} calls/{fmt(poll[k+' ctx'])}" for k in poll if not k.endswith(" ctx")))
    for mdl, b in sorted(r.tok_by_model.items(), key=lambda x: -tin(x[1])):
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

    print("\n## Skills loaded via Skill tool"); print("  " + " · ".join(f"{k} {v}" for k, v in r.skills.most_common()))
    print("## Slash commands typed");        print("  " + " · ".join(f"{k} {v}" for k, v in r.slash.most_common()))
    print("## Tools (errors)");              print("  " + " · ".join(f"{k} {v}({r.tool_err[k]})" for k, v in r.tools.most_common(20)))
    print("## Subagent types");              print("  " + " · ".join(f"{k} {v}" for k, v in r.sub_types.most_common()))
    print("## Bash heads");                  print("  " + " · ".join(f"{k} {v}" for k, v in r.bash_heads.most_common(30)))

    print(f"\n## Bash errors by class ({sum(r.bash_err.values())} of {r.tools['Bash']} calls)")
    for k, v in r.bash_err.most_common():
        print(f"  {v:4d}  {k}")
    print("## Error samples")
    for k, lst in r.err_samples.items():
        for e in lst[:2]:
            print(f"  [{k}] {e[:200]}")

    print(f"\n## Large tool results >20k chars: {len(r.big_results)} ({dict(C(t for _, t, _, _ in r.big_results))})")
    for n, t, sid, what in sorted(r.big_results, reverse=True)[:8]:
        print(f"  {fmt(n):>5} {t:5s} {sid} {what}")

    print(f"\n## Friction signals in {len(r.short_prompts)} short prompts (regex; read prompts.txt to confirm)")
    for k, v in r.friction.most_common():
        print(f"  {v:4d}  {k}")

    print("\n## Heaviest sessions (tokens incl. subagents)")
    for s in sorted(main, key=lambda s: -s["family_tok"])[:12]:
        print(f"  {fmt(s['family_tok']):>6} peak {fmt(s['peak_ctx']):>5} turns {s['turns']:4d} prompts {s['prompts']:3d} subs {s['n_sub']:3d} "
              f"poll {fmt(s['poll_ctx']):>5} {s['id'][:8]} {s['project'][-22:]} | {(s['first_prompt'] or '')[:80]}")

    print("\n## Metrics (per day, share or percentile; stats.json `metrics`; sql/metrics/<name>.sql)")
    items = [f"{k} {fm(k, v)}" for k, v in ev.metrics.items()]
    for i in range(0, len(items), 4):
        print("  " + " · ".join(items[i:i + 4]))
    for f in report_files():
        print(f"\n## {f.stem}: {title(f)}")
        print("\n".join(table(ev.reports.get(f.stem, []))))
    print("\n## Experiments (running, from the ledger)")
    print("\n".join(experiment_lines(ev.ledger, ev.metrics, ev.today)))
    print("\nTranscript of a session: find ~/.claude/projects -name '<id>*.jsonl'")

def month_lines(ledger, t0, reviews_dir):
    d0 = local_day(t0)
    out = [f"\n## Month: experiments opened or closed since {d0}"]
    for e in ledger:
        if (e.get("opened") or "") >= d0 or (e.get("closed") or "") >= d0:
            out.append(f"  {e.get('id')} [{e.get('status')}] {e.get('metric')} {e.get('direction')} opened {e.get('opened')} "
                       f"closed {e.get('closed')} | {(e.get('hypothesis') or '')[:70]} | {(e.get('result') or '')[:60]}")
    if len(out) == 1:
        out.append("  none")
    out.append(f"ad-hoc queries: {len(glob.glob(str(Path(reviews_dir) / '*' / 'adhoc' / '*.sql')))} in {reviews_dir}/*/adhoc/")
    return out

PROMPTS_SQL = ("SELECT left(session, 8) AS id8, strftime(ts, '%H:%M') AS hhmm, prompt FROM claude_events "
               "WHERE in_window(ts) AND hook = 'UserPromptSubmit' AND prompt IS NOT NULL ORDER BY ts")
DIGEST_KEYS = ("tokens_per_day", "cache_read_share", "poll_share", "poll_loop_share", "subagent_share", "over_200k_share",
               "bash_error_rate", "prompts_per_day", "active_hours_per_day", "response_latency_p50_s", "response_latency_p90_s",
               "agent_wait_hours_per_day", "parallel_agents_p50", "focus_switches_per_active_hour", "session_wall_minutes_p50")

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=float)
    p.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    p.add_argument("--out")
    p.add_argument("--telemetry", default=os.path.expanduser("~/.claude/telemetry"))
    p.add_argument("--dl-events", default=os.path.expanduser("~/.local/state/devlaunch/events.jsonl"))
    p.add_argument("--ledger", default=os.path.expanduser("~/.claude/usage-reviews/experiments.jsonl"))
    p.add_argument("--cache", default=os.path.expanduser("~/.cache/usage-review"))
    p.add_argument("--digest", action="store_true")
    p.add_argument("--daily-dir", default=os.path.expanduser("~/.claude/usage-reviews/daily"))
    p.add_argument("--month", action="store_true")
    p.add_argument("--refresh-cache", action="store_true", help="update the transcript cache and exit")
    p.add_argument("--now", type=float, help=argparse.SUPPRESS)  # tests pin the clock
    a = p.parse_args(argv)
    t_start, now = time.time(), a.now or time.time()
    refresh_cache(a.root, a.cache, a.telemetry)
    if a.refresh_cache:
        return
    if a.digest and a.days is None:
        t1 = midnight(now); t0 = midnight(now, 1)
    else:
        a.days = a.days or (30 if a.month else 7)
        t0, t1 = now - a.days * 86400, now
    days = a.days = (t1 - t0) / 86400
    base = [(midnight(t0, i), midnight(t0, i - 1), 1) for i in range(7, 0, -1)] if a.digest else []
    src = dict(telemetry_dir=a.telemetry, dl_events=a.dl_events, cache_dir=a.cache, now=now,
               load_from=(base[0][0] if base else t0) - 86400)  # a day before, for herdr pane state
    per, reports, (prompts_full,) = evaluate(src, [(t0, t1, days), *base], report_files(), [PROMPTS_SQL])
    metrics = per[0]
    ledger = list(read_jsonl(a.ledger))
    today = local_day(now)
    since_iso = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(t0))
    r = scan(a.root, t0, t1) if a.out or not a.digest else None

    if a.digest:
        vals = collections.defaultdict(list)
        for dm in per[1:]:
            for k, v in dm.items():
                if v is not None:
                    vals[k].append(v)
        med = {k: statistics.median(v) for k, v in vals.items()}
        date = local_day(t1 - 1)
        out = [f"# usage digest {date} ({days:g} d window; 7d = median of the {len(vals.get('tokens_per_day', []))} days before)"]
        out += [f"  {k:32s} {fm(k, metrics.get(k)):>8}   7d {fm(k, med.get(k)):>8}" for k in DIGEST_KEYS]
        out.append("## Experiments")
        ex = experiment_lines(ledger, metrics, today)
        out += ex[:5] + ([f"  ... {len(ex) - 5} more"] if len(ex) > 5 else [])
        moved = [(k, v, med[k]) for k, v in metrics.items() if v is not None and med.get(k) and abs(v - med[k]) / abs(med[k]) > .5]
        out.append(f"## Moved > 50% vs 7d ({len(moved)})")
        out += [f"  {k} {fm(k, v)} vs {fm(k, b)} ({(v - b) / abs(b):+.0%})" for k, v, b in moved[:25 - len(out) - 1]]
        out = out[:25]
        print("\n".join(out))
        Path(a.daily_dir).mkdir(parents=True, exist_ok=True)
        (Path(a.daily_dir) / f"{date}.txt").write_text("\n".join(out) + "\n")
        print(f"digest took {time.time() - t_start:.2f}s", file=sys.stderr)
    else:
        report(r, a, since_iso, SimpleNamespace(metrics=metrics, reports=reports, ledger=ledger, today=today))
        if a.month:
            print("\n".join(month_lines(ledger, t0, Path(a.ledger).parent)))

    if a.out:
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        (out / "prompts.txt").write_text("\n".join(r.short_prompts) + "\n")
        (out / "prompts_full.txt").write_text("".join(
            f"{x['id8']} {x['hhmm']} {x['prompt'].replace(chr(13), '').replace(chr(10), chr(92) + 'n')}\n" for x in prompts_full))
        rows_out = [{k: (dict(v) if isinstance(v, C) else v) for k, v in s.items()} for s in r.sessions]
        (out / "stats.json").write_text(json.dumps(dict(
            window_days=days, since=since_iso, tokens=r.tok, sub_tokens=r.sub_tok, over_200k=r.over_200k, poll=r.poll,
            tools=r.tools, tool_errors=r.tool_err, bash_errors=r.bash_err, skills=r.skills, slash=r.slash,
            friction=r.friction, models=r.models, sessions=rows_out, metrics=metrics,
            sessions_by_repo={x["repo"]: x["sessions"] for x in reports.get("sessions_by_repo", [])},
            reports=reports,
            experiments=[{**e, "current": metrics.get(e.get("metric")), "verdict": verdict(e, metrics)} for e in ledger if e.get("status") == "running"]),
            indent=1, default=str))

if __name__ == "__main__":
    main()
