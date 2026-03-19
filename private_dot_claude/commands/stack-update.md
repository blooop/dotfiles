---
allowed-tools: Bash(git:*), Bash(gh:*), Bash(sleep:*), Read, Grep, Glob, Edit, Agent
description: Update a stacked PR chain — rebase each branch onto its updated base from bottom to top
argument-hint: "[top-branch]"
---

## Context

- Current branch: !`git branch --show-current`
- Default branch: !`git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
- Git status: !`git status --short`
- Top branch override: "$ARGUMENTS"

## Task

Update a chain of stacked PRs so that every branch in the stack is rebased onto its freshly-updated base, from the bottom of the stack to the top. The target branch is the current branch (or the branch given as argument).

---

### Phase 1 — Discover the stack

1. Determine the **top branch**: use the argument if provided, otherwise the current branch.
2. Walk the PR chain downward to build an ordered list of branches:
   - For the top branch, run:
     ```
     gh pr view <branch> --json baseRefName,headRefName -q '.baseRefName'
     ```
   - Record the branch and its base. Then repeat for the base branch.
   - **Stop** when the base is the repository's default branch (main/master/develop) or when there is no open PR for a branch.
3. The result is an ordered list from **bottom** (closest to default branch) to **top** (the target branch). Example:
   ```
   default ← feature-a ← feature-b ← feature-c  (target)
   stack = [feature-a, feature-b, feature-c]
   ```
4. Print the discovered stack to the user for confirmation before proceeding. Format:
   ```
   Discovered stack (bottom → top):
     1. feature-a  (base: main)
     2. feature-b  (base: feature-a)
     3. feature-c  (base: feature-b)  ← current
   ```

### Phase 2 — Update the stack bottom-up

For each branch in the stack, from bottom to top:

5. **Fetch** the latest from origin:
   ```
   git fetch origin <base-branch> <branch>
   ```
6. **Check out** the branch:
   ```
   git checkout <branch>
   ```
7. **Rebase** onto the updated base:
   ```
   git rebase origin/<base-branch>
   ```
   - If the base branch was earlier in the stack (and therefore just updated & pushed by us), rebase onto `origin/<base-branch>` (which we just pushed).
   - If the base is the default branch, rebase onto `origin/<default>`.

8. **If rebase conflicts occur:**
   - Read each conflicted file and resolve the conflicts.
   - `git add` the resolved files and `git rebase --continue`.
   - If you cannot confidently resolve a conflict, **abort** the rebase (`git rebase --abort`), report the issue, and stop.

9. **Force-push** the rebased branch (with lease for safety):
   ```
   git push --force-with-lease origin <branch>
   ```

10. **Update the PR base** if needed. After rebasing, the PR's base ref should still be correct, but verify:
    ```
    gh pr view <branch> --json baseRefName -q '.baseRefName'
    ```
    If the base ref doesn't match the expected base branch, update it:
    ```
    gh pr edit <branch> --base <correct-base>
    ```

11. Move to the next branch in the stack and repeat steps 5–10.

### Phase 3 — Return to target branch

12. Check out the original top branch (or the branch the user was on before):
    ```
    git checkout <top-branch>
    ```
13. Print a summary:
    ```
    Stack updated successfully:
      ✓ feature-a  rebased onto main, pushed
      ✓ feature-b  rebased onto feature-a, pushed
      ✓ feature-c  rebased onto feature-b, pushed
    ```
    Include any conflicts that were auto-resolved or branches that were already up-to-date.

### Rules

- Always use `--force-with-lease` (never `--force`) when pushing rebased branches.
- If there are uncommitted changes on any branch before starting, **stash** them first and restore after.
- Each branch in the stack must have an open PR — branches without PRs are skipped with a warning.
- Do not rebase or push the default branch.
- If a rebase fails and cannot be resolved, abort it, restore the original state, and report clearly which branch failed and why.
- Print progress as you go so the user can follow along.
- If the stack has only one branch (a single PR against the default branch), just rebase and push that one branch.
