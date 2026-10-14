---
name: review-mark
description: Deep, production-grade review of a PR (or the current branch's diff) against the full quality bar — correctness, SOLID/DRY, complexity, concurrency and resource lifecycle, security, API breakage, tests, project conventions — returning concise review comments anchored to exact GitHub diff lines. Use when the user pastes a PR link and asks for a deep/thorough review, or invokes /review-mark.
---

# Deep PR Review

**Target:** `$ARGUMENTS` — a PR URL or number, a branch name, or empty. Empty means the current branch's PR; if the branch has no PR, review `git diff origin/<default-branch>...HEAD`.

Review **every change** in the target to the bar below and return a list of concise, paste-ready review comments, each anchored to the exact line GitHub will render it under. The bar is world-class engineering: every line intentional, lean, maintainable, and shippable to production as-is. No hacks, workarounds, or "good enough for now".

**Do not post anything to GitHub** unless the user passed `--comment` or explicitly asked. Default output is the comment list in the terminal.

## 1. Load the change

```bash
gh pr view <n> --json title,body,author,baseRefName,headRefName,files,additions,deletions,state,isDraft
gh pr diff <n>
gh pr view <n> --json statusCheckRollup   # CI state — a red lane is a finding, not a footnote
gh pr view <n> --comments                  # existing review threads: never re-raise a settled point
```

Then read the **whole changed files**, not just the hunks — most real findings live in the interaction between new code and the code around it. For files not on the current branch: `git fetch origin <headRefName> && git show origin/<headRefName>:<path>`. Read the base version too where the diff is a modification (`git show origin/<baseRefName>:<path>`) so you judge the delta, not the file.

Establish before reviewing: what problem the PR claims to solve, whether the diff actually solves it, and what it touches that it did not claim to touch.

## 2. Review dimensions

Work all of these. A dimension you skipped is a dimension you must say you skipped.

**Correctness and design**
- Is this a production-grade long-term fix, or a patch over a symptom? Name the root cause if the PR treats a symptom.
- SOLID: single, clear responsibility per component; dependencies abstracted and injected, not reached for.
- DRY: duplicated logic, copy-paste variants, parallel implementations of one rule.
- Leaky abstractions, dead code, unreachable branches, vestigial parameters.
- Law of Demeter, KISS, YAGNI: speculative generality, config knobs nothing sets, hypothetical-future scaffolding.
- Design patterns applied judiciously — flag both a **missing** pattern that would collapse the code and an **over-applied**/speculative one.
- **Flags and fallbacks are an architecture smell**: if a flag, default, or defensive fallback is what makes the change work, the wiring is wrong — say so and describe the direct control flow that replaces it.

**Complexity and hot paths**
- Nested loops over the same data, redundant iteration, repeated lookups that belong outside the loop.
- Unnecessary allocations, copies of large buffers/messages/images, per-iteration object construction.
- Anything in a latency-critical path — a real-time or control loop, a request handler, a render frame, a tight inner loop: allocation, locking, logging, or syscalls on the hot side.

**Concurrency and resource lifecycle**
- Thread safety of shared state; correctness of whatever concurrency model the project uses (thread pool, async event loop, actor, ROS executor and callback groups). A blocking call made on the same single-threaded context that must service its completion is a deadlock.
- Races, deadlocks, lost wakeups, ordering assumptions between callbacks.
- Leaked or improperly torn down subscriptions, timers, clients, threads, tasks, file handles, sockets, memory. Teardown ordering vs. process/component shutdown.
- Callbacks arriving on a foreign thread (an SDK, a network library, a UI toolkit) must be marshalled onto the owning context before touching shared state.

**Boundaries, security, contracts**
- Input validated at system boundaries (and *only* there — internal re-validation is noise).
- Injection, unsafe deserialization (`yaml.load`, `pickle`, `eval`), path traversal, mishandled secrets or tokens in logs/env/artifacts.
- Breaking changes to public interfaces, wire schemas, RPC/proto, event or message definitions, topic/queue names, config schema, CLI flags, or DB schema — **name the consumers affected** (grep the tree for them, and say if consumers live in another repo).
- Networked paths: timeouts on every call, retry policy and backoff, idempotency, partial-failure and reconnect behaviour.

**Bloat**
- Unused imports, dead feature flags, commented-out code, "just in case" branches, defensive fallbacks that mask real failures instead of surfacing them.

**Tests**
- Every new and modified path covered, including edge cases and failure modes; a bug fix carries the regression test that would have caught it.
- Judge **quality, not coverage**: assertions must be meaningful (not `assert result is not None`), and tests must not be brittlely coupled to implementation detail — mock-call-count assertions that would break on a legitimate refactor are a finding.
- Missing failure-mode tests (timeout, cancel, exception, empty input, shutdown mid-call) count as missing tests.

**Error handling, naming, docs**
- Explicit, specific error handling; no bare `except:`; no swallowed exceptions; failures loud, not defaulted away.
- Precise, consistent naming; public interfaces documented.

**Scope and conventions**
- Tightly scoped: no unrelated churn, drive-by reformatting, or opportunistic refactors mixed into the diff.
- The conventions of *this* repo — see below.

## 3. Project conventions to check explicitly

Review against this repo's rules, never a remembered project's. In order of authority:

1. **`.claude/review-conventions.md`**, if the repo has one — a distilled checklist of what PRs here actually get wrong, plus the project's build/test/lint commands. Check every item in it.
2. **`CLAUDE.md` / `AGENTS.md`** at the repo root, plus any nested ones covering the changed directories. The root file is usually already in context; nested ones usually are not, so read them.
3. **The surrounding code and its tooling config** — formatter, linter, type-checker settings, and the idioms of the nearest neighbouring files. Match what is there.

Where none of the three settles a question, it is not a convention finding — say so rather than importing a rule from elsewhere.

These generic classes are worth an explicit pass in any repo:

- **Generated and mirrored files.** A build manifest, test registry, lockfile, schema stub or generated client that a hook or codegen step owns must land regenerated in the same diff — and hand-edited rather than regenerated is itself a finding. Likewise a value declared once and mirrored into another language or config: adding a member means updating every copy.
- **Hardcoded values a registry owns.** A literal topic/queue/route name, path, or enum string where the project has a single source for it.
- **Dependency changes.** A new dep carries its manifest *and* lockfile update, in every lock universe the repo maintains; a lock without the matching export/sync leaves the build reading stale pins.
- **Docs.** A package or system renamed, removed or restructured ships its `.md` updates in the same PR. References in prose are markdown links, never bare `#1234`.
- **Commit messages.** Match the project's format (imperative mood, scope prefix, trailer rules). No AI-attribution trailers.

## 4. Verify before you report

A review is worthless if its findings are speculative. For each candidate finding:

- Point at the actual code that makes it true — quote the line, don't paraphrase from memory.
- Check the claim against the rest of the tree (`grep`/`rg` for the caller, the consumer, the existing helper you say duplicates it). A "this duplicates X" finding must name X's path.
- Where it is cheap, run the targeted check using **the project's own commands** (from the sources in §3 — never a guessed or remembered one): the narrowest test invocation for a suite you doubt, the lint/hook run scoped to the changed files for a convention you suspect.
- **Drop anything you cannot substantiate.** State residual uncertainty explicitly rather than upgrading a hunch to a finding.

## 5. Scaling

For a small PR (roughly <15 files, <800 changed lines) review it directly — a single careful pass beats fan-out.

For a large PR, split by **dimension** across parallel subagents (≤5: correctness/design, concurrency+lifecycle, complexity/hot paths, tests, security+API contracts), give each the PR number and the file list, and require each to return findings with file, line, quoted evidence. Then verify and de-duplicate their findings yourself before reporting — subagent findings are candidates, not conclusions.

## 6. Deliverable

Report in this shape, most severe first:

```
## Verdict
<2-3 sentences: does it do what it claims, is it shippable, what is the one thing that must change>

## Blocking
1. `<path>:142` — <short title>
   **Comment:** <the exact concise text to paste as the review comment — 1-3 sentences, states the problem and the fix>
   **Evidence:** <quoted line / grep result / test name that proves it>

## Non-blocking
...same shape...

## Checked and clean
<one line per dimension you cleared, so the coverage of the review is visible>
```

Comments are for the PR author: concrete, specific, and actionable. No praise padding, no restating the diff, no "consider possibly maybe".

**Line anchoring — GitHub renders a comment *below* the line you target, and only lines visible inside a diff hunk can receive one.**

- Modified file: count from `+new_start` in `@@ -old,count +new_start,count @@`, incrementing for context lines and `+` lines only — **never** for `-` lines.
- New file: the line number is its 1-indexed position among the `+` lines.
- A multi-line finding uses `start_line` + `line` (the span GitHub highlights).
- Feedback that belongs to no single line is file-level: `subject_type: "file"`, `path` only, no `line`.
- Count from the hunk header to the target content every time. Never eyeball it — GitHub silently misplaces a wrong `line` rather than erroring.

## 7. Posting (opt-in only)

Only with `--comment` or an explicit ask. On the user's own PR the default is findings in chat, not self-annotation; on an external reviewer's PR, replying is expected.

```bash
gh api repos/{owner}/{repo}/pulls/<n>/comments -f body='...' -f commit_id=<head sha> -f path=<file> -F line=<n> -f side=RIGHT
```

Batch them into one review (`gh api .../pulls/<n>/reviews`) rather than firing N notifications.

Then confirm every comment landed where you meant it, using the review `id` that call returned:

```bash
gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate \
  --jq '.[] | select(.pull_request_review_id == <review id>) | {id, path, line, under: (.diff_hunk | split("\n") | last)}'
```

`under` is the diff line GitHub rendered the comment below; it must be the line the comment is about. Delete a misplaced one (`gh api -X DELETE repos/{owner}/{repo}/pulls/comments/<id>`) and repost it on the right line — never leave it for the author to decode. Report each comment's link and the line it landed on.
