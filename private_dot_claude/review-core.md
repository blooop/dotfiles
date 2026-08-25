# Review core

Shared review content for **`review-self`** (fix it yourself) and **`review-other`**
(comment on someone else's PR). The review is identical either way — the same
attack, the same bar, the same findings. Only the **output** differs: commits in
one, a single batched PR review in the other. Nothing in this file decides which;
your skill does.

Read this alongside your skill, not instead of it.

The Spec axis (§5) and the parallel-subagent split are adapted from aihero.dev's
`/code-review`: the brief is theirs, the spec resolution is made deterministic so
nothing is ever asked, and its Standards axis is deliberately **not** imported
(§6 refuses those findings on purpose).

## How to run it: three subagents

Run the review as **three parallel subagents**, so the three kinds of reading do
not pollute each other's context:

- **Defects** — §1, §2, §4. The adversarial read: attack, prove, refute.
- **Types** — §3. Constructive modeling: what states the change now permits.
- **Spec** — §5. Conformance against what was actually asked for.

Each subagent gets the diff command, the commit list, and its own sections of this
file pasted in full; it has no other access to them. Each reports at most ~400
words. All three read only; nothing a subagent finds is fixed by the subagent that
found it.

**Types always runs.** It is not gated on the diff containing a `struct` keyword,
and it is the one axis with no skip condition — every change models something, and
§3 says where to look when there is no new type declaration. Spec is the only
skippable axis: where §5 resolves no spec, skip that subagent and say so in the
report.

The parent aggregates and **ranks correctness first** (§6). A §1–§2 defect outranks
everything. A Types finding that names a reachable illegal state ranks with it — an
illegal state you can construct *is* wrong behaviour on a concrete input; one that
only argues a tighter shape ranks below, above §4. A Spec finding ranks by which of
§5's three questions it answers. Do not merge the reports into one list before
ranking, and never let one clean report soften another's finding.

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
  a branch nothing exercises is where the bug is.
- **Interaction with what did not change.** Most real defects live here: a new
  caller violating an old function's unstated assumption.
- **Lifetimes and ownership** — dangling reference, use-after-move, iterator
  invalidation, a captured reference outliving its frame.
- **Concurrency** — two of these at once, out of order, one half-failed.
- **Schema and wire compatibility** — an old peer, an old recorded log, a
  half-deployed fleet.
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

A spec finding still has to clear §6. "The spec says X and the diff does Y" is a
finding; "the spec is vague here" is a question for the author, not a defect.

## 6. What counts as a finding

| Counts | Does not |
|---|---|
| Wrong behaviour on a concrete input you can name | Style, naming, formatting, import order |
| Silent failure — swallowed error, ignored return, empty `except` | "Consider extracting this" |
| Data loss, corruption, or an unbounded resource | Preference dressed as a rule |
| Race, deadlock, or lifetime/ownership bug | Anything the linter or CI already says |
| Security: injection, secret in the diff, auth bypass | A test you would have written differently, but which passes and asserts something |
| Public API or wire-format break with no migration | Restating what the diff does |
| A test that asserts nothing, or asserts the mock | Anything you are not fairly confident about |
| An illegal state the types now permit (§3) | "The spec is vague here" |
| A requirement the spec asked for that the diff does not deliver (§5) | A spec you reconstructed from the diff |
| Behaviour the diff adds that no spec asked for (§5) | |
| A comment that narrates, or has gone stale (§4) | |

The test: **would a competent author change the code because of this?** If the
honest answer is "they would reply 'sure, whatever'", it is not a finding.
