---
name: approve
description: Approve the PR under review once this session's agentic review is posted on it. `/approve [PR...]`
disable-model-invocation: true
---

# Approve after the review posts

The user typed `/approve` while this session reviews a PR (`review-other`,
`review-dl`, `code-review --comment`, `wf-review`, or a plain "review this").
They read the PR by hand while you review, and they want their approval to land
**after** your review, never before it. The decision to approve is made: this
skill is the human's call that the review skills reserve for them. It changes
the end of the review, not the review itself.

**Targets:** the PRs named in the argument (number, URL or branch). With no
argument, every PR this session reviews.

## 1. Finish the review, unchanged

Run the review to its own completion criterion, with the same rigour as before
`/approve` arrived. The approval waits on the review; the review never rushes
for the approval. A review that a subagent runs (a `review-dl` worker, a
background axis) finishes when its final report arrives: wait for that
notification, and treat an interim "still waiting" as a stall to resume.

## 2. Prove the review is posted

The gate is the review on GitHub, not your memory of posting it. For each PR:

```bash
me=$(gh api user --jq .login)
gh api "repos/{owner}/{repo}/pulls/$PR/reviews" \
  --jq "[.[] | select(.user.login==\"$me\")] | last | {id, state, submitted_at, html_url}"
```

The gate is open when that review is the one this session posted (its
`submitted_at` falls after the review started, its `html_url` matches what the
post returned). A review that posted nothing still posts its summary (see
`review-other` §2), so every finished review leaves one. No review on GitHub
means the post failed: fix the post, then come back here.

## 3. Check what an approval sets off

```bash
gh pr view "$PR" --json author,autoMergeRequest,reviewDecision,body,comments
```

- **The user wrote the PR:** GitHub refuses a self-approval. Report it and stop.
- **Auto-merge is on:** the approval can merge the PR at once. Read the body and
  the comments for a hold note ("hold", "wait until", "do not merge"). A hold
  note parks the PR as ⛔ with the question to the user. No hold note: approve.
- **The user already approved this head:** skip it and say so.

## 4. Approve

```bash
gh pr review "$PR" --approve
```

Send it with no body: the review above carries the findings. Approve even when
the review posted findings. The user saw the PR themselves and chose to approve;
the findings stay on the PR for the author.

## 5. Report

One bullet per PR, link first: the review link, the comment count, the approval
link (or why there is none). Put any finding the review rated a correctness
defect in that bullet, so the user can dismiss the approval if they disagree.
