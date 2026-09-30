---
name: done
description: Close out a session so the user can exit — sweep for loose ends, make this session's work durable, clean up what it left behind, and answer "safe to close". Use when the user asks if the session is done, says to clean up or finish up before they close or exit, or asks where the work is saved or whether it is merged or released.
argument-hint: "[anything the close-out must also do, e.g. 'and /sync']"
---

Arguments: "$ARGUMENTS"

The user is about to close this session and walk away, often to another machine. Anything that is only in this container, this scratchpad, a local branch or an uncommitted file is lost to them. The job is **durable**: at the end, every piece of this session's work lives somewhere the user can reach tomorrow from another machine, and every process and scratch copy this session started is stopped or removed.

Asking this is the order to close out, not a request for a report. Commit and push this session's own work without asking again. Stop for the user only on the decisions in step 4.

## 1. Scope: list what this session touched

From the conversation, list every repo, clone, worktree, `dl` workspace, directory, background task, subagent, container, PR, ticket and published artifact this session created or changed. Include `~/.local/share/chezmoi` when the session changed anything under `~/.claude`, `~/.config` or another chezmoi-managed path (`chezmoi managed` confirms).

Done when every item has an owner: **mine** (this session made it) or **not mine** (it was there at the start, or another session made it). The git status at the start of the conversation is the baseline; a file dirty in that snapshot is not mine unless this session edited it.

## 2. Sweep

Run the sweep on every repo from step 1:

```bash
~/.claude/shared-skills/done/scripts/sweep.sh <repo> [<repo> ...]
```

It is read-only. Per repo it prints in-progress rebases or merges, a detached HEAD, uncommitted paths, stashes, branches with no upstream or unpushed commits or a gone upstream, linked worktrees, and your open PRs with CI state. Then it prints running containers and ports your processes hold.

Then check what the script cannot see:

- Background tasks and subagents of this session that still run (`/tasks`). Exit kills them; their results are lost.
- Work outside any repo: scratchpad files, `/tmp`, container-only paths, a directory that `sweep.sh` calls "not a git repo".
- For a PR this session opened: is CI green, is it merged, and — when the user asked for a release — is the tag or package published and the installed version the new one.

Done when every loose end in the output is attributed to a step-1 item or marked not mine.

## 3. Make it durable and clean up

Work through each **mine** item:

- **Uncommitted work**: commit it on its branch in the repo's commit style, then push. When the session changed chezmoi-managed files, run the `sync` skill last, so the other machines get it.
- **Unpushed branch or no upstream**: push it with `-u`.
- **Work outside a repo** that the user will want again (research notes, a decoded dump, a plan): move it into the repo it belongs to and commit it, or put it on the project's ticket. A scratchpad path is not an answer to "where is it saved".
- **Background tasks and subagents**: wait for the ones near done and keep their results; stop the rest and record what they were doing.
- **Scratch copies**: remove worktrees, clones, `dl` workspaces, containers and local build output this session made, once the sweep shows they hold nothing unpushed. Remove local branches whose PR merged (`[gone]`).
- **Claimed tickets** with no finished work: unassign them or comment where the work stands.
- **Unfinished work**: when the task is not done, write a handoff per the global CLAUDE.md so the next session can continue.

Leave every **not mine** item as it is, and list it in the report.

Re-run `sweep.sh`. Done when the only loose ends left are not mine, or wait on a step-4 decision.

## 4. Decisions that stay with the user

Ask before any of these, and put them first in the report:

- Deleting anything that holds work no remote has: an unmerged branch, a stash, a dirty worktree.
- Deleting or overwriting anything published: a release, a package, a remote branch someone else uses.
- Committing or pushing a **not mine** change, or pushing to a default branch where the repo uses PRs.
- Merging a PR.

## 5. Report

Lead with the verdict, in one line: **Safe to close: yes**, or **Safe to close: no — <what is left>**. Then:

1. The decisions from step 4, each with the command that carries it out.
2. The ledger per the global CLAUDE.md: every item from step 1 as *done*, *not done* or *blocked*, with its evidence. For work, the evidence is **where it lives**: a commit, a pushed branch, a PR link, a ticket, a handoff path.
3. The **not mine** loose ends the sweep found, one line each, so the user knows they exist.
