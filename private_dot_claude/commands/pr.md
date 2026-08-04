---
allowed-tools: Bash(git:*), Bash(gh:*), Bash(pre-commit:*), Bash(npx:*), Bash(make:*), Read, Grep, Glob, Edit, Agent
description: Create a PR (fast). With --watch, babysit it to green — CI fixes, review comments, conflicts
argument-hint: "[--watch] [--no-review] [base-branch]"
---

## Context

- Branch: !`git branch --show-current`
- Base: !`git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || echo main`
- Status: !`git status --short`
- Commits ahead of base: !`git log --oneline origin/HEAD..HEAD 2>/dev/null || git log --oneline -5`
- Diff stat: !`git diff --stat origin/HEAD..HEAD 2>/dev/null | tail -1`
- Existing PR: !`gh pr view --json number,url,baseRefName,mergeable,reviewDecision 2>/dev/null || echo "none"`

## Task

Get the current branch onto a pull request, then **stop and report the URL**.

Flags in "$ARGUMENTS" (strip them; any remainder is a base-branch override):

- `--watch` — after the PR is up, run step 5 (babysit to green). Without it, **do not wait on CI**.
- `--no-review` — skip step 3.

Do all of this without asking follow-up questions, except for a merge conflict you can't confidently resolve. Each fix is its own commit — never amend.

### 1. Sync with base

If on the base branch itself with no PR, stop and tell the user to branch first.

`git fetch origin && git merge origin/<base>` (base = the existing PR's `baseRefName`, else the override, else the detected base). On conflict: read both sides, resolve, commit the merge. Mechanical conflicts (imports, formatting) auto-resolve; logic conflicts use surrounding code and PR context. If genuinely ambiguous, stop and ask.

### 2. Lint & commit

Stage and commit any uncommitted work with a clear message. Then lint **only what changed** — never `--all-files`, it's minutes on a large repo:

```
pre-commit run --from-ref origin/<base> --to-ref HEAD
```

No `.pre-commit-config.yaml`? Use the lint/format script from `package.json` or `Makefile`, scoped to the changed files if it takes paths. Fix failures, commit, retry — max 3 attempts, then report and stop.

### 3. Self-review — one pass only

Skip if `--no-review`, if a PR already exists, or if the diff is ≤3 files and ≤30 lines.

Review `git diff origin/<base>...HEAD` for bugs, silent failures, CLAUDE.md violations, and test gaps. Do it yourself inline. Only for a genuinely large diff (>30 files or >500 lines) split it across parallel `general-purpose` agents by area — and check the subagent type exists before naming anything else.

Fix what you're confident is wrong (commit, re-lint). Everything speculative goes in the PR body under `## Review notes` instead — don't fix it. **Do not re-review after fixing.**

### 4. Push & create

Push (`-u` if needed). If a PR exists, print its URL and stop unless `--watch`.

Otherwise `gh pr create` with a title under 70 chars, a bulleted `## Summary`, a `## Test plan`, and `## Review notes` if step 3 produced any. Use the base override if given. Print the URL.

**Without `--watch`, you are done here.** Say whether CI was still pending.

### 5. Babysit (`--watch` only)

Loop, max 5 rounds:

1. `gh pr checks <number> --watch --fail-fast` (poll every 60s if `--watch` is unsupported).
2. **Not mergeable** → redo step 1, re-lint, push, restart.
3. **CI red** → `gh run view <run-id> --log-failed`, focus on the actual error not the whole log, fix, commit `fix: <what failed>`, re-lint, push, restart. Fan out with agents only if several checks fail for unrelated reasons.
4. **Review comments** → `gh api repos/{owner}/{repo}/pulls/<number>/comments` and `.../reviews`. For each unresolved thread:
   - **Bots** (`github-actions`, `copilot`, `coderabbitai`, …): fix if actionable, else reply why not. Either way **resolve the thread** (GraphQL `resolveReviewThread`).
   - **Humans**: fix and reply saying what changed, or reply explaining why not / asking for clarification. **Never resolve a human's thread** — that's theirs.
   - Reply: `gh api repos/{owner}/{repo}/pulls/<number>/comments/<comment-id>/replies -f body="<reply>"`
   
   Re-lint, push, restart.
5. Green, mergeable, nothing unresolved → report success and stop.

After 5 rounds, report what's still broken and stop. Third-party comment handling still applies under `--no-review`.
