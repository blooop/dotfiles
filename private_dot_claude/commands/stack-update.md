---
allowed-tools: Bash(git:*), Bash(gh:*), Bash(uv:*), Bash(python*:*), Bash(sleep:*), Bash(*stack-tool*), Read, Grep, Glob, Edit, Agent
description: Update a stacked branch chain — merge each base into its child from bottom to top (git-notes topology, no PR required)
argument-hint: "[--init <base> <b1> <b2> ...] | [top-branch]"
---

## Context

- Current branch: !`git branch --show-current`
- Default branch: !`git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
- Git status: !`git status --short`
- Arguments: "$ARGUMENTS"
- Script path: `~/.claude/scripts/stack-tool.py`

## Tool — `stack-tool.py`

A UV-isolated Python script that handles all repeatable git operations. It outputs **JSON** so you can parse results reliably. Located at `~/.claude/scripts/stack-tool.py`.

Commands:

| Command | Purpose |
|---|---|
| `stack-tool.py init <base> <b1> [<b2> ...]` | Attach stack-base notes to each branch tip |
| `stack-tool.py discover [<top-branch>]` | Walk notes chain → ordered stack (bottom-up) |
| `stack-tool.py fetch-notes` | `git fetch origin refs/notes/stack` |
| `stack-tool.py push-notes` | `git push origin refs/notes/stack` |
| `stack-tool.py merge <branch> <base>` | Checkout branch, merge origin/base into it |
| `stack-tool.py move-note <branch> <base>` | Update note to new branch tip after merge |
| `stack-tool.py push-branch <branch>` | Push branch to origin |
| `stack-tool.py status [<top-branch>]` | Show stack with ahead/behind counts |

Run with: `uv run ~/.claude/scripts/stack-tool.py <command> [args...]`

---

## Task

Update a chain of stacked branches so that every branch has its base merged in, from bottom to top. Topology is stored in **git notes** (`refs/notes/stack`), not GitHub PRs.

Parse "$ARGUMENTS" to determine the mode:

- **If arguments start with `--init`**: run Phase 0 (init mode)
- **Otherwise**: run Phases 1–3 (update mode)

---

### Phase 0 — Init mode (`--init <base> <branch1> <branch2> ...`)

Set up the stack topology by attaching git notes to each branch.

1. Run `stack-tool.py init <base> <branch1> <branch2> ...`
2. Parse the JSON output — report any branches that weren't found.
3. Push notes to origin: `stack-tool.py push-notes`
4. Print the configured stack and exit.

---

### Phase 1 — Discover the stack

1. Fetch notes from origin: `stack-tool.py fetch-notes` (ok if it fails on first use)
2. Determine the **top branch**: use the argument if provided, otherwise the current branch.
3. Discover the stack: `stack-tool.py discover [<top-branch>]`
4. Parse the JSON — the `stack` array is ordered bottom-up, each entry has `branch` and `base`.
5. If discovery fails (no notes found), tell the user to run `/stack-update --init` first.
6. Print the discovered stack for confirmation:
   ```
   Discovered stack (bottom → top):
     1. feature-a  (base: main)
     2. feature-b  (base: feature-a)
     3. feature-c  (base: feature-b)  ← current
   ```

### Phase 2 — Update the stack bottom-up

For each entry in the stack array, from first (bottom) to last (top):

7. **Fetch** the latest from origin:
   ```
   git fetch origin <base-branch> <branch>
   ```

8. **Merge** the base into the branch: `stack-tool.py merge <branch> <base>`
   - Parse the JSON result.
   - If `"ok": true` — the merge succeeded, continue to step 9.
   - If `"conflict": true` — **this is where you add value as an agent**:
     a. Read each file listed in `conflicted_files`.
     b. Understand the intent of each side — the base changes vs the branch's own work.
     c. Resolve conflicts keeping the branch's intent isolated (its changes should not bleed into
        unrelated sections, and base updates should flow through cleanly).
     d. `git add` resolved files and `git commit --no-edit` to complete the merge.
     e. If you cannot confidently resolve a conflict, run `git merge --abort`, report the issue, and **stop**.

9. **Move the note** to the new tip: `stack-tool.py move-note <branch> <base>`

10. **Push** the branch: `stack-tool.py push-branch <branch>`

11. Repeat steps 7–10 for the next branch.

### Phase 3 — Finalize

12. Push updated notes: `stack-tool.py push-notes`
13. Check out the original branch the user was on:
    ```
    git checkout <original-branch>
    ```
14. Print a summary:
    ```
    Stack updated:
      ✓ feature-a  merged main, pushed
      ✓ feature-b  merged feature-a, pushed
      ✓ feature-c  merged feature-b, pushed
    ```
    Include any conflicts that were auto-resolved or branches already up-to-date.

### Rules

- **Merge workflow** — never rebase, never force-push. Use `git merge` and regular `git push`.
- If there are uncommitted changes before starting, **stash** them first and restore after.
- Do not merge into or push the default branch.
- If a merge fails and cannot be resolved, abort it, restore the original state, and report clearly which branch failed and why.
- Print progress as you go so the user can follow along.
- When resolving conflicts, prioritize keeping each branch's changes scoped to its own intent — don't let unrelated changes from the base leak into the branch's diff.
- If the stack has only one branch, just merge and push that one branch.
