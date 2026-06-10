---
allowed-tools: Bash(git:*), Bash(gh:*), Read, Grep, Glob, Edit, Agent
description: Turn the current branch into a stack of GitHub PRs and keep it in sync. Two modes — create and sync.
argument-hint: "create <N> | sync"
---

## Context

- Current branch: !`git branch --show-current`
- Default branch: !`gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo main`
- Git status: !`git status --short`
- Commits since default: !`git log --oneline --reverse @{u}.. 2>/dev/null | head -50; git log --oneline --reverse origin/HEAD.. 2>/dev/null | head -50`
- Open PRs: !`gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,url -L 100 2>/dev/null`
- Arguments: "$ARGUMENTS"

---

## Model

A stack is a chain of branches — each its own PR — layered from the default branch up to the **top
branch** (the original branch you started from). Every branch is a real commit target.

- **The agent decides which branch each commit belongs to.** A change that addresses a given PR/slice is
  committed onto *that* branch, not blindly onto the tip. Genuinely new, unrelated work goes on top.
- After committing anywhere in the stack, **bookkeeping (`/stack sync`) restacks the descendants** so
  every branch above the change incorporates it. After a sync the top branch holds the full cumulative
  diff, so it stays the place to view the whole change.
- **Interior branches** are named `<top>-1 … <top>-(N-1)` (bottom → top); the original name stays on top.
- **GitHub PRs are the source of truth for topology** (`baseRefName`/`headRefName`). GitHub auto-retargets
  a dependent PR to the default branch when its base PR merges. Enabled globally: `rebase.updateRefs`,
  `rerere.enabled`; `git pushf` = `push --force-with-lease`.

Parse "$ARGUMENTS": first token is the mode (`create` or `sync`). `create` takes a stack size `<N>`.

---

## Committing into the stack (the agent's commit discipline)

When a change belongs to an existing stack, choose its branch deliberately:

1. **Pick the target branch** = the PR/slice the change belongs to — the one whose files/topic it touches,
   or whose review comment it addresses. Unrelated new work → the top branch.
2. **Check out that branch first, then make and commit the change there**
   (`git checkout <target>` → edit → `git commit`). Working on the target branch directly avoids
   cross-branch apply problems and keeps each PR's diff scoped to its own intent.
3. Batch as many commits across branches as you like, then run **`/stack sync`** once — it restacks the
   descendants and updates every PR.

### Keeping review comments intact

A force-push never deletes review comments — it can only mark them "outdated" (collapsed but still in the
thread). GitHub re-anchors each inline comment to its **diff hunk content**, not its commit SHA: if the
lines under a comment are unchanged after a rebase, the comment stays current. So restacking is mostly
comment-safe — outdating concentrates on the lines you actually changed. To keep it that way:

1. **Address a PR's feedback on that PR's branch**, not on top — the fix lands in the right PR's diff and
   only the comments you actually resolved go outdated.
2. **Keep every commit scoped to its own branch's files/lines.** If branch B's commits don't touch C's
   lines, rebasing C never shifts C's commented hunks, so C's comments survive.
3. **Resolve threads as you address them**, so open vs. outdated doesn't pile up ambiguously.
4. When resolving rebase conflicts, **change only the minimal lines** — don't re-flow unrelated code.
   `rerere` replays the same minimal resolution on each sync.

---

## Mode: `create <N>`

Slice the current branch into an **N-PR stack**: N−1 interior branches below, the original branch kept
as the top. `<N>` is the total number of PRs.

1. **Validate.** Current branch must not be the default branch. `git fetch <remote>` first.
2. **List commits** since the default branch, oldest → newest:
   `git log --reverse --format='%H %s' origin/<default>..HEAD`. Let `K` = count.
   - If `K < N`: stop and report — you need at least one commit per PR. Suggest a smaller `<N>`.
3. **Propose a split** into N contiguous groups (roughly even; put any remainder in the top group).
   Print the proposed grouping with commit subjects:
   ```
   Proposed 3-PR split of `feature` (6 commits):
     PR1 feature-1  ← main      : c1, c2
     PR2 feature-2  ← feature-1 : c3, c4
     PR3 feature    ← feature-2 : c5, c6   (top — your working branch)
   ```
   **Ask the user to confirm or adjust the boundaries before proceeding.**
4. **Create the interior branch refs** at each group's last commit (do NOT move the original branch):
   `git branch -f <branch>-<i> <boundary_commit_i>` for i = 1 … N−1.
5. **Push** every branch: `git push -u <remote> <branch>-1 … <branch>-(N-1) <branch>`.
6. **Create PRs** bottom → top, base = the branch below (default branch for the bottom):
   `gh pr create --head <b> --base <parent> --fill --draft`.
   (Ask whether to drop `--draft` if the user wants them review-ready immediately.)
7. **Stay on the original branch.** Print the final stack with PR links.

---

## Mode: `sync`

The single idempotent bookkeeping verb. **Inspect the current state, decide what's needed, do it.**
Safe to run from any state (mid-review, after new commits, after `main` moved, after a merge).

### 1. Determine state
- Default branch + open PRs from Context.
- Find the stack chain: the PR chain whose **top head** is the original branch (if the current branch is
  interior, find the chain containing it; the top is the branch no open PR uses as a base). Interior
  branches = the lower heads. Remember the original/top branch.
- If no PR chain and no local `<branch>-N` refs exist → tell the user to run `/stack create <N>` first.
- `git fetch --prune <remote>`.

### 2. Reconcile merges (if any PR in the chain merged)
- A merged PR's commits are now in the default branch. Drop that branch from the stack and delete it
  locally (`git branch -D`); the remote branch is usually auto-deleted. GitHub has already retargeted the
  next PR. Recompute the chain on the remainder.

### 3. Restack the chain (bottom → top)
- Rebase **each branch onto its parent**, bottom → top: parent = `origin/<default>` for the bottom, else
  the local parent branch you just rebased. `git rebase <parent> <branch>`. This propagates a commit made
  on *any* branch up through its descendants, and is a no-op for branches with nothing new upstream. After
  this pass the top branch holds the full cumulative diff. (`rebase.updateRefs` + `rerere` assist.)
- **On conflict (agent value-add):** read conflicted files, resolve keeping each slice's intent scoped to
  itself, `git add`, `git rebase --continue`. `rerere` records resolutions for next time. If you cannot
  resolve confidently, `git rebase --abort`, report which branch failed, and stop.

### 4. Reconcile PRs
- For any branch in the chain with **no open PR** → create one (`gh pr create --head <b> --base <parent>`).
- For any PR whose `baseRefName` ≠ its parent in the chain → `gh pr edit <n> --base <parent>`.

### 5. Push + finish
- `git pushf <b1> <b2> … <top>` — one `--force-with-lease` push of every branch.
- Return to the **original/top** branch.
- Print the final stack: each PR with ahead/behind vs. its base, draft flag, and URL.

### Rules
- Never rebase, push, or delete the default branch.
- Always `--force-with-lease`, never a bare `--force`.
- If the working tree is dirty before a rebase, `git stash` and restore at the end.
- Print progress per branch so the user can follow along.
