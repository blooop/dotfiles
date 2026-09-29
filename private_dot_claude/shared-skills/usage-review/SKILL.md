---
name: usage-review
description: Weekly (or, with `month`, monthly) review of my Claude Code usage — skills and workflows used, friction, token efficiency, my working patterns from herdr and devlaunch telemetry, and fixes run as experiments with a metric, compared against last week.
disable-model-invocation: true
argument-hint: "[days, default 7 | month]"
---

# Usage review

Review how Claude Code was used over the window (default 7 days; `$ARGUMENTS` overrides):
which skills and workflows ran, where the human had to push, where tokens bought
nothing, and which standing instructions no longer earn their place. The deliverable is a short list of **fixes**, each tied to a mechanism seen in a
transcript and a number to check next week. Counts point at a problem; a transcript shows
its mechanism. Every finding in the report names its mechanism.

Every fix is an **experiment** in the ledger `~/.claude/usage-reviews/experiments.jsonl`,
with a named metric, a baseline and a check date. A fix stays only if its metric moved.
Read [methodology.md](references/methodology.md) before step 2: it has the ledger format,
how to pick a metric, when to revert, and the rule for ad-hoc queries.

The review is one of three rhythms:

- **Daily:** `usage_stats.py --digest`, a script with no agent. The first interactive
  shell of the day prints it (`usage-digest` in `.bash_env`). It shows yesterday's metrics
  and the running experiments.
- **Weekly:** this skill, steps 1–8.
- **Monthly:** this skill with `month` as the argument. Run steps 1–8 with a 30-day window,
  then the **Monthly retro** section.

Reports live in `~/.claude/usage-reviews/<YYYY-MM-DD>/` — one folder per run, so each week
diffs against the last.

## Steps

1. **Collect.** Run the stats script; its stdout is the main input.

   ```bash
   D=~/.claude/usage-reviews/$(date +%F); mkdir -p "$D"
   S=~/.claude/skills/usage-review/scripts/usage_stats.py
   case "${ARGUMENTS:-7}" in
       month) python3 $S --month --out "$D" | tee "$D/stats.txt" ;;
       *)     python3 $S --days ${ARGUMENTS:-7} --out "$D" | tee "$D/stats.txt" ;;
   esac
   ```

   The script reads the transcripts into a cache, then runs every metric in
   `sql/metrics/` and every breakdown in `sql/reports/` in one DuckDB call. The SQL reads
   the telemetry logs (`~/.claude/telemetry/` for the Claude hooks and herdr,
   `~/.local/state/devlaunch/events.jsonl` for dl and aid), and the script reads the ledger.
   Done when `$D/stats.txt`, `$D/stats.json`, `$D/prompts.txt` and `$D/prompts_full.txt`
   exist. A metric that is `null` has no data yet; say so rather than guess.

2. **Load last week.** `~/.claude/usage-reviews` is a git clone of the private
   blooop/usage-reviews, shared by every machine. Pull it first, so the ledger and the
   reports from other machines are here: `git -C ~/.claude/usage-reviews pull --ff-only`.
   Read the newest earlier `~/.claude/usage-reviews/*/report.md`, and
   list skill and instruction changes since that date:

   ```bash
   chezmoi git -- log --since=<last report date> --format='%h %ad %s' --date=short -- '*claude*'
   ```

   Then read the ledger and the **Experiments** block of `stats.txt`. For each experiment
   whose check date has come: decide kept, reverted or inconclusive by the rules in
   methodology.md, and write `status`, `closed` and a one-line `result` with the number.
   A reverted fix is a change to propose in step 8. An experiment whose commit never
   landed stays `running` with a new check date, and the report says it did not land.
   No earlier report means this is the baseline week; say so and skip the comparison.

3. **Read the prompts.** Read all of `$D/prompts.txt`, then skim `$D/prompts_full.txt`
   for the long prompts that file leaves out (relayed context, long corrections). The script's friction counts are regex
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

5. **Read the working patterns.** Take the telemetry metrics and the report tables from
   `stats.txt`: response latency by hour and by repo, agent wait hours, parallel agents,
   focus switches, active hours, session wall time, container share, dl and aid start
   times by repo and by stage. Look for the mechanism, as in step 4: an agent that waits
   for hours because its pane is in a workspace you do not look at; a latency peak at the
   hours you run the most agents; a repo whose cold start eats the first minutes of each
   session. A question the fixed metrics do not answer goes into an ad-hoc query,
   `$D/adhoc/<slug>.sql`, that you run in `usage-db` (methodology.md, **Ad-hoc questions**).
   Done when each pattern you report names its mechanism and the number behind it.

