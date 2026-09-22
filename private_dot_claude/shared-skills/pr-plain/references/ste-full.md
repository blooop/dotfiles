# ASD-STE100, and a worked rewrite

## What the specification is

**ASD-STE100 Simplified Technical English** is a controlled-language standard written for
aerospace and defence maintenance documentation, where a sentence that can be read two ways
is a safety defect. It began as AECMA Simplified English in the 1980s and is maintained by
the Simplified Technical English Maintenance Group (STEMG) at the AeroSpace, Security and
Defence Industries Association of Europe. The specification is free on request from
[asd-ste100.org](https://www.asd-ste100.org/) — get it from there rather than trusting a
summary, including this one.

It has two parts:

- **Part 1, the writing rules.** Around 65 rules, grouped into sections on words, noun
  clusters, verbs, sentences, procedural writing, descriptive writing, warnings and cautions,
  and punctuation.
- **Part 2, the Dictionary.** Around 900 approved words. Each approved word has one part of
  speech and one meaning, with the unapproved alternatives listed beside it. The dictionary
  is the part you cannot reconstruct from memory, which is why
  [word-swaps.md](word-swaps.md) gives a test instead of a copy.

A PR description is **descriptive writing** in the specification's sense, so the descriptive
limits are the ones that bind: 25 words per sentence, 6 sentences per paragraph, one topic
per paragraph, active voice, simple tenses.

## Rules the SKILL file leaves out

These bite less often in a PR body, and apply when a description contains the thing they
govern.

**Procedures.** A set of steps someone must follow — reproduction instructions, a migration a
reviewer runs — obeys the procedural rules. 20 words per sentence. One instruction per
sentence. Start each step with the command verb: *Set the poll interval to 6 seconds.* Put
the condition first: *If the test fails, read the run log.* Use a numbered list, never a
paragraph of prose with the steps buried in it.

**Warnings and cautions.** Anything a reader can do that loses work or breaks an environment
goes **before** the step it applies to, never after. Start it with the command, and say the
condition and the consequence: *Do not rebase this branch. The stacked PRs below it lose
their base and close.*

**Technical names.** A noun or noun phrase that names a real thing — a function, a topic, a
tool, a part — may be used even though it is not in the dictionary. The rule that comes with
that permission is consistency: one technical name for one thing, written the same way every
time. A technical name does not become a verb. Write *the test starts the simulator*, not
*the test restarts-the-sim*.

**Punctuation.** Standard marks only. No slash to mean *and/or* — write *and*, or *or*, and
say which. No ampersand. No dash used as a general-purpose joint between two half-thoughts;
the specification wants a full stop and a second sentence, which is also the fastest way to
get under 25 words. Parentheses hide information a reader skips, so a fact worth stating goes
in a sentence of its own.

## A worked rewrite

From [#11811](https://github.com/kinisi-robotics/kinisi_ros/pull/11811). The original:

> That wait returns on the first `/status` poll that observes RUNNING **or any later state**
> (`_state_reached`, added in [#7779](https://github.com/kinisi-robotics/kinisi_ros/pull/7779)
> so a skipped state does not strand the wait). The client polls every 0.5s, and both pre-tick
> states — RUNNING and COMPILING — routinely fit inside one interval. When they do, the wait
> returns with the new session's clock already ticking, `reset()` clears the latch, and the
> first sample it then catches is wherever the clock had got to.

Three sentences of 28, 17 and 31 words, so two are over the 25-word limit. It also carries
an -ing form (*ticking*), two idioms (*strand the wait*, *wherever the clock had got to*), a
parenthesis holding a fact the reader needs, and a dash pair holding another. The third
sentence states three separate facts.

The rewrite:

> The client asks the simulator for its state every 0.5 seconds. The wait stops at the first
> answer that says `RUNNING`, or any state after it.
> [#7779](https://github.com/kinisi-robotics/kinisi_ros/pull/7779) made the wait accept a
> later state, so a state the client does not see cannot make the wait run forever.
>
> The simulator goes through two states before the clock starts: `RUNNING` and `COMPILING`.
> Both states often happen inside one 0.5 second gap. Then the wait ends after the new clock
> already started. The test clears its record too late, and it reads the clock somewhere in
> the middle of the new session.

Seven sentences, the longest 22 words, all active, no -ing forms, no idiom. Both links survive.
`RUNNING` and `COMPILING` are technical names and are written the same way every time. The
paragraph break separates the two topics: what the wait does, and why that is wrong here.

The rewrite is 100 words against the original's 76. That is the correct direction.
