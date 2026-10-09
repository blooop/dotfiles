---
name: pr
allowed-tools: Bash(git:*), Bash(gh:*), Bash(prek:*), Bash(pre-commit:*), Bash(uv:*), Bash(npx:*), Bash(make:*), Bash(~/.claude/skills/mermaid/scripts/*:*), Read, Write, Grep, Glob, Edit, Agent, Skill
description: Create or refresh a PR, or a stack of PRs, that a reviewer takes in one pass — reviewed first, plainly described, with a diagram where it helps. With --watch, babysit it to green
argument-hint: "[--stack] [--draft] [--watch] [--no-review] [base-branch]"
---

## Context

- Branch: !`git branch --show-current 2>/dev/null || echo "(not a git repo)"`
- Base: !`git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || echo main`
- Status: !`git status --short 2>/dev/null || echo "(not a git repo)"`
- Commits ahead of base: !`git log --oneline origin/HEAD..HEAD 2>/dev/null || git log --oneline -5 2>/dev/null || true`
- Diff stat: !`git diff --stat origin/HEAD..HEAD 2>/dev/null | tail -1; true`
- Existing PR: !`gh pr view --json number,url,baseRefName,mergeable,reviewDecision 2>/dev/null || echo "none"`

## Task

Get the current branch onto pull requests a tired reviewer understands in one pass, then **stop and
report the links**. Ask nothing, except about a merge conflict you cannot resolve confidently. Each
fix is its own commit; never amend.

Flags in "$ARGUMENTS" (strip them; any remainder is a base-branch override):

- `--stack`: you may split the work into a stack, and independent parts into separate PRs, where
  that reviews better. The user's own words ("stack as appropriate", "split this up") mean the same.
- `--draft`: open the PRs as drafts.
- `--watch`: after the PRs are up, run step 8. Without it, **do not wait on CI**.
- `--no-review`: skip step 3.

On a branch that already has a PR, this is a **refresh**: steps 1–3, then rewrite the description
and visual against the code as it now is (steps 5–6), and push.

### 1. Sync with base

If on the base branch itself with no PR, stop and tell the user to branch first.

`git fetch origin && git merge origin/<base>` (base = the existing PR's `baseRefName`, else the
override, else the detected base). On conflict: read both sides, resolve, commit the merge.

### 2. Commit and lint

Commit any uncommitted work with a clear message. Lint **only what changed**:
`prek run --from-ref origin/<base> --to-ref HEAD` (`pre-commit` where there is no prek; a repo's
CLAUDE.md names its own). Fix, commit, retry, at most 3 rounds, then report and stop.

### 3. Review

Skip for `--no-review` or a diff of 3 files and 30 lines or less. Otherwise run the `review-self`
skill on the branch (on the whole stack after step 4, if you split it). It proves defects with tests,
fixes them as commits and pushes. Do not review again after it.

### 4. Choose the shape

One PR is the default. With `--stack`, split where each slice has one purpose, builds and passes
its tests on its own, and is smaller to read than the whole; a slice that does not depend on the
others goes on its own PR off the base instead. Build the stack with the `stack` command's
`create` mechanics, skipping its confirmation, and name the split in the final report. Without
`--stack`, keep one PR; if it clearly splits, say so in one line of the report.

### 5. Write the description

Load `pr-plain` and write in its Simplified Technical English from the start, not as a rewrite.
Describe the code in the diff as it is now: no history of how it got there, nothing the diff does
not contain. Use the repo's own terms (its `GLOSSARY.md` when it has one). Shape, keeping only the
sections that have content:

- `Part of [#<ticket>](url).` when there is a ticket
- `## What this changes`: what the reviewer will see, one bullet per change
- `## Where this fits`: the visual from step 6
- `## Why it stands alone`: stack slices only
- `## How I checked it`: **before/after** pairs. Best is a screenshot pair for a visual change;
  next, the test that failed before and passes now (its steps as pseudocode), or the output
  before and after. Then the commands you ran; say what you did not run
- `## Merge danger`: always present. `**Door:** one-way` or `two-way`: a two-way door is a plain
  revert; a one-way door is a destructive action, a data or schema migration, or a changed
  message, API or file format that something already consumes. `**Blast radius:**` one word,
  then what breaks and for whom if the change is wrong
- `## Review notes`: anything `review-self` left open
- `## Stack`: every PR bottom first, each a link, `← this PR` on this one

Every reference is a markdown link. No `Co-Authored-By` or session trailers unless the repo asks.

### 6. Visual

Pick the **smallest view** that makes the key point clear, next to the one sentence it supports.
One view is usual, two at most:

- Logic or an algorithm: pseudocode.
- Runtime control flow: a call tree.
- A refactor or a move: a shallow file tree.
- A change to a shape that already exists: a `diff` fence of that shape (call tree, file tree,
  pseudocode), with `+` and `-` on the lines that change:

  ```diff
   on(save)
  +  if content is unchanged
  +    return cached result
     write new content
  ```

- A component added, removed or moved, a change to how data flows, a process boundary crossed,
  or a stack: Mermaid. Load `mermaid` for it.

Keep only the calls, files and states the reviewer needs. A config value or a doc needs no view:
if a sentence says it, the sentence is the description.

- **One PR**: put the view in `## Where this fits`. For Mermaid, draw the mechanism the change
  turns on and run its self-check.
- **A stack**: write one spec at `~/.claude/stack-diagrams/<ticket-or-top-branch>.mmd`, with a
  `files` line for every box and a `note` per PR (and a `ticket` line if there is one). After the
  PRs exist, `stack.py render`, read the views, then `stack.py apply`, which writes each PR's
  section from its own diff.

The body format adapts Matt Pocock's `pr` skill (github.com/mattpocock/skills), whose visuals come
from Dex Horthy's `show-me`.

### 7. Push and create

Push (`-u` if needed). Create each PR with `gh pr create --body-file` (bottom first for a stack,
base = the branch below), a title under 70 characters in the repo's commit style, `--draft` only if
asked. Then run the step 6 stack `apply`. Print every link, and whether CI was still pending.

**Without `--watch`, you are done here.**

### 8. Babysit (`--watch` only)

Loop, at most 5 rounds, over every PR you opened:

1. `gh pr checks <number> --watch --fail-fast --interval 60`. Watch one PR at a time: the
   default 10s poll, times several PRs, uses up the account's API quota.
2. **Not mergeable**: redo step 1, lint, push, restart. In a stack, run `/stack sync` instead.
3. **CI red**: `gh run view <run-id> --log-failed`, fix the actual error, commit
   `fix: <what failed>`, lint, push, restart.
4. **Review comments**: run the `respond` skill.
5. Green, mergeable, nothing unresolved: report and stop.

After 5 rounds, report what is still broken and stop. When a push changes a stack PR's diff, rerun
`stack.py apply` so its diagram still matches.
