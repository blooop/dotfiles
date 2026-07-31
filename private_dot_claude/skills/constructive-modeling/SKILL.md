---
name: constructive-modeling
description: Audit or refactor types so illegal states are unrepresentable — sum types instead of tag+parallel-fields, no sentinel values, exhaustive matching, total functions. Use when reviewing a diff or PR for data-modeling defects, when designing or changing a struct/message/enum/proto/.msg, or when the user mentions constructive modeling, illegal states, sentinel values, "parse don't validate", or making an invariant type-enforced.
---

# Constructive Data Modeling

Model the states a system can actually be in, so the ones it cannot be in have no
representation. This needs only three language features — product types, sum
types, exhaustive matching — never dependent types or a fancier type system.

**The one question:** for this type, what values can be constructed that the
program must then reject, apologise for in a comment, or panic on? Each one is a
finding.

## Modes

- **Review** — audit a diff, PR, or file. Report findings; do not edit. Use the
  output format below.
- **Apply** — perform the transformation. Bump schema versions, update every
  consumer the compiler flags, add tests asserting the illegal state no longer
  compiles or no longer round-trips.

Default to Review when the user is looking at someone else's change, Apply when
it's their own working tree. Ask only if genuinely ambiguous.

## Principles

1. **Define the positive space, not the negative space.** It is easier to add
   than to subtract. `Natural` is not "Int where >= 0"; it is `UInt`, and
   `Integer = (Bool, Natural)`. `NonEmptyList<T>` is not "List with len > 0"; it
   is `(T, List<T>)`.
2. **Decouple representation from interpretation.** Data has no privileged
   representation. "My data *is* an array" is a bug; "my data is a sequence of
   one or more elements, representable as an element plus an array" is a design.
3. **A type system is an obligation-propagation machine.** Its job is to track
   the cases you must handle. Exhaustiveness is what makes adding a case break
   every consumer — that is the whole value, so never defeat it.
4. **Pick the simplest representation that lets you write "this shouldn't
   happen" as rarely as possible.** Precision is not the goal. Total functions
   are.
5. **Types move obligations.** Widening a parameter to `Option<T>` is generous
   to callers and often unanswerable in the body. Narrowing it pushes the
   obligation to the caller, who usually knows what to do. Choose deliberately.

## Smell catalogue

Scan for these. The comment is usually the tell: **prose explaining what a value
means is an invariant the type system was supposed to carry.**

| Smell | Tell | Transformation |
|---|---|---|
| Comment-enforced correlation | "at least one of X or Y", "only valid when", "iff", "must be set", "ignored unless" | Sum type; each arm carries only the fields that arm makes meaningful |
| Sentinel value | a comment explaining what `-1` / `0` / `""` / `+inf` / `null` / `NOT_SET` means | `optional<T>`, or an arm of a sum type. Never overload the value domain |
| **Two** sentinels in one field | one magic value documented with two meanings | Highest severity — separate arms. This is a live ambiguity, not a style issue |
| Tag plus parallel fields | `uint8 type` / `enum kind` beside fields only some tags use | Variant with per-arm payload |
| Bool-plus-message result | `bool success; string message;` (and payload fields that are garbage on failure) | `Result` / `StatusOr` / `Either` |
| Refinement wish | `// must be >= 0`, `where len > 0`, a validate-on-every-read helper | Build from the positive space (principle 1) |
| Panic on an invariant | `unreachable`, `shouldn't happen`, `CHECK(false)`, `assert(false)`, `.unwrap()`, `InternalError("unreachable")` | Strengthen the *input* type — but only at this call site (principle 4) |
| Unanswerable `None` | `f(x: Option<T>)` whose `None` branch has no sensible action | Narrow the parameter; move the obligation to the caller |
| Duplicated enum | the same constants in two or more schema languages | One source of truth; derive or generate the rest, and assert agreement in a test |

## Language recipes

**C++17/20** — `std::variant`, `std::optional`, `absl::StatusOr` / `std::expected`.
Invariants that resist modelling: private constructor plus a static factory
returning `StatusOr<T>`.

Exhaustiveness requires a visitor with **no `auto` parameter**:

```cpp
template <class... Fs> struct Overloaded : Fs... { using Fs::operator()...; };

std::visit(Overloaded{
    [&](const Governing& g) { ... },
    [&](const HardStop& h) { ... },
}, state);   // adding an alternative → hard compile error at every call site
```

