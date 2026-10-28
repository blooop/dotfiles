---
name: pr-plain
description: Rewrite a PR description in ASD-STE100 Simplified Technical English so a tired reader or a non-native speaker gets it in one pass. Use when asked what a PR does in simple terms, to make a PR description simpler, plainer, more readable or easier to understand, or to write one in Simplified Technical English.
---

# Plain PR

Rewrite a PR description so a reader who is tired, in a hurry, or reading English as a
second language understands it the first time. The standard is **ASD-STE100 Simplified
Technical English**: the aerospace maintenance-documentation spec, where a wrong reading
grounds an aircraft. Simple words, whole facts.

A plain description is not a shorter or vaguer one. Every number, link, file path, error
string and claim in the original survives the rewrite. What goes is the effort of reading.

## Steps

1. **Get the original.** Default to the current branch's PR (`gh pr view --json number,title,body,url`).
   A number, a branch or pasted text overrides that. Save the body to the scratchpad before
   you touch it, so the original is recoverable.
2. **List what the description asserts.** Every claim, number, identifier, link, code block
   and piece of evidence, as a flat list. This list is the contract: the rewrite is finished
   when each entry appears in it. Read the diff where a claim is unclear — a description you
   do not understand cannot be made plain, and guessing produces confident wrong prose.
3. **Name the thing once.** Pick one word for each moving part and write that word every
   time. See [one word, one meaning](#one-word-one-meaning).
4. **Rewrite** against the [rules](#the-rules). Keep the structure that already works
   (what was wrong → how it was found → the fix → the tests); a reader looking for one of
   those should find it under a heading that says so. Order it as a news story — see
   [write it like a news story](#write-it-like-a-news-story).
5. **Check the contract.** Walk the step 2 list against the rewrite, entry by entry. Then
   read the rewrite once as a stranger: any sentence you must read twice is not done.
6. **Deliver.** Asked to update the PR: `gh pr edit <n> --body-file <path>`, then give the
   user the PR link. Asked only to explain: print the rewrite and offer the update in one line.

## Write it like a news story

A reviewer reads a description the way people read a newspaper: the headline, then the first
paragraph, then further only if they care. So build it as an inverted pyramid. The most
important fact comes first, and each layer adds detail. A reader who stops after any layer
has a true picture, only a less detailed one.

1. **Headline: the PR title.** One statement of what is true after the merge, in the repo's
   commit style, under 70 characters: `ci: Rebuild the x64 base on main when a cancelled run
   missed it`. A verb and a result, not a topic (`ci: base image fixes`).
2. **Lede: the first line of the body.** One or two sentences, in bold: what changes for whom,
   and why it matters. No identifiers a stranger must look up.
3. **`## In short`.** The problem, then the fix, in about eight sentences, for a reviewer who
   knows the repo but not this corner of it. Say the problem as the system's behaviour, not
   the code's shape, and end it on what a user would see. When two things disagree, name both
   and say how each works, as a numbered list. Say the fix as what is true now.
4. **`## Evidence`.** Now the reader knows what each graph measures.
5. **The detail.** What changes, how it was checked, the mechanism. Bulky material that only a
   close reviewer needs (long logs, full tables, command lists, long pseudocode) goes in a
   `<details><summary>…</summary>` block whose summary says what is inside.

**Explain a term where it first appears**, in plain words, in the layer that first needs it:
*"the pin (the file in GCS that names main's newest base image)"*. A term the lede or
`## In short` needs is explained there. Never collect terms in a glossary section. If the
description coins a word, coin it once and then use only that word.

Never move to a deeper layer a fact that a shallow reader needs to decide: a risk, a one-way
door, a behaviour change. `## Merge danger` stays open, never inside `<details>`.

The test: a reviewer who reads only the title and the lede can say what the PR does. One who
also reads `## In short` can say why, and can read the evidence. If you cannot write the lede
without reading the diff, read the diff: a vague lede is worse than none.

## The rules

**Short sentences.** 25 words maximum for descriptive text, 20 for an instruction. One
thought per sentence. One instruction per sentence.

**Short paragraphs.** Six sentences maximum, one topic each, the topic in the first sentence.

**Active voice.** *The client polls the status every 0.5s*, not *the status is polled*.
Passive earns its place only where the actor is genuinely unknown or irrelevant.

**Simple tenses.** Present, past, future. Not *had been returning*, not *will have been*.

**No -ing words.** Rewrite *arming the gate before issuing the restart* as *the test turns
the filter on before it starts the restart*. An -ing word survives only inside a technical
name.

**Three nouns maximum in a row.** *The restart state wait return timing* is a noun cluster;
break it with prepositions and a verb: *when the wait for the new state returns*.

**Keep the small words.** Articles (*a*, *the*) and *that* stay in. Dropping them to save a
word costs the reader more than it saves.

**Say it straight.** No idiom, no metaphor, no understatement, no joke that depends on tone.
*The wait can return with the clock already ticking* is fine, because a clock does tick.
*The answer is answerable from the stream* is not English anyone speaks.

**Plain word, every time.** Use the shortest common word that carries the meaning — see
[word swaps](references/word-swaps.md).

**Lists for lists.** Three or more parallel items become a vertical list. Conditions come
before the action: *If the sim never zeroes, the test fails and prints the value.*

### One word, one meaning

The strongest rule and the one that hurts. Write **one word for one thing, every time**, and
one meaning for each word. A description that calls the same mechanism a gate, then a latch,
then a filter, then a threshold, has asked the reader to work out that these are one thing.
Pick the word a newcomer can picture (*filter*), define it once in the sentence that
introduces it, and never reach for a synonym — repetition is the point, not a weakness.

The same rule protects the identifiers: a **technical name** — a function, a file, a state,
an error string, a flag — is written exactly as the code writes it, every time, in code
formatting. Never translate `SimState.SIMULATING` into prose.

## What does not change

- **Links stay links.** Every reference stays a markdown link, and a link never moves into a
  table. Plain English is not an excuse for a bare `#11811`.
- **Evidence stays exact.** Error strings, timings, sample values, run links and file paths
  are copied, not paraphrased. `first sample 0.302s` never becomes *about a third of a second*.
- **Claims stay as strong as they were, and no stronger.** A test that ran on CI says so and
  links the run. A test that did not run is not described as passing.
- **The trailer stays.** Whatever attribution line the body ended with ends the rewrite.

## Reference

- [word-swaps.md](references/word-swaps.md) — the plain word for the long one.
- [ste-full.md](references/ste-full.md) — the rest of ASD-STE100: procedures, warnings,
  technical names, punctuation, and what the specification is.
