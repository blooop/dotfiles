---
allowed-tools: Bash(git:*), Bash(gh:*), Bash(pre-commit:*), Bash(npx:*), Bash(make:*), Read, Grep, Glob, Edit, Agent
description: Create or babysit a PR — pre-commit, CI fixes, review comments, merge conflicts
argument-hint: "[--no-review] [base-branch]"
---

## Context

- Current branch: !`git branch --show-current`
- Default branch: !`git remote show origin | sed -n '/HEAD branch/s/.*: //p'`
- Git status: !`git status --short`
- Existing PR: !`gh pr view --json number,title,url,baseRefName,statusCheckRollup,reviewDecision,mergeable,mergeStateStatus 2>/dev/null || echo "No PR yet"`
- Recent commits on this branch not on default: !`git log --oneline origin/HEAD..HEAD 2>/dev/null || git log --oneline -5`
- Change stats against base: !`git diff --stat origin/HEAD..HEAD 2>/dev/null | tail -1`

## Task

Create a pull request (or pick up an existing one) for the current branch, then monitor it until CI is green, reviews are addressed, and it's mergeable. Base branch override: "$ARGUMENTS" (strip `--no-review` if present — it disables self-review phases but not 3rd-party comment handling).

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

### Phase 2.5 — Self-review before push (new PRs only)

> Skip this phase if `--no-review` was passed or a PR already exists.

7. **Classify change size** from the diff against the base branch (`git diff --stat origin/<base>...HEAD`):
   - Count files changed and total lines (insertions + deletions).
   - Categorise: **Trivial** (≤3 files AND ≤30 lines), **Small** (≤10 files AND ≤200 lines), **Medium** (≤30 files AND ≤500 lines), **Large** (>30 files OR >500 lines).

8. **Run a proportionate review:**

   - **Trivial**: Scan the diff yourself for obvious bugs, style violations, and CLAUDE.md compliance. No agents needed.
   - **Small**: Launch the `code-reviewer` agent on the diff. If error-handling code was modified, also launch `silent-failure-hunter`.
   - **Medium**: Launch applicable agents based on what changed:
     - Always: `code-reviewer`
     - Test files changed → `pr-test-analyzer`
     - New types introduced → `type-design-analyzer`
     - Error handling changed → `silent-failure-hunter`
     - Comments/docs added → `comment-analyzer`
   - **Large**: Same as Medium but launch all applicable agents **in parallel**.

9. **Process review results:**
   - **Critical issues** (confidence ≥ 90): Fix them, stage, commit, re-run pre-commit (step 6).
   - **Important issues** (confidence 80–89): Fix them, stage, commit, re-run pre-commit (step 6).
   - **Suggestions**: Do not block. Include notable suggestions in the PR description body later.
   - This is a **single pass** — do not re-run the review after fixing issues found by the review.

### Phase 3 — Push & create PR (if needed)

10. Push the branch to origin (with `-u` if needed).
11. If a PR already exists, skip to Phase 4.
12. If no PR exists, create one with `gh pr create`:
    - Short title (< 70 chars) summarising the branch's commits
    - Body with a `## Summary` section (bulleted) and `## Test plan` section
    - If the self-review (step 9) produced suggestions, include them in a `## Review notes` section
    - Use the base branch argument if provided, otherwise let gh pick the default
13. Output the PR URL.

### Phase 4 — Monitor CI, reviews & mergeability

Enter a check-fix loop:

14. Wait ~60 seconds for CI to start, then check PR status:
    ```
    gh pr checks <number> --watch --fail-fast
    ```
    If `--watch` is not available, poll with `gh pr checks <number>` every 60s.

15. **If the PR has merge conflicts** (mergeable != MERGEABLE):
    - Pull the base branch and merge again (repeat Phase 1 steps 3-4).
    - Re-run pre-commit (Phase 2 step 6).
    - Push and restart this loop.

16. **If CI fails:**
    - Fetch the failed check's logs: `gh run view <run-id> --log-failed`
    - Read and understand the failure.
    - Fix the issue in code, commit with a message like "fix: <what failed>".
    - Re-run pre-commit (Phase 2 step 6) before pushing.
    - Push and restart this loop.

17. **If there are review comments:**

    Fetch all review comments:
    ```
    gh api repos/{owner}/{repo}/pulls/<number>/comments
    gh api repos/{owner}/{repo}/pulls/<number>/reviews
    ```

    For each unresolved comment thread, determine the author type:

    **Bot / AI comments** (author is a bot, or from known AI reviewers like `github-actions`, `copilot`, `coderabbitai`, `codeclimate`, etc.):
    - If actionable: fix the code, commit, push.
    - If not actionable (false positive, irrelevant): leave a brief reply explaining why it's not being addressed.
    - **Resolve the thread** after responding: `gh api --method PUT repos/{owner}/{repo}/pulls/comments/<comment-id>/resolve` or use the GraphQL API to resolve the review thread.

    **Human comments:**
    - If actionable: fix the code, commit, push, and **reply to the comment** explaining what was changed. Do NOT resolve the thread — let the human reviewer resolve it.
    - If not actionable (disagree, out of scope, or unclear): **reply to the comment** explaining why it's not being addressed or asking for clarification. Do NOT resolve the thread.
    - Reply using: `gh api repos/{owner}/{repo}/pulls/<number>/comments/<comment-id>/replies -f body="<reply>"`

    After fixing code for review comments, run `code-reviewer` agent **scoped to only the files touched by fixes** to verify the fixes don't introduce new issues. If the targeted review finds critical problems, fix and commit before pushing.

    After addressing comments, restart this loop.

18. **Quality gate — self-review before declaring success:**

    > Skip if `--no-review` was passed.

    Before declaring success, when CI is green and no comments are pending, perform a final quality check:

    a. If this HEAD commit was already self-reviewed in this session, skip to step 19.

    b. Classify change size (same as step 7, using `git diff origin/<base>...HEAD`).

    c. **Trivial changes**: Skip the quality gate — go straight to step 19.

    d. **Small/Medium/Large**: Launch the `code-reviewer` agent on the full PR diff against the base branch. Focus the review on:
       - Anything that might have been introduced by fix commits during this session
       - Overall coherence and correctness of the final diff

    e. Process results:
       - **Critical issues found**: Fix, commit, re-run pre-commit, push, and restart this loop.
       - **Suggestions only**: Optionally leave a self-review comment on the PR noting observations, then proceed to step 19.

    f. Mark this HEAD as reviewed so subsequent loop iterations don't re-review the same commit.

19. **If CI is green, no merge conflicts, no unresolved actionable comments, and self-review complete**, report success and stop.

20. **Max iterations:** Repeat the check-fix loop up to 5 times. If still failing after 5 rounds, report the remaining issues and stop — don't loop forever.

### Rules

- Do all phases without asking follow-up questions (except unresolvable merge conflicts).
- Each fix should be a separate, clearly-messaged commit (not amended).
- Always re-run pre-commit/lint before every push.
- When reading CI logs, focus on the actual error, not the full log.
- Use agents for parallel investigation if multiple checks fail simultaneously.
- When resolving merge conflicts, prefer preserving both sides' intent. If the conflict is purely mechanical (imports, formatting), auto-resolve. If it's a logic conflict, use the surrounding code and PR context to make the right call.
- **Review skip**: If `--no-review` is in `$ARGUMENTS`, skip Phase 2.5 and the quality gate (step 18). Strip `--no-review` from arguments before using the remainder as a base branch override. The 3rd-party comment handling (step 17) is never skipped.
