---
name: pr
allowed-tools: Bash(git:*), Bash(gh:*), Bash(prek:*), Bash(pre-commit:*), Bash(uv:*), Bash(npx:*), Bash(make:*), Bash(~/.claude/skills/mermaid/scripts/*:*), Read, Write, Grep, Glob, Edit, Agent, Skill
description: Create or refresh a PR, or a stack of PRs, that leads with evidence the change works — before/after graphs from real runs — then a plain description a reviewer takes in one pass. With --watch, babysit it to green
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
report the links**. Each PR leads with **evidence**: graphs from real runs that show the change does
what it claims. Passing tests support the evidence; they are not the evidence. Ask nothing, except about a merge conflict you cannot resolve confidently. Each
fix is its own commit; never amend.

Flags in "$ARGUMENTS" (strip them; any remainder is a base-branch override):

- `--stack`: you may split the work into a stack, and independent parts into separate PRs, where
  that reviews better. The user's own words ("stack as appropriate", "split this up") mean the same.
- `--draft`: open the PRs as drafts.
- `--watch`: after the PRs are up, run step 9. Without it, **do not wait on CI**.
- `--no-review`: skip step 3.

On a branch that already has a PR, this is a **refresh**: steps 1–3, then measure the evidence again
if the behavior changed (step 5), rewrite the description and visual against the code as it now is
(steps 6–7), and push. Push the new description first, with the evidence you have now: mark each
graph still running as `_Pending: <run>_`, and update the description again when the run ends. In
status lines, call it "the description", not "the PR refresh".

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

### 5. Prove it works

The evidence is the center of the PR. A reviewer sees that the change works before reading how.

1. **Claim.** Write one sentence for each behavior the change makes true, in the terms a user of the
   system measures: "the robot stops within 0.6 m at 1.2 m/s", not "adds a braking ramp".
2. **Measure.** Run the base and the branch through the same scenario (sim, benchmark, replay,
   script) with the project's real runner. Every number in the PR comes from a run you did.
3. **Draw.** One graph per claim, before and after on the same axes, so the difference is the first
   thing the eye sees.
   - **Text first.** Each graph is text that GitHub draws inside the PR body (the forms below).
     Text stays the default and the fallback. For what text cannot show (every repeat, box plots,
     2-D heatmaps, paths), add images with `bencher ab --images`. Images live on
     `refs/bencher/evidence`, never on a branch, so a clone never fetches them.
   - **A metric across runs, inputs or time:** Mermaid `xychart-beta` with two named lines
     (`line "before" [...]`, `line "after" [...]`, which draw a legend) and a `plotColorPalette`
     in the frontmatter (the default palette hides the first line). Show the spread as a CI band:
     pale lines for the bounds. Keep to about 30 points and summarize more (a median per case).
   - **A changed order of events or states:** a `sequenceDiagram` or `stateDiagram` pair.
   - **Two swept inputs:** a markdown table heatmap of the percent change, with emoji squares
     (🟦🟩🟨🟧🟥) chosen by better or worse, and a legend line.
   - **Negative values, many categories, or labels too long for an axis:** a ```diff fence of
     Unicode bars, a `-` line for before and a `+` line for after, each with its number.
   - **The data under each graph:** a `<details><summary>data</summary>` block with a CSV fence.
   - **No text form and no bencher image** (a screenshot): describe the result in one sentence
     with its numbers, and name the command that reproduces the view.
   Run the `mermaid` skill's `render.py` on each Mermaid block and look at the PNG, in light and dark.
4. **Caption.** Under each graph, one line: what it shows, the number that matters, and its source
   (the command, the run link, or the CSV).

**Bencher is the default for any claim that is a number** (holobench ≥ 1.143): it does steps 2–4 in
one command, the same way in every repo. Draw by hand only a claim that is not a number (an order
of events, a screenshot) or a repo where no Python bench can drive the code. Declare the claim on
the result (`bn.ResultFloat(claim="< 0.7")`), then run `bencher ab --base origin/<base> -- <bench command>`.
It runs the base in a worktree and the working tree as the candidate, each with its own cache, and
writes `evidence.md`: text-only charts (the forms above), captions with the CI and the verdict, the
claim verdicts, and a data block per metric. Paste `evidence.md` as `## Evidence`. Add `--images`
(before the `--`) to put a PNG above each text chart that the image improves. `--images` needs push
access to a github.com `origin`; with none, or with an ssh host alias remote, it writes text only
and prints one line that says why. A bench
that the change itself adds has no base: commit the bench first and give that commit as `--base`.
In a repo that does not use bencher, keep the bench out of the repo: write it in the scratchpad,
install the repo editable with `holobench` into a venv that git ignores (`.git/info/exclude`), and
run `bencher ab --base origin/<base> -- python <scratchpad>/bench.py` with that venv first on `PATH`.
The base side still imports its own code.

**Statistical evidence** (holobench with `bencher/evidence_report.py`, blooop/bencher#1186). Every
number claim gets a verdict that the data can carry, not a bare before/after:

- **Name the claim kind and the margin before the run.** Improvement, no regression, same behaviour,
  reliability, flake fixed, absolute bound, or tail. Set ±Δ on the result
  (`bn.ResultFloat(claim=..., margin=0.05)`) or with `--margin`. Name the 1–3 metrics the PR claims
  as `--primary`; the others are secondary and only flag.
- **Run enough, and pair the runs.** Interleave base and candidate on the same machine with the same
  seed (kbench `--ci --base <ref> --paired`). To claim a flake is gone at rate p₀, you need
  ⌈ln 0.05 / ln(1 − p₀)⌉ clean runs: 29 for 10 %, 59 for 5 %, 299 for 1 %. When the report says
  "underpowered", add the runs it names or say the claim is not proven.
- **Write the report.** For two recordings: `bencher compare BASE.pkl CAND.pkl --report DIR`. For
  kbench rows (`repeats.json`, with `shard`, `order` and `seed` when known):
  `bencher evidence-rows BASE.json CAND.json --report DIR --primary m1,m2 [--paired]`. Push the
  PNGs with `bencher.evidence_ref.push_evidence` (flat file names, one run dir) and point the image
  links at the returned blob URLs (`--url-base` or rewrite `src`/`srcset`).
- **Read the verdict as written.** "No change" needs the whole 90 % CI inside ±Δ; a CI that crosses
  the margin is "? inconclusive", and the PR says so. Never write "unchanged" from a test that only
  failed to reject. Paste the report as `## Evidence`, scorecard and design strip first.

A refactor, or any change that must keep behavior, claims "no change", and its graph overlays before
and after to show it. A doc, comment or config value with no runtime effect gets one line that says
so. A claim you cannot measure here (hardware only, say) gets one line naming the run that would
prove it and who can do it. In a stack, each slice carries the evidence for its own behavior.

Done when every behavior bullet in `## What this changes` has a graph, or one of those lines.

### 6. Write the description

Load `pr-plain` and write in its Simplified Technical English from the start, not as a rewrite.
Describe the code in the diff as it is now: no history of how it got there, nothing the diff does
not contain. Use the repo's own terms (its `GLOSSARY.md` when it has one). Shape, keeping only the
sections that have content:

- `Part of [#<ticket>](url).` when there is a ticket
- One sentence: what the change makes true
- `## Evidence`: the graphs and captions from step 5, first, before any prose about the code
- `## What this changes`: what the reviewer will see, one bullet per change
- `## Where this fits`: the visual from step 7
- `## Why it stands alone`: stack slices only
- `## How I checked it`: the support under the evidence. The test that failed before and passes
  now (its steps as pseudocode), then the commands you ran; say what you did not run
- `## Merge danger`: always present. `**Door:** one-way` or `two-way`: a two-way door is a plain
  revert; a one-way door is a destructive action, a data or schema migration, or a changed
  message, API or file format that something already consumes. `**Blast radius:**` one word,
  then what breaks and for whom if the change is wrong
- `## Review notes`: anything `review-self` left open
- `## Stack`: every PR bottom first, each a link, `← this PR` on this one

Every reference is a markdown link. No `Co-Authored-By` or session trailers unless the repo asks.

### 7. Visual

The evidence shows the result; this view shows the mechanism.

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
  section from its own diff. Start with `flowchart TB`: a chain of more than four boxes laid out
  `LR` goes past GitHub's width, and GitHub shrinks the text until no one can read it.

The body format adapts Matt Pocock's `pr` skill (github.com/mattpocock/skills), whose visuals come
from Dex Horthy's `show-me`.

### 8. Push and create

Push (`-u` if needed). Create each PR with `gh pr create --body-file` (bottom first for a stack,
base = the branch below), a title under 70 characters in the repo's commit style, `--draft` only if
asked. Then run the step 7 stack `apply`. Print every link, and whether CI was still pending.

In a stack, check which PRs CI runs on: a workflow with `pull_request: branches: [main]` tests only
the bottom PR, so the PRs above it get no full-suite run until their base becomes `main`. For each
PR that CI skips, run the full suite on its head with the project's runner, and put the result in
its `## How I checked it`.

**Without `--watch`, you are done here.**

### 9. Babysit (`--watch` only)

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
