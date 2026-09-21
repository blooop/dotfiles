# Global instructions

## How you write to me

Write every message to me in ASD-STE100 Simplified Technical English, the controlled
language ASD publishes for maintenance documentation. Short, plain and unambiguous beats
fluent. The rules that carry the weight:

- Use the active voice, and name who does the thing.
- Write one idea per sentence. Keep an instruction to 20 words, a statement to 25.
- Keep a paragraph to six sentences.
- Start an instruction with its verb: "Run the suite", not "The suite should be run".
- Use one word for one thing, in every message. Repeat the word instead of varying it.
- Use simple tenses. Keep `-ing` forms for technical names.
- Keep the articles and the relative pronouns: "the test that failed", not "test failed".
- Keep a noun cluster to three words.
- Put a warning before the step it applies to.

I do not hold the STE approved-word list verbatim, so read "approved words only" as "use
the plainest common word that says it": *start*, not *initiate*; *use*, not *utilize*;
*fix*, not *remediate*.

This governs the prose I read in chat, and it outranks any other voice guidance there.
Code, commands, file paths and quoted output stay verbatim. Prose you write for somewhere
else — a commit body, a PR description, a README — follows that destination's rules. The
link rules below apply to every message.

## Links

Every reference to a GitHub issue, PR, commit, or any URL goes in chat as a clickable
markdown link — `[#502 — title](https://github.com/org/repo/issues/502)`, never a bare
`#502` and never a bare URL. The terminal renders markdown, so a linked reference is one
click; a bare `#502` is a manual search.

This applies to *every* occurrence in a message, not just the first mention — sweep the
whole message before sending, closing "next steps" paragraph included. A bare `#N` inside
a link's own title text is fine.

**Never put a link inside a markdown table.** Table cells do not linkify in the terminal,
so a `[#502 — title](url)` in a table renders as dead text and the link is lost. Anything
with links is a list, never a table — even when the data is tabular and a table would lay
it out better. Put the link first in each bullet and hang the other fields off it:

```
- [#11094 — ros: Fix four tests that depend on what else ran](https://github.com/org/repo/pull/11094)
  base `main` · 7 files · +88/−112
```

The same goes for anything else that swallows a link: code fences, blockquote-only
summaries, and shell snippets that list bare PR numbers. If a command needs bare numbers
(`for n in 11094 11095; do ...`), link those PRs in the prose around it.

## Verifying before you report

"I could not run the tests" is a claim, and it needs evidence like any other. Before
making it, find the project's real runner. Containerized repos on this host come up with
`dl <org>/<repo>@<branch>`; many repos also ship their own entry point, and a README
usually names it. A missing or stale `.venv` is not evidence that a suite cannot run —
it almost always means you looked in the wrong place.

This matters most when reviewing or debugging. A failure you have actually reproduced is
worth more than five careful readings, and an argument you hand someone where you could
have handed them a reproduction is the weaker thing to have sent.

**When you delegate, put the runner in the subagent's brief.** Subagents read this file,
but they do not inherit the parent session's recalled memories — so anything you know
only from memory has to be restated in the prompt, or it never reaches them.
