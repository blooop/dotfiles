# Instruction audit

Every always-loaded instruction costs context on every turn of every session, and every
rule the agent must remember is a rule it sometimes forgets. The audit asks of each rule:
does it still earn its line, and could the environment make it unnecessary?

## Which files

- `~/.claude/CLAUDE.md` (the global file; `~/AGENTS.md` links to it).
- The `AGENTS.md` / `CLAUDE.md` at the root of each repo that held ≥5 sessions in the
  window (the stats' Projects list), read from `origin/main` with `git show`. Nested ones
  only where the window's sessions worked in that subtree.
- Memory: `~/.claude/projects/*/memory/*.md` for the same projects.

A team-owned file (kinisi_ros `AGENTS.md`) is audited the same way, but its fixes are
proposals for a PR, never direct edits.

## Verdicts

Give each rule or memory one verdict, with its evidence:

- **keep** — live, and the behaviour it asks for is not the default. Most lines land here;
  list them in one line, not one each.
- **stale** — names a tool version, path, flag, branch or limitation the environment no
  longer has. Check it: run the command, `git show origin/main:<path>`, `which <tool>`
  inside the container. A claim checked in this run is the evidence; a feeling is not.
- **duplicate** — the same meaning lives in another loaded file or a skill. Keep the
  source of truth, delete the copy.
- **no-op** — the model does this unprompted. Evidence is transcripts where the behaviour
  shows up in sessions that never loaded the rule, or a rule nobody ever tripped.
- **footgun** — the rule warns about a trap the environment could remove: a bad default,
  a missing guard, an error message that names the wrong cause. The fix is the
  code/config change that removes the trap, after which the rule is deleted. This is the
  verdict worth the most; hunt for it.
- **failing** — the rule is live, but the transcripts show agents break it anyway. Prose
  has already lost; the fix is a hook or a default that enforces it.

## Transcript checks

For a rule that forbids or requires a command, count it in the window's Bash calls
(adapt this; `ts` limits it to the window):

```bash
cd ~/.claude/projects && python3 - <<'EOF'
import json, re, time; from pathlib import Path
cut = time.time() - 7*86400; since = time.strftime("%Y-%m-%dT%H", time.gmtime(cut))
RX = re.compile(r"git\b[^|;&]*commit\b[^|;&]*--no-verify")   # the rule's command
n = 0
for f in Path(".").rglob("*.jsonl"):
    if f.stat().st_mtime < cut: continue
    for l in f.open(errors="replace"):
        if '"Bash"' not in l: continue
        j = json.loads(l)
        if j.get("timestamp", "") < since: continue
        for b in (j.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("name") == "Bash" and RX.search(b["input"].get("command", "")):
                n += 1; print(b["input"]["command"][:150].replace("\n", " "))
print(n)
EOF
```

For output rules (trailers, links, prose), check the artifact: `git log --since=7.days
--author=<me> --format=%B | grep -c '<trailer>'`, or the assistant text in transcripts.
Read a sample of matches before counting: a regex match inside a `pkill` or a heredoc is
not a violation.

## Memory cleanup

Memory files are local to this machine and have no history, so first copy them:

```bash
for p in ~/.claude/projects/*/memory; do
  d="$D/memory-backup/$(basename "$(dirname "$p")")"; mkdir -p "$d" && cp -a -- "$p/." "$d/"
done
```

Then apply, without asking, each verdict that evidence from this run settles:

- **stale** — rewrite the fact to what the environment says now; delete the memory when
  nothing true is left.
- **duplicate** — delete the memory when a loaded file or a skill carries the same rule.
- **retired** — a memory that says "delete once <fix> is on main": check main; if the fix
  is there, delete it. A footgun fix proposed this week gets that line added to its memory.
- **index** — every `MEMORY.md` line names a file that exists and every file has a line;
  every `[[name]]` link names a memory that exists or is removed. A memory that assigns
  the user pronouns they have not stated is rewritten with "the user" / they.

Leave, and ask the human in the report, any memory whose truth is a preference or a
"for now": those are theirs to retire.

## Done

Every loaded file has been read, every non-keep verdict carries evidence from this run,
every footgun and failing rule has a named fix (the file to change, the change, and the
rule it retires), and the clear-cut memory verdicts are applied.
