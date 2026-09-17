---
name: review-self
description: "Adversarially review your own branch — try to break the change, prove each defect with a failing test, fix it, and push. Fixes go in as commits, never as PR comments. Use when the user asks to review their own work, a branch they wrote, or uncommitted changes they made, to find and fix problems in what they just wrote, or runs `/review-self [branch|PR|stack]`. Not for a branch someone else wrote: that is `review-other`."
---

# Review your own work

**Read [review-core.md](references/review-core.md) first — it is the
review.** What to attack, how to prove a finding, constructive modeling, comment
verbosity, and what counts. `review-other` reads the same file; the review is
identical. This file is only the half that differs: you **fix**, and the commits
are the output.

First person: this is **your** change, so a finding is not something to report,
it is something to fix. Nothing here posts a PR comment.

The argument names the branch, the PR, or a stack of PRs. With no argument, use
the current branch.

```bash
PR=$(gh pr view "${ARG:-}" --json number -q .number 2>/dev/null)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ -n "$HERDR_ENV" ] && herdr tab rename "$HERDR_TAB_ID" "#${PR:-wip} ${BRANCH##*/}"
[ -n "$ZELLIJ" ] && zellij action rename-tab "#${PR:-wip} ${BRANCH##*/}"
```

No PR yet is normal — review `git diff origin/HEAD...HEAD` and skip anything
PR-shaped. Open one only if asked; `/pr` does that with a babysit attached.

## The parent stays thin

This skill costs what the parent context costs. Measured over 35 runs: the parent
spent ~150 turns at ~200k tokens each, and 80% of every review was the parent
re-reading its own context — not the subagents. So the rule here is mechanical:
**the parent never edits a file, never runs a test, and never waits.** It reads
reports, ranks, briefs agents, and writes the final report. Everything else
happens in a subagent with a fresh context and a short return.

Every subagent brief carries the **runner** — the exact command that builds and
tests this repo, from its CLAUDE.md or README. A subagent that has to rediscover
the runner burns the tokens this rule exists to save, and one that cannot find it
will report "could not run the tests" as if that were a result.

## Stacks

A PR is in a stack when its `baseRefName` is not the default branch, or when its
head is another open PR's base. GitHub is the source of truth for topology, the
same as `/stack`:

```bash
gh pr list --state open --json number,headRefName,baseRefName -L 100
```

Walk the chain both ways from the PR you were given. Then review the PRs
**serially, bottom to top, one review-self subagent per PR**, in the one
checkout. Serial is the default because a stack's reviews are not independent:
a fix on PR 2 changes the base PR 3 is reviewed against, and running them in
parallel means paying for a review of code that is about to move. It also costs
N parallel contexts at once; a stack is expensive enough already.

