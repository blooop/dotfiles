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
3. As each returns, give the user its findings with links, and the next PR that
   starts. Check its cleanup line: a workspace it could not delete is an open
   item in the ledger.
4. When all have returned, run `dl --ls` and `docker ps -a` once. Every workspace
   and container this run made must be gone. Delete what is left, as in the Cleanup part
   of the brief.
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
- `~/kinisi` is root-owned. Put throwaway clones under /tmp/claude-1000/.
- The host is dev-only: no robots, no host DDS tuning.
- Reproduce a defect rather than argue it. A claim that a test cannot run
  needs evidence.

Cleanup, after the review is posted, even when the review failed:
- Note the workspace id from `dl --ls`, then run `dl <owner/repo>@<branch> rm`.
  You made no commits, so `rm` should not refuse. If it does, run `git status`
  in the clone, report what it found, and then run `rm --force`.
- Run `docker ps -a | grep <workspace id>`. Remove any container still left,
  such as a `kinisi_unreal_runtime_*` sim sidecar, with `docker rm -f`.
- Delete any clone you made under /tmp/claude-1000/.

Return under 250 words: the findings you posted, each with its comment URL; the
findings you refuted and why; what you ran and the result; and one cleanup line
that names what you deleted and anything you could not delete.
```
