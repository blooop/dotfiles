# Global instructions

## How you write to me

Write every message to me in ASD-STE100 Simplified Technical English, the controlled
language ASD publishes for maintenance documentation. Short, plain and unambiguous beats
fluent. The rules that carry the weight:

- Use the active voice, and name who does the thing.
- Write one idea per sentence. Keep an instruction to 20 words, a statement to 25.
- Keep a paragraph to six sentences.
- Start an instruction with its verb: "Run the suite", not "The suite should be run".
- Use one word for one thing, in every message. Repeat the word instead of varying it.
- Use simple tenses. Keep `-ing` forms for technical names.
- Keep the articles and the relative pronouns: "the test that failed", not "test failed".
- Keep a noun cluster to three words.
- Put a warning before the step it applies to.

I do not hold the STE approved-word list verbatim, so read "approved words only" as "use
the plainest common word that says it": *start*, not *initiate*; *use*, not *utilize*;
*fix*, not *remediate*.

This governs the prose I read in chat, and it outranks any other voice guidance there.
Code, commands, file paths and quoted output stay verbatim. Prose you write for somewhere
else — a commit body, a PR description, a README — follows that destination's rules. The
link rules below apply to every message.

## PR descriptions

Write every PR description, and every edit to one, with the `pr-plain` skill: Simplified
Technical English, ordered as a news story. Create PRs with `/pr`, which loads it. When
another route makes a PR (`stack`, a plain `gh pr create`), load `pr-plain` and write the
body with it; never ship `--fill` commit text as the body.

## Links

Every reference to a GitHub issue, PR, commit, or any URL goes in chat as a clickable
markdown link — `[#502 — title](https://github.com/org/repo/issues/502)`, never a bare
`#502` and never a bare URL. The terminal renders markdown, so a linked reference is one
click; a bare `#502` is a manual search.

This applies to *every* occurrence in a message, not just the first mention — sweep the
whole message before sending, closing "next steps" paragraph included. A bare `#N` inside
a link's own title text is fine.

**Never put a link inside a markdown table.** Table cells do not linkify in the terminal,
so a `[#502 — title](url)` in a table renders as dead text and the link is lost. Anything
with links is a list, never a table — even when the data is tabular and a table would lay
it out better. Put the link first in each bullet and hang the other fields off it:

```
- [#11094 — ros: Fix four tests that depend on what else ran](https://github.com/org/repo/pull/11094)
  base `main` · 7 files · +88/−112
```

The same goes for anything else that swallows a link: code fences, blockquote-only
summaries, and shell snippets that list bare PR numbers. If a command needs bare numbers
(`for n in 11094 11095; do ...`), link those PRs in the prose around it.

## Verifying before you report

"I could not run the tests" is a claim, and it needs evidence like any other. Before
making it, find the project's real runner. Containerized repos on this host come up with
`dl <org>/<repo>@<branch>`; many repos also ship their own entry point, and a README
usually names it. A missing or stale `.venv` is not evidence that a suite cannot run —
it almost always means you looked in the wrong place.

This matters most when reviewing or debugging. A failure you have actually reproduced is
worth more than five careful readings, and an argument you hand someone where you could
have handed them a reproduction is the weaker thing to have sent.

**Do process experiments inside a throwaway container**, never in the host shell. Kill
only a pid you recorded; never `pkill`/`killall` on the host.

**When you delegate, put the runner in the subagent's brief.** Subagents read this file,
but they do not inherit the parent session's recalled memories — so anything you know
only from memory has to be restated in the prompt, or it never reaches them. Name the
skill the subagent must load in its brief, too.

**End the work with a ledger.** The last message lists every item I asked for as
*done* (with its evidence: commit, PR link, the test run), *not done*, or *blocked*
(and on what). An item missing from the ledger reads as done, so none is missing.
Start each bullet with its status mark, so the open items show at a glance:

```
- ✅ Fix the flaky test — [#502 — title](https://github.com/org/repo/pull/502), suite green
- ❌ Update the README — not started
- ⛔ Deploy to staging — blocked on access to the cluster
```

Stop to report when you need a decision from me, when you are blocked, or when the
ledger is all *done* — a checkpoint with unblocked work left is where you keep going.