Each agent reviews **its PR's own diff** — `git diff origin/<its base>...<its
head>` — never the cumulative diff from the top, or every PR re-finds the bottom
one's defects. Its brief is this file, the PR number and base, and the runner;
its return is the per-PR report below, ≤300 words. Fixes land on each PR's own
branch, so the diff a reviewer sees stays scoped to that PR.

**Restack as you go.** When PR N's agent returns with fixes committed, every
branch above it is now behind. Before starting PR N+1, rebase the descendants
onto the fixed branch, bottom to top, and push each with `--force-with-lease` —
the same walk `/stack sync` does, and the one place this skill rewrites history:

```bash
git rebase <fixed branch> <next branch>   # then the one above that, and so on
git push --force-with-lease origin <next branch> ...
```

A restack replays the same commits onto a new base; GitHub re-anchors review
comments to hunk content, so comments on lines the fix did not touch survive. On
a conflict, `resolving-merge-conflicts`, changing only the minimal lines — and if
it cannot be resolved confidently, `git rebase --abort`, name the branch in the
report, and stop the walk there. Never rebase the default branch.

Only the **bottom** PR merges the default branch (**Merge base** below); the
rest receive it through the restack. Parallel is available on explicit request,
one worktree per PR so the agents do not trample each other's checkout, and the
restack then happens once at the end instead of between PRs — say which ran.

## What you may and may not do

| May | May not |
|---|---|
| Commit fixes on this branch | Post PR comments, reviews, or approvals |
| Add tests | `--amend` or rewrite a fix commit — the reviewer needs to see what moved. The one allowed rewrite is restacking a stack's descendants (**Stacks**) |
| Push | Merge, or open the PR |
| Fix a CI failure your own commits caused | Buy green — skip, xfail, loosen, ignore, or re-run until the flake lands |
| Delete a narrating or stale comment the diff touched, and every copy of a claim the diff falsified (core §4) | Sweep comments outside the diff for anything else |
| Say a defect needs a design decision | Redesign the change to fit your opinion of it |
| Brief a fix agent and commit what it returns | Fix, test, or wait in the parent context |

Never **weaken a test to make it pass**, and never delete a test you cannot
explain. If a test is wrong, the commit message says why in one line.

No drive-by refactors inside the fix commits — reuse and tidying are
`/simplify`'s, and it runs only when the invocation asks for it (**Simplify —
only when asked** below). Mixing the two buries the fix that mattered. Deleting a comment the diff itself added or
falsified is not a refactor; it is core §4, in scope.

## Attack, prove, fix

Run core §1–§7 over `git diff origin/HEAD...HEAD` as the **four subagents** core
describes — Defects, Types, Spec, Tests — all in one message so they run
concurrently.
The parent then ranks their reports (core §7, correctness first) and dispatches
**one fix agent per finding, serially**, each in a fresh context. Serial because
they all commit to the same branch in the same checkout; the concurrency win was
the review fan-out, and the win here is that a 20-turn fix loop never lands in
the parent's context. Types and Tests both run on every review, so there is
always a §3 and a §6 report to work — even on a diff that declares no new type and
adds no test.

A fix agent's brief is: the finding as core §2 states it (input → wrong result,
file:line), the diff command, the runner, and the rules from this section — red
before green, one commit, no narration, never weaken a test, nothing outside the
finding. It returns ≤150 words: the test it wrote and saw fail, the commit SHA,
and anything it could not do. It never touches a second finding it noticed on
the way — that goes back to the parent as one line, and the parent decides.

All four reports land as commits, but not the same way. A **Defects** finding
becomes a failing test and a fix. A **Tests** finding is the one that lands
without a red step to precede it: the missing test is the commit, written to the
cases §6 named, and the proof is that it passes on this branch and fails with the
fix reverted — check that, because a new test that passes either way pins nothing.
Where a Tests finding and a Defects finding turned out to be one defect, they are
one commit: the regression test and the guard together. A test-selection finding
(the marker, the ini line, the justification that does not hold) is a fix to the
comment or the gate, committed on its own and named for the claim it corrected. A **Spec** finding is a decision before it is a diff: a
missing requirement you can honestly build gets built and committed like any other
defect, while scope creep you did not add, or a requirement the spec and the code
genuinely disagree about, goes to **Escalate instead of redesigning** below. Deleting
someone's feature because a spec omitted it is not a self-review.

A **Types** finding is the one exception to one-commit-one-test. The subagent
reported it in Review mode, so brief a fix agent to run `constructive-modeling` in
*Apply* mode over what it named, and let the compiler be the proof — the illegal state is gone when
the code that constructed it no longer compiles. Where the language cannot enforce
it, the failing test asserting the bad construction is rejected is the proof
instead. Same bar otherwise: one commit, named for the state it removed —
`fix: Waypoint could carry a tag with no matching payload`.

Apply mode changes types, so it is the one place a fix can spread past the diff:
every construction site has to move with the shape. That is in scope and is not a
drive-by refactor — but if the blast radius turns out to be a schema break or a
public API change, it stops at **Escalate instead of redesigning** below like any
other finding whose honest fix is a different design.

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

Each fix agent lints only what it changed and runs the tests that cover the area
— the full suite if it is cheap, the package if it is not. The whole branch gets
one more gate after **Merge base** below, so the push is not the first time the
fixes have met each other, or met `main`.

## Simplify — only when asked

**Do not run `/simplify` as part of a review.** It runs only when the invocation
says so — `/review-self and simplify`, `/review-self before marking ready`, or
the user asking for it in as many words. Silence means it does not run, and the
report says the Standards axis did not run rather than treating it as optional
polish you skipped.

It is gated because it is the most expensive thing this skill can do. Measured
over seven runs on 2026-09-16: **~14M tokens and 11–26 minutes each**, 12% of
that day's entire spend, effectively all of it in `/simplify`'s own four parallel
cleanup agents. That is a real pass worth running before a human opens the PR,
and pure waste on a mid-stack review nobody is reading yet.

When it does run: **on the parent's model, which is Opus** — nested agents
inherit, and the four cleanup agents are the pass, so downgrading them is
downgrading the result. Run it after the fix commits are in, over the same diff,
from a **single subagent** so its apply step does not land in the parent context.

This is the Standards axis — reuse, duplication, dead code, altitude — and it
lives here on purpose: on your own branch a quality finding is a cheap commit,
while on a colleague's PR it is a comment that displaces a real defect. So
`review-other` never raises it, core §7 refuses it as a *finding*, and this is
the one place it gets applied.

Its commits stay separate from the fix commits, named for what they removed
(`refactor: fold the two waypoint clamps into one`), so a reviewer can tell what
changed behaviour from what tidied it. Same bar as the fixes: no test weakened,
nothing outside the diff swept. Lint again if it touched anything.

## Merge base

The last thing before the push is bringing the base branch in, so what CI builds
is what will merge, and so a reviewer never opens a PR that is already behind:

```bash
BASE=$(gh pr view "$PR" --json baseRefName -q .baseRefName 2>/dev/null || git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')
git fetch origin && git merge "origin/$BASE"
```

A **merge**, never a rebase of your own branch — the fix commits stay where the
reviewer can see them. On conflict, `resolving-merge-conflicts`: mechanical
conflicts resolve, logic conflicts read both sides and the PR body, and one you
cannot resolve confidently stops here and goes in the report. Commit the merge.

Then one agent runs the **whole gate** over the branch — lint on what changed,
the tests that cover the area, the build if the repo has one:

```bash
pre-commit run --from-ref "origin/$BASE" --to-ref HEAD
```

This runs *after* the merge on purpose. A conflict-free merge can still break
the build — two clean sides can redeclare the same symbol — and the gate is
where that shows up, not the reviewer's checkout. Then push.

In a stack this happens on the bottom PR only; the branches above get it through
the restack. No PR yet means the base is the default branch; everything else is
the same.

## Drive CI green

A red check on your own PR is your defect, and it needs no further proof — the
run *is* the failing test core §2 asks for. Fixing it here is the whole point:
the alternative is a reviewer opening a PR that never built.

No PR yet means no CI; skip this.

**Never wait in the parent.** Across those 35 runs, 380 turns — 6% of every
review token — were `sleep`, `until`, and `--watch` loops re-reading a 200k
context to learn nothing had changed. Run the watch as a background Bash and let
the single completion notification wake you:

```bash
# Bash tool with run_in_background=true — exits on the first failure or when all are green
gh pr checks "$PR" --watch --fail-fast
```

No `sleep`, no `until`, no polling turns between. If a notification cannot reach
you, one `gh pr checks "$PR"` every ≥5 minutes is the floor, not `--watch` in the
foreground. When it fires red, brief a fix agent with the failed job's log:

```bash
gh run view <run-id> --log-failed
```

It reads the actual error, not the whole log.

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

**Not `/respond`, and not an open-ended babysit.** Three rounds on your own
checks, then stop: no replies to review threads — including the bots that
comment on CI failures — and no PR creation. Posting is still forbidden. The base
was merged once, above; if it has moved again by the time the checks finish, say
so rather than looping. Minding a PR until it is green *and* answered *and*
current is `/pr --watch`'s job, and it is a different, longer session.

## Escalate instead of redesigning

A real defect whose only honest fix is a different design — a schema break, an
API change, a different concurrency model — **stops at a report**. Fix everything
else, then say plainly what is left, why the small fix would be a lie, and what
the options are. Guessing at a redesign inside a self-review is how a review
turns into a rewrite nobody asked for.

## Report

For a stack, one block per PR, bottom to top, with the restack that followed each
— or the branch where the walk stopped. Per defect: the failure, the test that now covers it, the commit.
Then, if `/simplify` was asked for, what it changed in one line — and if it was
not, say the Standards axis did not run, so nobody reads its silence as a clean
bill. Say which of the
four axes found each defect, name the Types findings you applied and any you escalated,
say what Tests added — the cases you wrote and any coverage gap you left open — and
say plainly whether the Spec axis ran at all or reported no spec available. Then the merge — clean, or what conflicted and how it was resolved — and the CI state you left behind — green, or what is still red and whether it was yours.
Then what you attacked and found solid — a self-review that lists only wins hides how much of
the change was actually examined — and anything escalated above.
