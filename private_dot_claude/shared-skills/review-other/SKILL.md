---
name: review-other
description: "Adversarially review someone else's pull request — hunt the input that breaks the change, try to refute each finding before posting, and post only high-value inline comments — real defects, not style. Never edits the branch under review. Use when asked to review a PR, branch, or work that someone else wrote, or when the user runs `/review-other [branch|PR]`. Not for your own branch: that is `review-self`."
---

# Review a colleague's PR

**Read [review-core.md](../review-self/references/review-core.md) first — it is the
review.** What to attack, how to prove and refute a finding, constructive
modeling, comment verbosity, and what counts. `review-self` reads the same file;
the review is identical. This file is only the half that differs: you **comment**,
and the PR review is the output.

Someone else wrote this. Your output is comments on their PR, and nothing else.
The bar is high on purpose: a review of twelve nitpicks and one real bug gets the
real bug ignored. Reuse, duplication, and dead code are not comments here at all
— that axis is `review-self`'s `/simplify` pass, on the author's own branch.

The argument names the PR — a branch name, a number, or a URL. With no argument,
use the current branch.

## Read-only

You are running with write access to a real checkout — in an `aid` container,
already on their branch. Do not use it.

- **No** edits, commits, pushes, rebases, or force-pushes.
- **No** `gh pr merge`, `gh pr close`, `gh pr edit`.
- **No** `gh pr review --approve` / `--request-changes`. Approving is the
  human's call. Post the review as `event: COMMENT`.

Building and running tests is fine and encouraged — that is reading, and a
failing test you can reproduce is the strongest comment there is. Leave the tree
clean afterwards.

## 1. Set up, then run the core review

```bash
PR=$(gh pr view "${ARG:-}" --json number -q .number)
BRANCH=$(gh pr view "$PR" --json headRefName -q .headRefName)
[ -n "$HERDR_ENV" ] && herdr tab rename "$HERDR_TAB_ID" "#$PR ${BRANCH##*/}"
[ -n "$ZELLIJ" ] && zellij action rename-tab "#$PR ${BRANCH##*/}"
```

Name the tab first: the title Claude generated is frozen from the first prompt
and cannot carry a number you had to look up, and a screenful of review sessions
all called `Review this PR` is the problem this solves. An explicit rename pins
the tab. Both multiplexers are guarded so whichever one you are in fires; an
`aid` container sets neither and has no socket to the host, so both are no-ops.

```bash
gh pr view "$PR" --json title,body,baseRefName,files,reviews
git fetch origin && git diff origin/<base>...HEAD
```

Then run core §1–§7 over that diff as the **five subagents** core describes —
Defects, Types, Spec, Tests, Mutant — in one message, and aggregate their reports
here. Mutant edits only its own worktree (core §6a), so the read-only rule above
still holds for this checkout.

## 2. Post one review, not N comments

Every comment states the failure concretely — the input or sequence, and the
wrong result — and stays short: the defect, the consequence, and a suggested fix
only if it fits on one line. A wrong comment on a colleague's PR costs them a
round-trip and costs you the next comment's credibility, so an unrefuted-but-
unproven hunch is worth less than silence.

Batch everything into a single review so it arrives as one notification:

```bash
gh api repos/{owner}/{repo}/pulls/$PR/reviews --input - <<'JSON'
{"event":"COMMENT",
 "body":"<2-3 lines: what the change does, and the one thing that matters most>",
 "comments":[
   {"path":"src/foo.cpp","line":214,"side":"RIGHT","body":"..."}
 ]}
JSON
```

`line` is a line in the **post-image** of the diff; a line the diff does not
touch cannot carry an inline comment, so raise it in the summary body instead.
For a multi-line span add `start_line`.

**Types findings are suggestions, never edits.** The axis runs on every review
(core §3), and here its output is a comment: the state the change now permits, the
field or argument combination that reaches it, and the shape that would make it
unrepresentable — a sum type, a non-empty type, a parsed value instead of a
validated one. Sketch the shape in one or two lines if it fits; never apply it, and
never open a patch or a suggested-change block that rewrites their types for them.
That is the author's call to make, and on someone else's PR the read-only rule above
is not negotiable.

A Types finding earns an inline comment when you can anchor it to the declaration
or the call site in the post-image, and it queues under correctness in the cap
below. One you cannot tie to a state the code can actually reach is not a finding —
"this could be a sum type" with no reachable illegal state is preference dressed as
a rule, and §7 refuses it.

**Tests findings anchor to the fixture, not to the production line.** A missing
test comments where the test should have been — the fixture override, the
`TEST_F` next to the gap, the assertion that passes on zero — and names the cases
to write: input, the branch it reaches, the assertion. Naming them is what makes
the comment actionable; "this needs tests for the rate limiter" is not a review
comment. A test-selection finding anchors to the marker, the ini line, or the
conftest hunk, and quotes the justification it refutes. A surviving mutant
(core §6a) anchors to the test that let it survive, and quotes the mutant as a
one-line diff: the author can re-run it in one step.

Where a Tests finding and a Defects finding are the same defect (core §6), post
**one** comment covering both, on whichever line the author has to change. Two
comments describing one bug from two angles read as two reviewers who did not talk
to each other, and each one costs the other its weight.

**Spec findings usually have no line.** A requirement the diff never implements
anchors to nothing, so it belongs in the summary body, named as a spec gap and
quoting the spec line. Only a spec finding you can point at a hunk — behaviour that
is present and wrong, or scope creep you can highlight — earns an inline comment,
and it still queues behind correctness in the cap below.

**Cap it at six inline comments.** More than six means either the PR is a
mess — say so in the body and name the top six — or your bar slipped. Rank
correctness above everything: comment-verbosity findings (core §4) travel as one
line in the summary body, never as an inline comment that displaces a real
defect.

The sixth slot came in with the Tests axis (core §6); it is not a loosened bar. A
fourth axis with no more room to post is an axis that can only displace one of the
other three, and the first thing a full cap drops is the finding with no line to
hang it on — which is most of what Tests finds.

**Nothing qualifying? Post the summary alone**, saying what you checked and that
you found nothing blocking. That is a real review result, and a short one is
more credible than a padded one. Never invent a comment to look thorough.

## 3. Report

Print the review URL, the comment count, what each of the five axes returned — the mutant and whether it was killed,
including whether the Spec axis ran or reported no spec available — and anything you
deliberately left out and why.
