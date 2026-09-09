# Global instructions

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