6. **Audit the instructions and clean the memories.** Follow
   [instruction-audit.md](references/instruction-audit.md) over the global `CLAUDE.md`, the
   busiest repos' `AGENTS.md`, and their memory files. Friction from step 3 often points at
   a rule that is failing or at a footgun. Memory is the one place this skill edits without
   asking: back it up, apply the clear-cut verdicts, and carry the rest to the report as
   questions (the reference's **Memory cleanup** section). Done when every memory has a
   verdict and every clear-cut one is applied.

7. **Price the waste.** Tokens here are input-side context re-read on every turn, so cost is
   *turns × context size*. Attribute tokens to each mechanism from steps 4 and 5: polling turns,
   context above 200k, subagent fan-out that is too big for the diff, whole files or diffs
   dumped into the parent, repeated work after a crash or a handoff. Name the share of the
   window's total each one holds.

8. **Write `$D/report.md`** with these sections:
   - **Snapshot** — sessions, prompts, tokens, cache-read share, subagent share, deltas vs last week.
   - **Skills and workflows** — what ran, how often, cost per run (median), and what changed.
   - **Friction** — each theme: count, two quoted prompts, the mechanism, the fix.
   - **Working patterns** — each pattern from step 5 with its number and mechanism.
   - **Token efficiency** — each waste mechanism with its token share.
   - **Instructions** — each non-keep verdict (stale, duplicate, no-op, footgun, failing)
     with its evidence and fix; the keeps in one line.
   - **Memories** — what was deleted, rewritten or fixed, with the reason; the questions
     for the human; memories waiting on a fix to land.
   - **Experiments** — each one judged this week: kept, reverted or inconclusive, with the
     number; the ones still running, with their current value.
   - **Fixes** — ranked by tokens or human prompts at stake. Each fix names the file to change
     (a skill, `CLAUDE.md`, a hook, a setting, a repo's code), the change, and the metric to
     check next week. A fix that removes a footgun also names the rule it lets you delete.
     Three to six fixes; the ones whose evidence is strongest go first.

   Append each fix to the ledger as a `running` experiment, with its baseline from this
   week's `stats.json` `metrics`. The `change` field stays empty until the commit lands.
   Done when every fix has evidence, a target file, a metric, and a ledger row.

9. **Report in chat.** Give the snapshot, the top fixes, and the report path. Offer to apply
   the fixes; edit skills or settings only when the human says yes (memory edits from step
   6 are already done — list them). A fix in a team repo is
   a proposed PR.

   Then commit and push the review, so the other machines see it. The repo's
   `.gitignore` keeps the memory backup and the prompt dumps out:

   ```bash
   git -C ~/.claude/usage-reviews add -A
   git -C ~/.claude/usage-reviews commit -m "Review $(date +%F)"
   git -C ~/.claude/usage-reviews push
   ```

   A ledger edit made outside a review (a `change` field after a commit lands) is
   committed and pushed the same way.

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

## Monthly retro

Run this after step 8 when the argument is `month`. Add its findings to `report.md` as a
**Retro** section.

1. **Score the month.** List every experiment opened or closed in the window (the
   `--month` output has them). Count kept, reverted and inconclusive. When more than half
   are inconclusive, the metrics are too noisy or the windows too short; say which ones.
2. **Delete what earns nothing.** A rule, hook or skill step whose experiment came back
   inconclusive twice, or that no experiment ever measured, is a candidate for removal.
   Propose each removal with its evidence.
3. **Review the method.** Name the metrics that no report used in the month, and propose to
   remove them (delete the file in `sql/metrics/`). Count the ad-hoc queries,
   `~/.claude/usage-reviews/*/adhoc/*.sql` (the `--month` output has the count). A question
   asked in three of them becomes a named metric (methodology.md, **Ad-hoc questions**).
4. **Check the instruments.** Confirm that each telemetry log was written on most days,
   and look for `logger_error` records in the herdr log. Remove a log that no metric reads.
   Delete telemetry files older than 180 days:

   ```bash
   find ~/.claude/telemetry -name '*.jsonl' -mtime +180 -delete
   ```

