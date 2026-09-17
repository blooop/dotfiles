# Review core

Shared review content for **`review-self`** (fix it yourself) and **`review-other`**
(comment on someone else's PR). The review is identical either way — the same
attack, the same bar, the same findings. Only the **output** differs: commits in
one, a single batched PR review in the other. Nothing in this file decides which;
your skill does.

Read this alongside your skill, not instead of it.

The Spec axis (§5) and the parallel-subagent split are adapted from aihero.dev's
`/code-review`: the brief is theirs, the spec resolution is made deterministic so
nothing is ever asked, and its Standards axis is deliberately **not** a review
axis here: §7 refuses those as findings, and `review-self` applies them instead,
as a `/simplify` pass after the correctness commits — and only when the
invocation asks for it, because that pass is expensive. `review-other` never
raises them at all.

## How to run it: four subagents

Run the review as **four parallel subagents**, so the four kinds of reading do
not pollute each other's context:

- **Defects** — §1, §2, §4. The adversarial read: attack, prove, refute.
- **Types** — §3. Constructive modeling: what states the change now permits.
- **Spec** — §5. Conformance against what was actually asked for.
- **Tests** — §6. The test diff, and the machinery that decides what runs.

Each subagent gets the diff command, the commit list, the path to this file, and
the section numbers that are its — it reads those sections itself. Pasting them
costs the parent output on every spawn and buys nothing. Each reports at most
~400 words. All four read only; nothing a subagent finds is fixed by the subagent that
found it.

**Types always runs.** It is not gated on the diff containing a `struct` keyword,
and it is the one axis with no skip condition — every change models something, and
§3 says where to look when there is no new type declaration. **Tests always runs
too**, and a diff that adds no test at all is the case it exists for, not a reason
to skip it. Spec is the only skippable axis: where §5 resolves no spec, skip that
subagent and say so in the report.

**Defects and Tests read the same diff from opposite ends, and that overlap is
deliberate.** Defects hunts the input that breaks the code; Tests asks which new
branches nothing exercises. On a real review the two meet in the middle — the
uncovered branch and the bug sitting in it are one defect and its missing guard.
Where they collide, the parent merges them into a single finding naming the bug
*and* the test that would have caught it, rather than posting the pair. A finding
two axes reached independently is the strongest thing in the report; say that it
was.

The parent aggregates and **ranks correctness first** (§7). A §1–§2 defect outranks
everything. A Types finding that names a reachable illegal state ranks with it — an
illegal state you can construct *is* wrong behaviour on a concrete input; one that
only argues a tighter shape ranks below, above §4. A Tests finding ranks with
correctness when the untested branch is one that ships by default; one that asks for
more coverage of a path already exercised ranks below §4. A Spec finding ranks by
which of §5's three questions it answers. Do not merge the reports into one list
before ranking, and never let one clean report soften another's finding.

## 1. Read the change, then attack it

Read the diff, then the PR body if there is one — it says what the change is
*for*, and half of all findings are answered there. Then read the **surrounding
code** for everything the diff touches.

Now stop reading for correctness and go looking for the input that breaks it.
"Does this look right" finds nothing; a competent author already read it that
way:

- **Boundaries** — empty, one, exactly full, one past, zero, negative, NaN, max.
- **Error paths** — every early return and `catch`: what state is left behind,
  what does the caller see, is the failure silent?
- **The paths the tests skip.** Diff the new tests against the new branches —
  a branch nothing exercises is where the bug is. Finding the bug there does not
  spend the gap: hand it to §6, which reports the missing test as a finding of
  its own rather than as your evidence.
- **Interaction with what did not change.** Most real defects live here: a new
  caller violating an old function's unstated assumption.
- **Lifetimes and ownership** — dangling reference, use-after-move, iterator
  invalidation, a captured reference outliving its frame.
- **Concurrency** — two of these at once, out of order, one half-failed.
- **Node lifecycle** — for a ROS node the diff adds or changes: which callback
  group each callback lands in and whether two of them may run together, a
  callback arriving on a foreign SDK or network thread touching node state
  unmarshalled, and every subscription, timer, and handle it creates torn down
  on shutdown. The repo's CLAUDE.md usually names the node base class and its
  rules — grade against that, not against raw `rclpy`.
- **Networked paths** — a timeout on every call, what a retry does the second
  time (idempotent, or a duplicate), and what state a partial failure leaves.
- **Schema and wire compatibility** — an old peer, an old recorded log, a
  half-deployed fleet; ROS messages, services, and parameters count. A break is
  half a finding until you name who consumes it.
- **Resources** — unbounded growth, a lock held across I/O, a leak on the error
  path.

Building the branch and running the failing case is the strongest form of this,
and it is available in both modes.

## 2. Prove it, then try to refute it

For each candidate, write the failure as **concrete inputs → wrong result**. "This
could break" is not a finding; "an empty `waypoints` here makes `.front()` UB at
line 214" is. If you cannot name the input, drop it.

Then argue the other side. Go looking for the reason it is **not** a defect: a
guard upstream, an invariant the caller holds, a type that cannot represent the
bad value, a test that already covers it. Read that code — do not assume it is
absent because you have not seen it.

Only what survives both steps is a finding. Where the check is cheap, run it: a
reproduction you have actually seen fail is worth five careful readings.

## 3. Constructive modeling

Run the **`constructive-modeling`** skill in **Review** mode over what the diff
models, and fold its findings in. Two sentinels in one field, a tag beside
parallel fields, `bool success` next to a payload — these are the findings most
worth having and the ones a line-by-line read misses.

This axis runs on every review. A diff that declares no new type still models
state, so where there is no `struct`, `enum`, `class`, `oneof`, `.proto`, or
`.msg` in the diff, look at:

- New or changed **function signatures** — a `str` parameter that is really three
  states, a pair of `bool`s where one is only meaningful if the other is set, an
  argument whose valid range the type does not carry.
- **Return shapes** — a nullable return that means both "absent" and "failed", a
  tuple whose fields go stale relative to each other, an error signalled in-band.
- **Untyped structure** — a dict, JSON blob, config key, or string-keyed state
  machine the diff introduces or grows.
- **New call sites of existing types** — a caller that now constructs a
  combination of fields the old code never produced.

Report, never edit: name the state the change now permits and the field or
argument combination that reaches it. Applying the transformation is the parent's
job, and only where the parent fixes — `review-self` re-runs the skill in *Apply*
mode, `review-other` suggests the shape in a comment and implements nothing.

Scope it to what the diff touches. Do not audit the whole schema because the diff
brushed against it, and do not report a tighter shape you cannot tie to a state
the code can actually reach.

## 4. Comment verbosity

Comments the diff adds or touches are part of the change, and a comment that
restates the code is not a style preference — it is a claim that goes stale and
then lies. Count as findings:

- Narration of what the next line plainly says.
- A comment describing behaviour this diff just changed — now wrong.
- A banner or block header over a three-line function.
- A docstring that repeats the signature without adding a unit, an invariant, an
  ownership rule, or a failure mode.
- A commented-out block, or a `TODO` with no owner and no ticket.

The comments worth keeping say *why*, or name something the types cannot: a
unit, an invariant, a non-obvious constraint, a reference to the bug that forced
the shape. Where code and comment disagree, treat the comment as the defect until
you have proven otherwise.

Scope this to the diff. Do not sweep the file, and do not trade a correctness
finding for a comment one.

**One exception, and it is mandatory: a claim the diff falsifies.** Where the
change makes a stated claim untrue — and especially where the diff itself rewords
that claim in one place — every other copy of it is in scope, wherever it lives:
another file, a test docstring, a config header, a README, a marker description.
Grep the tree for the claim; do not sweep the file for comments. A PR that updates
four copies of a sentence and misses a fifth has left that fifth *false*, and the
copy it missed is usually the one sitting on the test that pins the behaviour —
the first place the next reader looks to find out what the thing is for. The
exception licenses that one grep and nothing else. You are chasing copies of a
claim the diff already changed, not auditing the project's prose.

## 5. Spec conformance

Everything above asks whether the change is correct. This asks whether it is the
change that was asked for, and a diff can pass every other section while building
the wrong thing.

Resolve the spec **deterministically, and never ask**:

1. The ticket the PR closes: `Closes #n`, or the tracker's Development link.
2. Issue references in the branch's commit messages.
3. A spec file the ticket links.

If none of those resolve, report **"no spec available"** and skip this section.
Never infer the spec from the code. A spec reconstructed from the diff grades the
diff against itself, and always passes.

With a spec in hand, three questions:

- **Missing or partial** — a requirement the spec asked for that the diff does not
  deliver. Quote the spec line.
- **Unasked-for behaviour** — scope creep. Quote the hunk, and name what in the
  spec it answers to, if anything.
- **Implemented but wrong** — a requirement the diff appears to satisfy where the
  implementation does not do what the spec meant. This is the most valuable finding
  in the section and the one a §1 read misses, because the code looks deliberate.

A spec finding still has to clear §7. "The spec says X and the diff does Y" is a
finding; "the spec is vague here" is a question for the author, not a defect.

## 6. The test diff, and what decides which tests run

Every section above reads the code. This one reads the tests as a change in their
own right — because they are one, and on most PRs nobody reviews them. Three
questions, and the third is the one that gets skipped.

**Does the new behaviour have a test?** Diff the new tests against the new
branches. A branch that ships by default and is executed by no test is a finding,
stated as the cases to write — input, the branch it reaches, the assertion — never
as "this needs more coverage". A bug fix with no regression test is the same
finding: the test is what stops it coming back, and the repo's own agent
instructions usually say so outright. Where §1 already found the bug in that
uncovered branch, this is the same defect from the other side; say so, so the
parent posts one finding instead of two.

Two shapes hide here, and both are invisible from the production code:

- A **fixture-wide override** pinning a parameter to the one value that disables
  the feature. Every test in the file inherits it, so the shipped default is
  exercised by nothing while the suite looks green and thorough.
- A suite that **holds one input fixed** — a clock that never advances, a
  single-element collection, one device, one robot — leaving every branch that
  depends on it changing dead in the suite.

**Does each new or changed test assert what it appears to assert?** Read the setup
against the assertion, not the test name. The recurring failure is an assertion
that passes on a value the setup never wrote: zero-initialised fields compared
against zero, a default-constructed message, an empty collection matching an empty
expectation. A test over an n-way slice, a stride, or a pair of offsets that
asserts only the first block passes on `0 == 0` and pins nothing — a later
refactor can transpose the offsets and stay green. Finding this means reading the
fixture, which is exactly what a Defects pass aimed at production code does not do.

**Does a change to test selection deliver the coverage it claims?** Markers,
tiers, lanes, gates, `pytest.ini`, `conftest.py`, CI path filters, manifest
generators, allowlists — moving a test between lanes is a change to what runs
before merge, and the justification for it is checkable. Run the machinery rather
than reading it: the repo's manifest or partition check, the lane or tier query,
the marker registry. Then hold the claim in the PR body or the comment against
what the machinery actually does. A justification that does not hold — "a stack
change can break it with the sim untouched", where the gate still defers to
another filter and a stack-only PR runs neither test pre-merge — is a finding,
because the next author applies the rule expecting coverage it does not give.
Where the move is sound, name which cadence actually widened; that is worth
stating so nobody re-derives it.

Report, never fix, the same as every other axis.

## 7. What counts as a finding

| Counts | Does not |
|---|---|
| Wrong behaviour on a concrete input you can name | Style, naming, formatting, import order |
| Silent failure — swallowed error, ignored return, empty `except` | "Consider extracting this" |
| Data loss, corruption, or an unbounded resource | Preference dressed as a rule |
| Race, deadlock, or lifetime/ownership bug | Anything the linter or CI already says |
| Security: injection, secret in the diff, auth bypass | A test you would have written differently, but which passes and asserts something |
| Public API or wire-format break with no migration — named with its consumers | Restating what the diff does |
| A test that asserts nothing, asserts the mock, or pins the implementation so tightly that a behaviour-preserving refactor fails it | Anything you are not fairly confident about |
| A fallback or default that masks a real error instead of surfacing it | Reuse, duplication, dead code — `/simplify`'s, when asked for, and never a finding here |
| An illegal state the types now permit (§3) | "The spec is vague here" |
| A requirement the spec asked for that the diff does not deliver (§5) | A spec you reconstructed from the diff |
| Behaviour the diff adds that no spec asked for (§5) | |
| A comment that narrates, or has gone stale (§4) | |
| New behaviour, or a bug fix, with no test that would have caught it — named as the case to write (§6) | "Needs more test coverage", with no branch named |
| An assertion that passes on a value the setup never wrote — zero-init fields, a default-constructed message (§6) | A test-selection change you would have scoped differently, where the stated reason holds |
| A change to test selection or gating whose stated justification does not hold (§6) | |

The test: **would a competent author change the code because of this?** If the
honest answer is "they would reply 'sure, whatever'", it is not a finding.
