# Methodology: fixes are experiments

A review that proposes fixes and never checks them only collects opinions. Every fix
this skill proposes goes into the ledger as an experiment. The fix stays only if its
metric moved.

## The loop

1. **Observe.** The numbers show where to look, and a transcript or a telemetry record
   shows the mechanism behind them.
2. **Hypothesize.** Write down what the mechanism causes and which number it moves. For
   example: "agents wait 40 min a day for me because blocked panes in other workspaces
   are not visible → `agent_wait_hours_per_day` drops if the agent queue shows them".
3. **Change one thing.** Change one file (skill, CLAUDE.md, hook, setting, tool code).
   Ship it as one commit so the ledger can name it.
4. **Measure.** The daily digest shows the metric each day. The check date is when the
   experiment is judged.
5. **Decide.** Keep, revert, or mark inconclusive. A reverted fix goes out of the file
   it touched. A kept one stays, and the monthly retro asks again whether it still earns its place.

## The ledger

The ledger is `~/.claude/usage-reviews/experiments.jsonl`, one JSON object per line. The
agent edits it in the weekly and monthly reviews. `usage_stats.py` only reads it.

```json
{"id":"E004","opened":"2026-10-06","hypothesis":"…","change":"abc1234 CLAUDE.md","metric":"poll_share","direction":"down","baseline":0.12,"target":0.05,"check":"2026-10-20","status":"running","closed":null,"result":null}
```

- `metric` is a key of `metrics` in `stats.json`, which is the name of a file in
  `sql/metrics/`. If the metric you need is not there,
  write it as an ad-hoc query first (see below). Do not open the experiment until
  the query gives a baseline.
- `baseline` is this week's value, from the same query, before the change lands.
- `target` is the smallest change you would call a win. Pick it before the result is
  known, never after.
- `check` is 14 days after `opened` by default. Use 7 days for a metric that moves every
  day (tokens, polling). Use 28 days for a metric that moves every week (friction themes).
- `status` is `running`, `kept`, `reverted` or `inconclusive`. When you close an
  experiment, set `closed` and a one-line `result` with the number.

## Picking a metric

- **Use a rate, not a total.** Every metric in `metrics` is per day, a share or a
  percentile, so a 1-day digest can compare with a 7-day baseline.
- **Measure the cost the human feels.** One nudge a day costs you more than a million
  tokens cost the budget. So the human-time metrics (`response_latency_*`,
  `agent_wait_hours_per_day`, `friction_*_per_day`) come first when two metrics conflict.
- **Name a guard metric when a fix could move a cost somewhere else.** For example, a fix
  that cuts review fan-out should not raise `friction_correction_per_day`. Write the guard
  in `hypothesis`.
- **Expect noise.** A week with half the usual sessions moves every share. If the window
  had fewer than 10 sessions, call the result inconclusive, not a win.

## When to revert

- The metric moved the wrong way past the baseline by the size of the target, or a guard
  metric did.
- The metric did not move, and the change costs something every session: context, a
  hook fork, a rule the agent must read. A rule with no effect is not free.
- The mechanism is gone for another reason (a tool changed, or a repo is no longer used).
  Close the experiment as `inconclusive` and remove the fix if nothing else needs it.

## Ad-hoc questions and promotion

A new question goes into a throwaway query, `$D/adhoc/<slug>.sql`, in the review folder.
The first line is a comment with the question. Run it in `usage-db`, which opens DuckDB
with every log loaded as a table (`.read $D/adhoc/<slug>.sql`; `.read` needs the full
path, not `~`). The tables and the shared views are in `sql/sources.sql`. A query that
needs a window uses `in_window(ts)`, which reads the `t0` and `t1` variables; they default
to the last 7 days.

A question that comes back in three reviews becomes a named metric. Move the file to
`sql/metrics/<name>.sql`, make it return one row with a column `value`, and add a test on
fixtures in `scripts/tests/`. The file name is the metric name, so the ledger can use it
at once. The metric must not depend on the window length: divide a count by
`getvariable('days')`, or return a share or a percentile. A breakdown that is not one
number goes to `sql/reports/<name>.sql` instead, and `stats.txt` prints it as a table.
The monthly retro counts the ad-hoc queries.

## Adding a goal

A new goal (for example, how long a `dl` or `aid` start takes) needs no Python change.

1. **Emit events.** The tool writes JSONL, one flat object per line:
   `{"ts": "<ISO-8601 UTC>", "ev": "<name>", ...fields}`. A field can be added later; the
   tables keep each whole line as `j`, so a new field is `j->>'field'`.
2. **Add or extend a table** in `sql/sources.sql`. A new log is one block that reads its
   glob; a glob that matches no file gives an empty table.
3. **Add metric files** in `sql/metrics/`, one number each, with a test.
4. **Open an experiment** in the ledger when a change is meant to move the metric.

## The data

- Transcripts: `~/.claude/projects/**/*.jsonl` (tokens, tools, what the human said).
- Claude hooks: `~/.claude/telemetry/claude-<date>.jsonl` (session lifecycle, full prompts,
  host or container, herdr pane, dl workspace). Devcontainers with the `claude-code`
  feature write to the host's copy through the `~/.claude` mount.
- herdr: `~/.claude/telemetry/herdr-<date>.jsonl` (focus, agent status, pane snapshots
  with the Claude session id). The logger is the `telemetry` herdr plugin.
- devlaunch and aid: `~/.local/state/devlaunch/events.jsonl` (dl `launch`, `session_end`,
  `stop`, `kill`, `remove`, `prune`; aid `aid_start`, `aid_end`; `seconds`, `cold`,
  `stages`).
- Transcript cache: `~/.cache/usage-review/transcripts/` (one row per assistant turn and
  per human prompt, written by `usage_stats.py`; SQL reads these as `turns` and `prompts`).

Join keys: the Claude `session_id` (the herdr snapshots hold it as `session`), `pane`
(`HERDR_PANE_ID`), `dl_ws` (`DEVLAUNCH_WORKSPACE_ID`), and time.
