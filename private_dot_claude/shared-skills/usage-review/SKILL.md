---
name: usage-review
description: Weekly review of my Claude Code usage — skills and workflows used, friction, token efficiency, and ranked fixes compared against last week.
disable-model-invocation: true
argument-hint: "[days, default 7]"
---

# Usage review

Review how Claude Code was used over the window (default 7 days; `$ARGUMENTS` overrides):
which skills and workflows ran, where the human had to push, where tokens bought
nothing, and which standing instructions no longer earn their place. The deliverable is a short list of **fixes**, each tied to a mechanism seen in a
transcript and a number to check next week. Counts point at a problem; a transcript shows
its mechanism. Every finding in the report names its mechanism.

Reports live in `~/.claude/usage-reviews/<YYYY-MM-DD>/` — one folder per run, so each week
diffs against the last.

## Steps

1. **Collect.** Run the stats script; its stdout is the main input.

   ```bash
   D=~/.claude/usage-reviews/$(date +%F); mkdir -p "$D"
   python3 ~/.claude/skills/usage-review/scripts/usage_stats.py --days ${ARGUMENTS:-7} --out "$D" | tee "$D/stats.txt"
   ```

   Done when `$D/stats.txt`, `$D/stats.json` and `$D/prompts.txt` exist.

2. **Load last week.** Read the newest earlier `~/.claude/usage-reviews/*/report.md`, and
   list skill and instruction changes since that date:

   ```bash
   chezmoi git -- log --since=<last report date> --format='%h %ad %s' --date=short -- '*claude*'
   ```

   For each fix last week's report proposed: did a commit land, and did its metric move?
   No earlier report means this is the baseline week; say so and skip the comparison.

3. **Read the prompts.** Read all of `$D/prompts.txt`. The script's friction counts are regex
   hints; the prompts are the evidence. Group them into friction themes: the human nudging a
   stopped agent, re-asking for status, fixing the environment and saying "try now", asking
   for plainer prose, relaying context between agents, correcting a wrong turn. A theme is
   real when three or more prompts show it.

4. **Trace the outliers.** For the three heaviest sessions, any session whose polling
   share is over 10%, and one sample session per friction theme, get the mechanism:

   ```bash
   python3 ~/.claude/skills/usage-review/scripts/session_trace.py <id-prefix> [--grep REGEX] [--subagents]
   ```

   The trace collapses repeats and prints context size per turn. Use it instead of a raw
   Read of a `.jsonl` — a transcript runs to megabytes. Done when each outlier has a
   one-line mechanism ("polled `ReadNotifications` 1099 times at ~150k context while waiting
   for CI"), not a restated count.

5. **Audit the instructions and clean the memories.** Follow
   [instruction-audit.md](references/instruction-audit.md) over the global `CLAUDE.md`, the
   busiest repos' `AGENTS.md`, and their memory files. Friction from step 3 often points at
   a rule that is failing or at a footgun. Memory is the one place this skill edits without
   asking: back it up, apply the clear-cut verdicts, and carry the rest to the report as
   questions (the reference's **Memory cleanup** section). Done when every memory has a
   verdict and every clear-cut one is applied.

6. **Price the waste.** Tokens here are input-side context re-read on every turn, so cost is
   *turns × context size*. Attribute tokens to each mechanism from step 4: polling turns,
   context above 200k, subagent fan-out that is too big for the diff, whole files or diffs
   dumped into the parent, repeated work after a crash or a handoff. Name the share of the
   window's total each one holds.

7. **Write `$D/report.md`** with these sections:
   - **Snapshot** — sessions, prompts, tokens, cache-read share, subagent share, deltas vs last week.
   - **Skills and workflows** — what ran, how often, cost per run (median), and what changed.
   - **Friction** — each theme: count, two quoted prompts, the mechanism, the fix.
   - **Token efficiency** — each waste mechanism with its token share.
   - **Instructions** — each non-keep verdict (stale, duplicate, no-op, footgun, failing)
     with its evidence and fix; the keeps in one line.
   - **Memories** — what was deleted, rewritten or fixed, with the reason; the questions
     for the human; memories waiting on a fix to land.
   - **Last week's fixes** — landed or not, and whether the metric moved.
   - **Fixes** — ranked by tokens or human prompts at stake. Each fix names the file to change
     (a skill, `CLAUDE.md`, a hook, a setting, a repo's code), the change, and the metric to
     check next week. A fix that removes a footgun also names the rule it lets you delete.
     Three to six fixes; the ones whose evidence is strongest go first.

   Done when every fix has evidence, a target file, and a metric.

8. **Report in chat.** Give the snapshot, the top fixes, and the report path. Offer to apply
   the fixes; edit skills or settings only when the human says yes (memory edits from step
   5 are already done — list them). A fix in a team repo is
   a proposed PR.

## Reading the numbers

- **cache-read share** near 95% is normal and good; a drop means context is rebuilt often
  (many short resumes, edits to always-loaded files, model switches mid-session).
- **avg context per turn** is the price of each tool call. Above ~150k, a long debug loop
  costs more than moving that loop into a subagent and returning a summary.
- **Workflows** group sessions by how they started (`/review-self`, `skill:pr`, `freeform`);
  their token figures include subagents. A `skill:` row whose median is far above the same
  slash command means the skill ran late in a session that was already large.
- **Bash errors** at a 2–4% rate are background noise. Look for a class that repeats one
  cause: a wrong cwd, a renamed skill, a tool-schema mismatch, a blocked foreground `sleep`.
- **Friction** counts come from the human's own words; one repeated nudge per day costs the
  human more than a million tokens costs the budget.
