---
name: review-dl
description: Run `review-other` on one or more PRs, each in its own subagent and its own dl workspace, then delete the workspace so the host is left clean. Use when asked to review several PRs with dl subagents, or when the user runs `/review-dl`.
argument-hint: "[N] <pasted PR list> [N] (N agents at once; default 1, serial)"
---

# Review PRs in dl workspaces

You are the **dispatcher**. Each PR gets one subagent; the subagent runs the
`review-other` skill inside a dl workspace on the PR's branch, and deletes that
workspace when the review is done. Your context holds only each subagent's short
summary, never a diff or a log.

## Arguments

The user pastes a list of PRs, often straight from a chat or a numbered list, with
the agent count before or after it: `/review-dl 2 <list>` or `/review-dl <list> 2`.

- **Agent count N**: a bare integer under 100 that is the first or the last token
  (`-j N` also works). Default **1**, a serial review: start the next subagent
  only when the last one has returned. With N > 1, keep N running and start the
  next PR as each returns. Each workspace builds on its own, so a high N costs
  RAM; above 3, say so before you start.
- **PR references**: every URL, `#number`, bare number of 100 or more, or
  `owner/repo@branch` in the rest of the text. A bare number belongs to the repo
  of the current directory, else `kinisi-robotics/kinisi_ros`.
- **Noise**: list markers (`1.`, `2)`, `-`, `*`), titles and other pasted text.
  Skip them, and drop a PR that appears twice.

If the count and the PRs are still unclear, list how you read them and ask once.

## Steps

1. Resolve each PR to `owner/repo`, number, head branch, title and author with
   `gh pr view <n> -R <owner/repo> --json number,title,headRefName,author`. A PR
   from a fork has no branch dl can open: report it as blocked, and go on.
2. Start the subagents (`general-purpose`, `run_in_background: true`), at most N
   at a time, each with the brief below. End your turn while they run; the
   completion notification wakes you.
   **Check the host before each start.** Each reviewer starts 4–5 axis agents
   and builds, so N=3 is about 15 agents. Run `~/.claude/hooks/resource-check.sh`;
   it prints a `systemMessage` when RAM is short or too many bazel servers run.
   If it prints one, start no new reviewer: wait for one to return, or drop N to
   1 and tell the user. On 2026-10-07, N=3 on a host with 35 dev containers
   reached load average 353 and hung other sessions.
   **Forward the axis notices.** Each reviewer spawns its own axis agents
   (Defects, Tests, Mutant…), and their notices often reach you, not the
   reviewer. A notice from an agent you did not start belongs to a reviewer:
   at once, `SendMessage` it to that reviewer (match it by the PR or branch in
   its text) with "the final report of your <axis> agent: …", unless it says
   it may be interim. Forward nothing and the reviewer sleeps until someone
   asks — in one run it lost 80 minutes. A reviewer whose result says it
   still waits on axes is not done: check that each named axis has reported.
3. As each returns, give the user its findings with links, and the next PR that
   starts. Check its cleanup line: a workspace it could not delete is an open
   item in the ledger.
4. When all have returned, check each workspace id from the cleanup lines, and
   only those: the host holds many other sessions' workspaces and sidecars, and
   an unfiltered listing floods the context.
   `for id in <ids>; do dl --ls | grep -c "$id"; docker ps -a --format '{{.Names}}' | grep -c "$id"; done`.
   Every count must be 0. Delete what is left, as in the Cleanup part of the brief.
5. End on the ledger: one line per PR with the review link and the comment count,
   the test result, and the cleanup result.

## The brief

Fill the `<...>` fields. The subagent does not inherit your memories, so the
runner facts here are the only ones it gets.

```
Run the `review-other` skill (Skill tool, skill: "review-other", args: "<PR URL>")
on <PR URL> — "<title>", branch `<branch>`, author <author>. Follow the skill in
full, including posting the verified inline comments it calls for. Never edit or
push to the branch under review.

Runner:
- Workspace: `dl <owner/repo>@<branch>`. Run a command in it with
  `dl <owner/repo>@<branch> -- bash -lc '<cmd>'`.
- Each `dl <ws> -- cmd` costs about 56 s. For repeated runs, find the dl-made
  dev container with `docker ps` and use `docker exec` into it.
- Run Python tooling and prek in the container, never on the host (the host
  python3 is 3.14 without ensurepip).
- `~/kinisi` is root-owned. Put throwaway clones under `${CLAUDE_CODE_TMPDIR:-/tmp}/claude-$(id -u)/` (on disk; /tmp is RAM).
- The host is dev-only: no robots, no host DDS tuning.
- Reproduce a defect rather than argue it. A claim that a test cannot run
  needs evidence.
- Build through `bm`, never raw `bazel --output_user_root=<own dir>`: a new
  cache root gets no disk cache, no remote cache and no test env, rebuilds
  the whole tree, and then exits 127 on `libfastcdr.so.2`. On 2026-10-07 six
  such roots at once hung the host.
- One bazel server per container. Only the Mutant axis builds a mutant;
  other axes reproduce through `bm` in the main checkout, one run at a time.
- For a mutant, use the worktree's own `<worktree>/bin/bm test //pkg:target`.
  `bm` takes its repo root from its own path, so that copy builds the
  worktree. The bare `bm` alias runs `$KINISI_ROOT/bin/bm`, the main
  checkout, and tests the unmutated code. Or put the mutant in the dl
  clone itself, run `bm test`, then `git checkout -- <file>`.
- Give `bm test` one target, `//pkg:target`, never a package name: a
  package name built 10,716 actions on 2026-10-07.
- `docker top` shows host pids. To stop a process in the container, get
  its pid from `docker exec <c> ps`.
- Your axis agents may run async. Their notices can come to the root session,
  which forwards them to you. Only a final report counts: a notice that says it
  "may be interim" is not one, and never write a result no tool gave you.
- Before you end a turn while an axis has not reported, find that axis
  (ListAgents, or SendMessage to it). If it still runs, wait for its notice;
  if it died, run that axis again. Do not end the turn on a bare "I wait".

Cleanup, after the review is posted and every axis agent has sent its final
report, even when the review failed:
- Run `docker top <dev container>`. Stop each bazel server you find with
  `bin/bm shutdown` in its checkout (`<worktree>/bin/bm shutdown` for a
  worktree one) before `rm`. Do not `rm` while a bazel process lives.
- Note the workspace id from `dl --ls`, then run `dl <owner/repo>@<branch> rm`.
  You made no commits, so `rm` should not refuse. If it does, run `git status`
  in the clone, report what it found, and then run `rm --force`.
- Run `docker ps -a | grep <workspace id>`. Remove any container still left,
  such as a `kinisi_unreal_runtime_*` sim sidecar, with `docker rm -f`.
- Delete any clone you made under `${CLAUDE_CODE_TMPDIR:-/tmp}/claude-$(id -u)/`.

Return under 250 words: the findings you posted, each with its comment URL; the
findings you refuted and why; what you ran and the result; and one cleanup line
that names what you deleted and anything you could not delete.
```
