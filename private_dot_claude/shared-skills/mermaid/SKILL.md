---
name: mermaid
description: Draw a legible Mermaid diagram for a PR, issue, ticket, README or doc that GitHub renders natively, checked by a throwaway render before it ships. Use when asked for a diagram (architecture, data flow, sequence, state), to diagram a PR or a stack of PRs (your own or someone else's), or when adding or editing a ```mermaid block.
---

# Mermaid

The deliverable is **Mermaid source** in a ```mermaid fence, which GitHub draws in PR bodies,
issues, comments and `.md` files with no build step. Renders exist only so you can look at
your own output: they go to a temp directory and are never committed, attached or linked.

A diagram earns its place when it shows a mechanism a cold reader would otherwise assemble
from prose: where data flows, which process owns what, which part a PR changes. If a
sentence says it, write the sentence.

## Where it goes

The argument, if any, names what to draw: a PR, a stack (any PR in it), an issue, or a file.
For a PR, read its body and `gh pr diff` first; the mechanism is in the diff, not the title.

- **Your own PR or issue**: the diagram goes in the body, in a `## Where this fits` section.
- **Someone else's**: never edit their body. Post the section as your own comment
  (`gh pr comment --body-file`), or for a stack, `stack.py apply --comment`, which edits that
  same comment on a rerun instead of adding another.
- **A file**: the fence goes where the file's reader needs it; a README's goes near the top.

## Steps

1. **State the claim.** One sentence: what the reader should see. Every node and edge
   either serves that sentence or goes.
2. **Draft** against the [layout rules](#layout-rules). Save it as a `.mmd` in the scratchpad.
3. **Self-check.** Run `~/.claude/skills/mermaid/scripts/render.py <file.mmd|file.md>`
   (a `.md` renders each of its fences), adding `--out <scratchpad>/mermaid-check` when the
   session has a scratchpad. It draws the diagram in **GitHub's own Mermaid viewer**, light
   and dark, at GitHub's column width, and flags a syntax error, a clipped label, a diagram
   GitHub would shrink, and more than 20 nodes. Read both PNGs. The step is done when the
   script exits 0 and in both themes you can read every label, with no edge crossing a label
   or a box. Fix and rerun; three rounds is plenty, and past that cut nodes. The check needs
   network access to GitHub's viewer; the source stays in the local browser.
4. **Deliver** the source in a ```mermaid fence. If colour carries meaning, say what each
   colour means in the prose beside the fence, since a Mermaid legend is clumsy.

## Layout rules

**Width is legibility.** GitHub fits a diagram to a column of about 880px, so a 1500px
diagram shows its text at 58%. The script warns below 90%. Width comes from how many things
sit side by side: the widest rank, plus long labels. Cut there first: stack a two-word name
on two lines (`<b>Image</b><br/><b>Transcoder</b>`) inside a left-to-right row.

**Fewer boxes, more text per box.** A component that only lists what it does is one node
with lines, not a subgraph of small nodes. A caller or a tool the diagram's claim does not
hinge on becomes a line of text in the node it talks to, not a node of its own. Aim for
about 12 nodes, 20 at most; past that, draw two diagrams.

**Layers down, data across.** `flowchart TB` for the layers (config → supervisor →
process → storage → consumer), and `direction LR` inside the subgraph where data moves
through stages. Mermaid ignores a subgraph's `direction` when any edge joins one of its
inner nodes to a node outside it, so outer edges attach to the subgraph id itself.
Keep nesting to one subgraph level.

**Name, then detail.** `<b>Name</b><br/>what it does`, one short line per fact. Break lines
yourself with `<br/>`; keep each line under about 35 characters. Size text only with `<b>`:
GitHub draws `<small>` at full size inside a box Mermaid measured for small text, so every
such label is cut off. Write `<` and `>` inside a label as `#lt;` and `#gt;`.

**Colour the strokes, never the fills.** GitHub picks a light or a dark Mermaid theme per
viewer, and a fill you set stays put in both. Open with `classDef default fill:transparent`,
give each subgraph `style <id> fill:transparent`, and carry meaning in `stroke` at
`stroke-width:2px`. Mid-tone hues read on white and on `#0d1117` alike: `#2563eb` blue,
`#16a34a` green, `#d97706` amber, `#9333ea` purple, `#dc2626` red. Dashed
(`stroke-dasharray:5 4`) marks a part outside the change.

**Label an edge only with its verb.** One to three words, where the edge is not obvious
(`compiled YAML`, `RGB`, `SIGINT`). An edge that crosses the diagram to say "also uses"
becomes text in the node instead.

**Straight edges, tight spacing.** GitHub honours this frontmatter; start with it:

```
---
config:
  flowchart:
    curve: linear
    nodeSpacing: 24
    rankSpacing: 36
    wrappingWidth: 340
---
```

## One diagram across a stack of PRs

The architecture is drawn **once**, in a spec file, and each PR's view is generated from it and
from that PR's diff, so the diagram shows the reviewer the code they can see, in place in the
wider stack. An architecture change is one edit and one rerun. The spec is a normal diagram
with no PR styling, plus `%%` annotation lines (Mermaid ignores them):

```
%% stack: 101 102 103                 bottom first; `stack.py discover <pr>` prints this line
%% files gate: *rate_gate*             fnmatch patterns (`*` crosses `/`) for each box's code
%% files bag:                          a box with no code of its own: empty, but listed
%% touches 101: bridge                 rare: a change no file pattern can catch
%% note 102: What this PR is in the picture, in a sentence or two, links written out.
%% ticket: 100                         optional: the issue gets the whole-stack view
%% note 100: The claim the whole diagram makes.
```

Give **every** box and subgraph a `files` line, so each one is styled in every view. In PR N's
view, a box N's diff changes is thick in N's colour and reads "this PR"; solid grey is code N
uses as it is; dashed grey is code a later PR changes. Changed files that no pattern catches
are listed under the diagram by package, so the picture never hides part of the diff; if the
list names code a reviewer would expect to see, it wants a box. The ticket's view colours
each box by the last PR that changes it, with a legend linking every PR.

1. Keep the spec at `~/.claude/stack-diagrams/<ticket>-<topic>.mmd`, which outlives the
   session and the container.
2. `stack.py render <spec> --out <scratchpad>/stack` prints which boxes each diff lights, writes
   every view and section, and runs the self-check on each. Check the lit boxes against each
   PR's purpose, and read the views' PNGs as in step 3 above.
3. `stack.py apply <spec> --out <scratchpad>/stack` renders, then replaces the section between
   `<!-- stack-diagram:start -->` and `:end -->` in each body (or inserts it after
   `## What this changes`), saves every original body in `--out`, and confirms each live body.
   A body already current is left alone. Editing PRs and the ticket is outward-facing: apply
   when the user asked for it.

Rerun `apply` after the architecture changes, after a push changes a PR's diff, or after a PR
joins the stack.

## GitHub compatibility

GitHub bundles its own Mermaid (11.17.2 when this was written), which is why the check
renders there rather than with a stock Mermaid: a stock render measures and draws with the
same font and CSS, so it can never show a clipped label. Verified on GitHub's viewer:

- the frontmatter `config:` block works (`curve`, spacing, `wrappingWidth`)
- `<b>` works
- `<small>` breaks: it clips the label
- `opacity` in a `classDef` is untested

When a new feature is in question, render a variant with and without it: the clip count
names the cause. Record the result here.
