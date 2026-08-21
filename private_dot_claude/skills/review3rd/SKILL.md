---
name: review3rd
description: Adversarially review someone else's pull request — hunt the input that breaks the change, try to refute each finding before posting, and post only high-value inline comments — real defects, not style. Never edits the branch under review. Use when asked to review a PR, a branch, or a colleague's work, or when the user runs `/review3rd [branch|PR]`.
---

# Review a colleague's PR

**Read [`~/.claude/review-core.md`](../../review-core.md) first — it is the
review.** What to attack, how to prove and refute a finding, constructive
modeling, comment verbosity, and what counts. `review1st` reads the same file;
the review is identical. This file is only the half that differs: you **comment**,
and the PR review is the output.

Someone else wrote this. Your output is comments on their PR, and nothing else.
The bar is high on purpose: a review of twelve nitpicks and one real bug gets the
real bug ignored.

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
[ -n "$ZELLIJ" ] && zellij action rename-tab "#$PR ${BRANCH##*/}"
```

Name the tab first: the title Claude generated is frozen from the first prompt
and cannot carry a number you had to look up, and a screenful of review sessions
all called `Review this PR` is the problem this solves. An explicit rename pins
the tab, and the attention plugin still composes its `⏳`/`✅` on top. Unset
`$ZELLIJ` — an `aid` container has no socket to the host — makes it a no-op.

```bash
gh pr view "$PR" --json title,body,baseRefName,files,reviews
git fetch origin && git diff origin/<base>...HEAD
```

Then run core §1–§5 over that diff.

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

**Cap it at five inline comments.** More than five means either the PR is a
mess — say so in the body and name the top five — or your bar slipped. Rank
correctness above everything: comment-verbosity findings (core §4) travel as one
line in the summary body, never as an inline comment that displaces a real
defect.

**Nothing qualifying? Post the summary alone**, saying what you checked and that
you found nothing blocking. That is a real review result, and a short one is
more credible than a padded one. Never invent a comment to look thorough.

## 3. Report

Print the review URL, the comment count, and anything you deliberately left out
and why.
