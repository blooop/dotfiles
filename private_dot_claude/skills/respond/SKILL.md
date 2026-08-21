---
name: respond
description: Address every unresolved review comment on a pull request — fix the code, push, and reply inline to each thread saying what changed. Use when the user asks to address, respond to, or reply to review comments, or runs `/respond [branch|PR]`.
---

# Respond to review

Take a PR from "has review comments" to "every thread answered, fixes pushed".
One pass, no questions, no waiting on CI.

The argument names the PR — a branch name, a number, or a URL. With no argument,
use the current branch. `git rev-parse --abbrev-ref HEAD` when in doubt; inside
an `aid` container the checkout is already on the right branch.

```bash
PR=$(gh pr view "${ARG:-}" --json number -q .number)
BRANCH=$(gh pr view "$PR" --json headRefName -q .headRefName)
```

Then name the zellij tab, so a screenful of `aid` sessions is tellable apart:

```bash
[ -n "$ZELLIJ" ] && zellij action rename-tab "#$PR ${BRANCH##*/}"
```

The title Claude generates is fixed from the first prompt and cannot carry a
number you had to look up, which is why this happens here rather than there. An
explicit `rename-tab` pins the tab out of auto-follow, and the attention plugin
still composes its `⏳`/`✅` onto whatever the tab is called. Unset `$ZELLIJ` —
an `aid` container, which has no socket to the host — makes it a no-op, so name
the tab host-side there instead.

## 1. Collect the threads

Review comments are **threads**, and the REST comment list cannot tell you which
are already resolved. Ask GraphQL:

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$pr:Int!){
  repository(owner:$owner,name:$repo){ pullRequest(number:$pr){
    reviewThreads(first:100){ nodes{
      id isResolved isOutdated path line
      comments(first:20){ nodes{ databaseId author{login} body } } } } } }
}' -F owner="{owner}" -F repo="{repo}" -F pr="$PR"
```

Also read the review bodies (`gh pr view $PR --json reviews`) — a request for
changes often lives there rather than on a line.

Work only `isResolved: false`. An `isOutdated` thread still counts: the code
moved, the point may not have. Read the current file before deciding.

## 2. Triage each thread

Three outcomes, and pick one per thread before touching any code:

| | When | What you owe the thread |
|---|---|---|
| **Fix** | The comment is right, or right enough that arguing costs more than changing | The change, plus a reply naming it |
| **Push back** | The comment is wrong, or based on something the diff does not do | A reply with the reason. Do not change the code to make a comment go away |
| **Ask** | Genuinely ambiguous, and both readings imply different code | A reply asking the one question that separates them |

Never silently skip a thread. Every unresolved thread gets a reply.

## 3. Fix

One commit per theme, never one commit per comment when several comments point
at the same defect. Never amend — the reviewer needs to see what moved since
they looked.

Lint only what changed:

```bash
pre-commit run --from-ref origin/HEAD --to-ref HEAD
```

No `.pre-commit-config.yaml`? Use the repo's lint/format script scoped to the
changed files. If a comment names a missing test, write the test.

Then push. Push **before** replying, so every reply points at code that exists.

## 4. Reply inline

```bash
gh api repos/{owner}/{repo}/pulls/$PR/comments/<databaseId>/replies -f body='...'
```

Reply to the thread's **first** comment id, not the last.

**Keep replies short — one or two sentences.** Say what changed and where, or
why not. That is all.

- Good: `Fixed in a1b2c3d — the clamp now runs before the margin is applied.`
- Good: `Not changing this: the caller already holds the lock (see line 88).`
- Bad: restating the reviewer's point back at them, an apology, a paragraph of
  reasoning nobody asked for, or a diff pasted into prose.

## 5. Resolve — bots only

| Author | Resolve the thread? |
|---|---|
| `github-actions`, `copilot`, `coderabbitai`, any bot | Yes, once answered |
| A human | **Never.** Marking a colleague's thread resolved is their call, not yours |

```bash
gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -F id=<threadId>
```

## 6. Report

Per thread: file:line, the outcome, and the commit if there was one. Then say
what CI is doing (`gh pr checks $PR` once — do not babysit it; that is `/pr
--watch`) and stop.