**When I say I am away** ("going home", "overnight", "no more questions"), do not
call `AskUserQuestion` and do not end a turn on a question: an unanswered question
blocks the session until I come back. Take your recommended option, write it in the
ledger as **decided for you**, with the other options and why, and keep going. A
one-way door is the only exception: a delete, a force-push, a merge, or a message
to other people. Park that item as ⛔ with the question, and go on with the rest.
Put this rule in the brief of every subagent you start while I am away.
Before each long wait while I am away, write the current ledger to the session's
handoff file, so a stall or a power-off still leaves me a report when I come back.

## Keeping the context small

Every tool call re-reads the whole conversation, so a turn costs what the context
holds: 200 calls at 300k is 60M tokens. Keep the parent context for decisions.

- **A loop goes to a subagent.** Repeated runs — sim or benchmark iterations, CI
  fix-and-retry, a flaky test run N times — go to one subagent (in the background when
  long) whose brief carries the runner and whose return is a short summary: what ran,
  what failed, the evidence. That subagent stays small too: at about 150k context it
  writes its state to a handoff file and returns, and the parent starts a fresh one
  from that file. Put this in the brief.
- **Wait by notification.** A command that outlives the 10-minute Bash limit runs with
  `run_in_background`, and you end the turn; its completion wakes you. A foreground
  `sleep`, `until` or `--watch` loop re-reads the context to learn nothing changed.
  An interim task notification (the agent is still running and waiting on its own
  work) gets a one-line reply and no action. The harness refuses an empty turn.
- **Background agents go one level deep.** Only the parent starts background agents.
  A subagent runs its own workers in the foreground and blocks until each returns: a
  notification does not reliably wake a subagent that ended its turn to wait, and the
  whole chain then waits in silence (2026-10-25: two group agents stalled for 9 hours).
  Put this in the brief of every subagent that starts agents.
- **A turn that ends on "waiting" is a stall.** When a subagent's result says it is
  waiting (on a worker, a run, an interim notification), it has stopped, not paused:
  resume it with SendMessage at once and tell it to wait in the foreground.
- **Agents get a heartbeat.** While background agents run, keep one background
  `run-wait --timeout 7200 -- sh -c '! find <session>/subagents -name "*.jsonl" -mmin
  -30 | grep -q .'` going (the session dir is under `~/.claude/projects/`). It exits
  when no agent transcript changed for 30 minutes; then look at each agent, resume the
  stalled ones, and start a new heartbeat.
- **Every wait has a timeout and sees the run die.** A loop that only greps a log
  waits in silence after the run crashes. Use `~/.claude/scripts/run-wait --timeout
  SECS --pid PID -- CHECK` in the background: it stops at once when the pid ends.
- **Say how long, and check when late.** When you start background work, tell me how
  long it should take. When its notification is twice that late, look at the child
  (its output, its process) and tell me what you find. "Still running" is a claim too.
- **Poll GitHub slowly.** Every container and the host share one token, so they share
  one quota of 5000 API calls an hour. `gh run watch` polls every 3s and `gh pr checks
  --watch` every 10s by default; one watch on an hour-long run takes half the quota.
  Always pass `--interval 60` or more, and run one watch at a time — to wait on several
  runs, watch them one after another, or poll `gh pr checks` once every few minutes.
- **Read summaries, not dumps.** Take `git diff --stat` and targeted hunks into the
  parent; the full diff, a whole log, or a whole large file belongs in a subagent.

## Handoffs between agents

When another agent takes over, or I ask for a prompt to give another agent, write the
handoff to `~/.claude/handoffs/<YYYY-MM-DD>-<branch-or-topic>.md` — kinisi_ros
containers mount `~/.claude`, so the host and those containers both read it. It holds
the goal, the current state, branch and PR links, the runner, and the next steps. Give
me its path and a one-line prompt that points at it. Where `~/.claude` is not mounted,
give the same content inline as a paste-ready block.

To find another agent, run `herdr agent list` on the host. Each row has the
`pane_id`, the tab title I see (`terminal_title_stripped`), the status, and a host
session's id; an agent in a dl container shows as `<repo>@<branch>`. `ListAgents`
misses the dl-container agents, and there is no herdr inside a container. Name an
agent to me by its tab title. Message it with `herdr agent prompt <pane_id> "<text>"`,
read it with `herdr agent read <pane_id>`, and never guess a recipient.

To learn what another session did, run
`~/.claude/skills/usage-review/scripts/session_trace.py <session-id>` (it takes `--grep`)
rather than reading the `.jsonl` — a transcript runs to megabytes.
