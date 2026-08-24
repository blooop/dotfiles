---
name: review-self
description: Adversarially review your own branch — try to break the change, prove each defect with a failing test, fix it, and push. Fixes go in as commits, never as PR comments. Use when the user asks to review their own work, a branch they wrote, or uncommitted changes they made, to find and fix problems in what they just wrote, or runs `/review-self [branch|PR]`. Not for a branch someone else wrote: that is `review-other`.
---

# Review your own work

**Read [`~/.claude/review-core.md`](../../review-core.md) first — it is the
review.** What to attack, how to prove a finding, constructive modeling, comment
verbosity, and what counts. `review-other` reads the same file; the review is
identical. This file is only the half that differs: you **fix**, and the commits
are the output.

First person: this is **your** change, so a finding is not something to report,
it is something to fix. Nothing here posts a PR comment.

The argument names the branch or PR. With no argument, use the current branch.

```bash
PR=$(gh pr view "${ARG:-}" --json number -q .number 2>/dev/null)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ -n "$ZELLIJ" ] && zellij action rename-tab "#${PR:-wip} ${BRANCH##*/}"
```

No PR yet is normal — review `git diff origin/HEAD...HEAD` and skip anything
PR-shaped. Creating the PR is `/pr`'s job, not this skill's.

## What you may and may not do

| May | May not |
|---|---|
| Commit fixes on this branch | Post PR comments, reviews, or approvals |
| Add tests | `--amend`, rebase, or `push --force*` — the reviewer needs to see what moved |
| Push | Merge, or open the PR |
| Fix a CI failure your own commits caused | Buy green — skip, xfail, loosen, ignore, or re-run until the flake lands |
| Delete a narrating or stale comment the diff touched | Sweep comments outside the diff |
| Say a defect needs a design decision | Redesign the change to fit your opinion of it |

Never **weaken a test to make it pass**, and never delete a test you cannot
explain. If a test is wrong, the commit message says why in one line.

No drive-by refactors — reuse and tidying are `/simplify`, and mixing them in
buries the fix that mattered. Deleting a comment the diff itself added or
falsified is not a refactor; it is core §4, in scope.

## Attack, prove, fix

Run core §1–§6 over `git diff origin/HEAD...HEAD` as the **two subagents** core
describes, then work their reports here in the parent. The subagents only read;
every fix is yours to commit.

Both reports land as commits, but not the same way. A **Defects** finding becomes a
failing test and a fix. A **Spec** finding is a decision before it is a diff: a
missing requirement you can honestly build gets built and committed like any other
defect, while scope creep you did not add, or a requirement the spec and the code
genuinely disagree about, goes to **Escalate instead of redesigning** below. Deleting
someone's feature because a spec omitted it is not a self-review.

Where the defect is testable — and most are — **write the failing test first**
and run it. Red, then fix, then green. A defect you fixed without ever seeing it
fail is a defect you have not confirmed exists, and the test is what stops it
coming back. Where it is genuinely not testable (a race, a build-level concern),
say so in the commit message rather than inventing a test that passes either way.

One commit per defect: the failing test and its fix together, message naming the
failure rather than the edit — `fix: empty waypoints made front() UB in
clamp()`, not `fix: add check`.

**Add no new narration alongside your own fix.** The failing test is the
explanation; a comment restating the guard you just added is the next stale
comment. Comment only what the test cannot say — a unit, an invariant, or why the
obvious fix was wrong.

Lint only what changed, then run the tests that cover the area — the full suite
if it is cheap, the package if it is not:

```bash
pre-commit run --from-ref origin/HEAD --to-ref HEAD
```

Then push.

## Drive CI green

A red check on your own PR is your defect, and it needs no further proof — the
run *is* the failing test core §2 asks for. Fixing it here is the whole point:
the alternative is a reviewer opening a PR that never built.

No PR yet means no CI; skip this.

```bash
gh pr checks "$PR" --watch --fail-fast
gh run view <run-id> --log-failed
```

Read the actual error, not the whole log.

**Establish it is yours before you fix it.** Check whether the same job is
already red on `origin/HEAD`. A failure that predates your branch is not yours to
fix inside a self-review — fixing it here buries your change in someone else's
and makes the diff unreviewable. Name it in the report and leave it. A failure
that appears only with your commits is a finding, and goes in as its own commit
named for what failed: `fix: clamp() test failed on empty waypoints in CI`.

**Never buy green.** No skipping a test, loosening an assertion, widening a
tolerance, adding a lint ignore or `# type: ignore`, marking something `xfail`,
or re-running until the flake lands. This is the same bar as never weakening a
test to make it pass, and CI is where the temptation is strongest because the
failure is someone else's problem until it is green. If a check is genuinely
wrong, the commit message says why in one line.

A flake is itself a finding — a test that passes or fails on the same commit is
a defect in the test. Report it with the run URL instead of re-running until it
cooperates.

Max three rounds, then stop and report what is still red. A check that fails
three times the same way is not going to yield to a fourth guess.

**Not `/pr --watch`, and not `/respond`.** Only the checks: no merge with base,
no PR creation, and no replies to review threads — including the bots that
comment on CI failures. Posting is still forbidden. A merge conflict blocking
the checks stops here and goes in the report; resolving it is `/pr`'s job.

## Escalate instead of redesigning

A real defect whose only honest fix is a different design — a schema break, an
API change, a different concurrency model — **stops at a report**. Fix everything
else, then say plainly what is left, why the small fix would be a lie, and what
the options are. Guessing at a redesign inside a self-review is how a review
turns into a rewrite nobody asked for.

## Report

Per defect: the failure, the test that now covers it, the commit. Say which axis
found it, and say plainly whether the Spec axis ran at all or reported no spec
available. Then the CI state you left behind — green, or what is still red and whether it was yours.
Then what you attacked and found solid — a self-review that lists only wins hides how much of
the change was actually examined — and anything escalated above.
