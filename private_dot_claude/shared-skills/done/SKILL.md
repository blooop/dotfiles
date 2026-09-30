---
name: done
description: Answer "is this done?" for a session — recover what was asked, finish the easy remainder, and say done or not with the reasons; before the user exits, also make the work durable and clean up. Use when the user asks if the session or task is done, what is left, or about loose ends, says to clean up or finish up before they close or exit, or asks where the work is saved or whether it is merged or released.
argument-hint: "[anything the close-out must also do, e.g. 'and /sync']"
---

Arguments: "$ARGUMENTS"

The user asking is often coming back to this session after hours or days, with none of its context left in their head. "Is this done?" is a genuine question, and the answer must stand on its own for a reader who remembers nothing.

The skill answers two questions:

- **Done**: is every piece of work the user asked for finished, with evidence?
- **Safe to close**: if the user exits now, is this session's work **durable** — somewhere they can reach tomorrow from another machine — with nothing lost?

The user wants the answer to be yes. When the work left between here and yes is **easy**, do it, then answer. When it is not, answer no and explain.

Two branches, from the user's words:

- **Question** ("is this done?", "what's left?", "is it merged?"): the user may keep working with this session.
- **Close-out** ("clean up before I close", "sync so I can exit"): the user is leaving. Step 5 runs in full.

## 1. Recover the goal

Re-read the conversation from the start. List every item the user asked for, including requests changed or added later, and the plan the session was following. For each item, find its state: finished with evidence, partly done, not started, or blocked (and on what).

Then list the **flags**: everything the session raised that the user did not follow up — a bug noticed on the side, a failing check left alone, an "I also saw…", a "want me to…?" with no answer, a TODO the session left, a step it skipped. The user often remembers only that there were loose ends, not what they were.

Done when every ask is on the list with a state and the evidence or reason behind it, and every flag is on its own list with one line on what it is. An ask missing from the list reads as done, so the lists are complete before any answer.

## 2. Scope: list what this session touched

List every repo, clone, worktree, `dl` workspace, directory, background task, subagent, container, PR, ticket and published artifact this session created or changed. Include `~/.local/share/chezmoi` when the session changed anything under `~/.claude`, `~/.config` or another chezmoi-managed path (`chezmoi managed` confirms).

Give every item an owner: **mine** (this session made it) or **not mine** (it was there at the start, or another session made it). The git status at the start of the conversation is the baseline; a file dirty in that snapshot is not mine unless this session edited it.

## 3. Sweep

Run the sweep on every repo from step 2:

```bash
~/.claude/shared-skills/done/scripts/sweep.sh <repo> [<repo> ...]
```

It is read-only. Per repo it prints in-progress rebases or merges, a detached HEAD, uncommitted paths, stashes, branches with no upstream or unpushed commits or a gone upstream, linked worktrees, and your open PRs with CI state. Then it prints running containers and ports your processes hold.

Then check what the script cannot see:

- Background tasks and subagents of this session that still run (`/tasks`).
- Work outside any repo: scratchpad files, `/tmp`, container-only paths, a directory that `sweep.sh` calls "not a git repo".
- For each PR: is CI green, is it merged, and — when the user asked for a release — is the tag or package published and the installed version the new one.

Done when every loose end in the output is attributed to a step-2 item or marked not mine.

## 4. Finish the easy remainder

Work left is **easy** when all of these hold:

- You can finish it now, in this turn, with the context you already hold.
- It needs no decision from the user (step 6 lists the ones that are theirs).
- You can prove it finished: a test run, a green check, a pushed commit.

Examples: commit and push this session's own work; run the tests and fix a failure whose cause is clear; push a branch with `-u`; move a notes file from the scratchpad into its repo; add the README entry; run `/sync` when chezmoi-managed files changed.

Work is **not easy** when it needs a new plan, a failure has an unknown cause, it waits on something outside the session (CI still running, a review, a person), it would run long, or it needs a step-6 decision. Leave it, and record the reason — that reason is the "why not" in the report.

A flag is not an ask: the user may have passed it by on purpose. Fix a flag in step 4 only when it is easy and it sits inside the asked work (a bug in code this session wrote, a test this session broke). Leave every other flag for the report.

Do every easy item, then update the step-1 lists. Leave every **not mine** item as it is.

## 5. Make it durable and clean up

Run this in full on the **close-out** branch, and on the **question** branch when step 4 left the work done. On a question branch with work still open, run only the first two bullets: the running tasks and scratch copies may be the work in progress.

- **Uncommitted or unpushed work that is mine**: commit it on its branch in the repo's commit style and push it. When the session changed chezmoi-managed files, run the `sync` skill last.
- **Work outside a repo** the user will want again (research notes, a decoded dump, a plan): move it into the repo it belongs to and commit it, or put it on the project's ticket. A scratchpad path is not an answer to "where is it saved".
- **Background tasks and subagents**: wait for the ones near done and keep their results; stop the rest and record what they were doing.
- **Scratch copies**: remove worktrees, clones, `dl` workspaces, containers and local build output this session made, once the sweep shows they hold nothing unpushed. Remove local branches whose PR merged (`[gone]`).
- **Claimed tickets** with no finished work: unassign them or comment where the work stands.
- **Work not done on close-out**: write a handoff per the global CLAUDE.md so the next session can continue.

Re-run `sweep.sh`. Done when the only loose ends left are not mine or wait on a step-6 decision.

## 6. Decisions that stay with the user

Ask before any of these, and put them first in the report:

- Deleting anything that holds work no remote has: an unmerged branch, a stash, a dirty worktree.
- Deleting or overwriting anything published: a release, a package, a remote branch someone else uses.
- Committing or pushing a **not mine** change, or pushing to a default branch where the repo uses PRs.
- Merging a PR.

## 7. Report

Open with the two verdicts, one line each:

- **Done: yes**, or **Done: no — <the main thing left>**.
- **Safe to close: yes**, or **Safe to close: no — <what would be lost>**.

When either is no, follow with **why**, written for a reader with no context:

1. The goal, in one or two sentences: what the user asked for and why.
2. Where it stands: what is finished, and where that work lives.
3. What is left, and for each item the reason step 4 could not finish it now.
4. The next step: the decision the user must make, or the prompt that continues the work.

Then:

- The step-6 decisions, each with the command that carries it out.
- What step 4 finished in this turn, with its evidence.
- The ledger per the global CLAUDE.md: every ask from step 1 as *done*, *not done* or *blocked*, with its evidence. For work, the evidence is **where it lives**: a commit, a pushed branch, a PR link, a ticket, a handoff path.
- The **flags** from step 1: for each, what it is, why it matters, whether step 4 fixed it, and the next step (fix it, put it on a ticket, or drop it). An open flag does not change **Done**, but it is lost if the session closes, so offer to put the open flags on a ticket or in the handoff.
- The **not mine** loose ends the sweep found, one line each. They change neither verdict.
