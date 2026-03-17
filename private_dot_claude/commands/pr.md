---
allowed-tools: Bash(git:*), Bash(gh:*), Bash(pre-commit:*), Bash(npx:*), Bash(make:*), Read, Grep, Glob, Edit, Agent
description: Create or babysit a PR — pre-commit, CI fixes, review comments, merge conflicts
argument-hint: "[base-branch]"
---

## Context

- Current branch: !`git branch --show-current`
- Default branch: !`git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
- Git status: !`git status --short`
- Existing PR: !`gh pr view --json number,title,url,baseRefName,statusCheckRollup,reviewDecision,mergeable,mergeStateStatus 2>/dev/null || echo "No PR yet"`
- Recent commits on this branch not on default: !`git log --oneline origin/HEAD..HEAD 2>/dev/null || git log --oneline -5`

## Task

Create a pull request (or pick up an existing one) for the current branch, then monitor it until CI is green, reviews are addressed, and it's mergeable. Base branch override: "$ARGUMENTS"

---

### Phase 1 — Sync with base branch

1. If on main/master and no PR exists, **stop** — tell the user to create a feature branch first.
2. Fetch origin.
3. Merge the base branch (default branch or the one from the existing PR's `baseRefName`) into the current branch:
   ```
   git fetch origin && git merge origin/<base>
   ```
4. **If there are merge conflicts:**
   - Read each conflicted file, understand both sides, and resolve the conflicts.
   - Stage resolved files. Commit the merge.
   - If you can't confidently resolve a conflict, stop and ask the user.

### Phase 2 — Pre-commit, lint & commit

5. If there are uncommitted changes (new work, not just the merge), stage and commit them with a clear message.
6. Run pre-commit / linting before pushing:
   - If a `.pre-commit-config.yaml` exists, run `pre-commit run --all-files`
   - Otherwise check for lint/format scripts in `package.json`, `Makefile`, or similar and run them
   - If pre-commit or linting fails, **read the output, fix the issues, stage, and commit the fixes**. Repeat until clean (max 3 attempts, then stop and report).

### Phase 3 — Push & create PR (if needed)

7. Push the branch to origin (with `-u` if needed).
8. If a PR already exists, skip to Phase 4.
9. If no PR exists, create one with `gh pr create`:
   - Short title (< 70 chars) summarising the branch's commits
   - Body with a `## Summary` section (bulleted) and `## Test plan` section
   - Use the base branch argument if provided, otherwise let gh pick the default
10. Output the PR URL.

### Phase 4 — Monitor CI, reviews & mergeability

Enter a check-fix loop:

11. Wait ~60 seconds for CI to start, then check PR status:
    ```
    gh pr checks <number> --watch --fail-fast
    ```
    If `--watch` is not available, poll with `gh pr checks <number>` every 60s.

12. **If the PR has merge conflicts** (mergeable != MERGEABLE):
    - Pull the base branch and merge again (repeat Phase 1 steps 3-4).
    - Re-run pre-commit (Phase 2 step 6).
    - Push and restart this loop.

13. **If CI fails:**
    - Fetch the failed check's logs: `gh run view <run-id> --log-failed`
    - Read and understand the failure.
    - Fix the issue in code, commit with a message like "fix: <what failed>".
    - Re-run pre-commit (Phase 2 step 6) before pushing.
    - Push and restart this loop.

14. **If there are review comments or changes requested:**
    - Fetch them: `gh pr view <number> --comments` and `gh api repos/{owner}/{repo}/pulls/<number>/comments`
    - Address actionable feedback — fix code, commit, push.
    - Restart this loop.

15. **If CI is green, no merge conflicts, and no unresolved comments**, report success and stop.

16. **Max iterations:** Repeat the check-fix loop up to 5 times. If still failing after 5 rounds, report the remaining issues and stop — don't loop forever.

### Rules

- Do all phases without asking follow-up questions (except unresolvable merge conflicts).
- Each fix should be a separate, clearly-messaged commit (not amended).
- Always re-run pre-commit/lint before every push.
- When reading CI logs, focus on the actual error, not the full log.
- Use agents for parallel investigation if multiple checks fail simultaneously.
- When resolving merge conflicts, prefer preserving both sides' intent. If the conflict is purely mechanical (imports, formatting), auto-resolve. If it's a logic conflict, use the surrounding code and PR context to make the right call.
