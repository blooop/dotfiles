---
name: review-mark
description: Deep, production-grade review of a PR (or the current branch's diff) against the full quality bar — correctness, SOLID/DRY, complexity, concurrency and resource lifecycle, security, API breakage, tests, project conventions — then fixes every verified finding directly on the PR branch: one commit per fix, verified with the project's own checks, and pushed. Never posts review comments. Use when the user pastes a PR link and asks for a deep/thorough review, or invokes /review-mark.
---

# Deep PR Review

**Target:** `$ARGUMENTS` — a PR URL or number, a branch name, or empty. Empty means the current branch's PR; if the branch has no PR, review `git diff origin/<default-branch>...HEAD`.

Review **every change** in the target to the bar below, then **fix every verified finding yourself** on the PR's head branch and push. The bar is world-class engineering: every line intentional, lean, maintainable, and shippable to production as-is. No hacks, workarounds, or "good enough for now" — and that bar holds for your fixes too.

**Never post review comments, reviews, or approvals.** The fix is the feedback: each one lands as a commit the author can read. Output to the user is the report in §8.

## 1. Load the change

```bash
gh pr view <n> --json title,body,author,baseRefName,headRefName,files,additions,deletions,state,isDraft
gh pr diff <n>
gh pr view <n> --json statusCheckRollup   # CI state — a red lane is a finding, not a footnote
gh pr view <n> --comments                  # existing review threads: never re-raise a settled point
```

Then read the **whole changed files**, not just the hunks — most real findings live in the interaction between new code and the code around it. For files not on the current branch: `git fetch origin <headRefName> && git show origin/<headRefName>:<path>`. Read the base version too where the diff is a modification (`git show origin/<baseRefName>:<path>`) so you judge the delta, not the file.

Check out the head branch where the project's real runner lives — `dl <org>/<repo>@<headRefName>` for a containerized repo, otherwise a git worktree on `origin/<headRefName>`. Fixes are built, tested and committed there, never in a checkout that cannot run the project's hooks and tests. Note `gh pr view <n> --json isCrossRepository,maintainerCanModify` now: a fork PR without maintainer edits cannot take a push (§7).

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

For a large PR, split the **review** by dimension across parallel subagents (≤5: correctness/design, concurrency+lifecycle, complexity/hot paths, tests, security+API contracts), give each the PR number and the file list, and require each to return findings with file, line, quoted evidence. Then verify and de-duplicate their findings yourself — subagent findings are candidates, not conclusions.

Fixes land serially in the one checkout, most severe first, so each builds on the last. When there are many, hand them to one fix subagent with the ranked findings, the checkout, and the project's runner and check commands in its brief.

## 6. Apply the fixes

For each verified finding, most severe first:

1. **Prove it where it is a behaviour defect.** Write the test that fails on the current code, run it, see it fail. A bug fix without its red step is unproven.
2. **Make the smallest fix that meets the bar** — the root-cause fix, not a guard around the symptom. Touch nothing outside the finding: no drive-by refactors in a fix commit.
3. **Run the project's own checks** (§3 sources) scoped to what you touched: the test you wrote, the suite around it, and the lint/format/type hooks for the changed files. Regenerate any generated or mirrored file the change affects.
4. **Commit it alone**, in the project's commit format, with a body that says what was wrong and why the fix is right — the author reads this instead of a review comment. One finding, one commit; never `--amend` or squash a fix into the author's commits.

Never weaken a test to get green — no skip, xfail, loosened assertion or re-run until a flake lands. If an existing test is wrong, fix it in its own commit and say why.

**Do not apply** a finding that is the author's call rather than a defect — splitting the PR, choosing between two valid designs, dropping a feature, a breaking change to an interface other teams consume. List it under *Not applied* with the reason and the change you would make. Keep this list short; "I'd rather not" is not a reason.

## 7. Push

Push the fix commits to the head branch with a plain fast-forward push — never a force push over the author's history:

```bash
git fetch origin <headRefName> && git rebase origin/<headRefName>   # pick up anything the author pushed meanwhile
git push origin HEAD:<headRefName>
```

A rebase conflict with the author's new commits is yours to resolve; re-run the checks after it. If the push is refused — a fork without maintainer edits, a protected branch, no write access — push the commits to `review-mark/<headRefName>` on a remote you can write, and report that branch so the author can pull it. Do not open a PR or post a comment about it.

Then check CI on the pushed head once (`gh pr checks <n>`), and again later at an `--interval 60` or slower if it is still running. A lane your commits broke is yours to fix before you report.

## 8. Report

Report in this shape, most severe first:

```
## Verdict
<2-3 sentences: does it do what it claims, is it shippable now that the fixes are in, what still needs the author>

## Applied
1. `<sha>` `<path>:142` — <short title>
   **Problem:** <1 sentence>
   **Fix:** <1 sentence>
   **Evidence:** <the test that failed before and passes now / the check that proves it>

## Not applied
1. `<path>:88` — <short title> — <why it is the author's call, and the change you would make>

## Checked and clean
<one line per dimension you cleared, so the coverage of the review is visible>

## Push
<branch pushed to, head sha, CI state>
```

No praise padding, no restating the diff.