> **Trap:** `std::visit([&](auto& x) { if constexpr (...) ... }, v)` is the
> common idiom and is **not** exhaustive. A new alternative compiles clean with
> `-Wall -Wextra` and silently falls through. Verify by adding a dummy
> alternative and recompiling — do not assume. Never add an `auto` fallback to
> an `Overloaded`; it restores exactly the bug it exists to prevent.

**Python** — frozen dataclasses plus `A | B`; `match` with
`case _ as x: assert_never(x)` for exhaustiveness.

> **Trap:** this is enforced only if mypy or pyright runs in CI. Without that,
> Python exhaustiveness is decorative — check the CI config before claiming it.

**Protobuf** — `oneof` is a tagged product, not a sum type: `*_NOT_SET` is always
representable and a `*_case()` switch still needs an unreachable tail. So convert
`oneof` to a real sum type **once** at load/parse, and never pass the proto
inward. That unreachable tail at the boundary is the correct price, not a defect.
Use `optional` for field presence.

**ROS 2 `.msg`** — no unions, and every message is default-constructible, so
messages **cannot** hold invariants. Treat them strictly as wire format: parse
into a domain type in the subscription callback (C++: `rclcpp::TypeAdapter`),
flatten at publish. Because publishers upgrade independently, model the unknown
tag explicitly (`Unknown(uint8)`) so each subscriber is forced to handle "a newer
publisher sent something I don't understand".

**Across a pub/sub or RPC boundary the compiler cannot propagate obligations.**
Adding a variant breaks nothing in another package, language, repo, or a deployed
node. In a monorepo with one build, internal types keep the guarantee; public
contracts do not. Fix the internal type, flatten at the edge, and confine the
lossy re-encoding to that one function.

## Zero-copy / shared-memory payloads

`std::variant` and `std::optional` over trivially-copyable alternatives are
themselves trivially copyable and fixed-size, so they are legal shared-memory
payloads. Keep `static_assert(std::is_trivially_copyable_v<T>)` and
`static_assert(sizeof(T) == N)`. Before asserting a size, compile and print it —
never guess the layout.

Three real costs, all worth stating in a review:

- Variant layout is implementation-defined. Fine same-compiler/same-ABI; **not**
  safe for a reader in another language (Rust, etc.) on the same topic.
- Changing a payload breaks recorded logs/bags of the old layout. Bump the schema
  version *and* the type name so mismatched peers fail to connect rather than
  mis-parse.
- An out-of-range tag byte makes `std::visit` UB, where a POD struct would have
  yielded a merely-wrong value. If corruption is in scope on a safety path, use a
  hand-rolled `enum class Tag` + `union` + a `Visit()` with a `default:` arm:
  same modelling, controlled layout, defined fallback.

## When NOT to apply this

Restraint is part of the technique. Do not flag, and do not perform:

- **Strengthening a type where nothing would panic.** `sum()` over a possibly-empty
  list is fine; `.front()` is not. Only the second justifies a non-empty type.
- **Newtype wrappers for IDs or units.** These are speed bumps, not safety. Worth
  it only if the team actually makes that mistake.
- **Chasing maximally precise types.** Precision costs reuse. "As simple as
  possible, but no simpler" — a string is usually the right type for an email
  address, because nothing inspects its structure.
- **Types whose only consumer is a debug printer or a log line.**
- **Append-only or externally-versioned public contracts.** Fix the internal type
  and flatten at the boundary instead.

If the honest answer is "this is representable but harmless," say so and move on.
A review that flags every imprecise type teaches people to ignore the reviewer.

## Review output format

Rank by consequence, not by count:

1. Safety- or money-critical states that are representable and wrong
2. Findings that remove a runtime panic / `CHECK` / `unwrap`
3. Findings that remove a genuine ambiguity (two meanings, one value)
4. Everything else — usually not worth raising

Per finding:

- `path/to/file.ext:LINE`
- **The impossible state, with concrete values.** "`state == HARD_STOPPED` with
  `max_velocity == 1.5`" beats "the invariant is not enforced."
- The transformation, in a line or two of the target language
- What it removes: a panic, an ambiguity, or a comment
- Blast radius: which files and how many call sites the compiler will flag
- If it is not worth fixing, say that explicitly

Verify before reporting: compile the negative case, and check whether the
exhaustiveness you are relying on actually exists in the codebase's idiom.

## Source

Alexis King, *The Unreasonable Effectiveness of Constructive Data Modeling*
(Software Should Work 2026) — https://www.youtube.com/watch?v=0BXuYlNrUmE.
Related: *Parse, don't validate* — https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/
