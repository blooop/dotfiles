#!/usr/bin/env python3
"""Give every PR in a stack its own view of one Mermaid diagram, and put it in the PR body.

The spec is one .mmd file: a normal diagram plus `%%` annotation lines, which Mermaid ignores.

    %% stack: 101 102 103              PR numbers, bottom of the stack first
    %% owns 101: gate                  ids (nodes or subgraphs) the PR adds or changes
    %% touches 101: bridge             ids it also changes without owning them
    %% note 101: One sentence on what this PR is in the picture.
    %% ticket: 100                     optional: the issue that gets the whole-stack view

In PR N's view, what N owns or touches is thick in N's colour and labelled "this PR", what an
earlier PR owns is thin in that PR's colour, what a later PR owns is grey and dashed, and an id
nobody owns is thin grey.

    stack.py render SPEC --out DIR    write each view and PR section to DIR, and check each view
    stack.py apply SPEC --out DIR     render, then replace the section in each PR body
    stack.py discover PR              print the `%% stack:` line for the stack PR belongs to
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PALETTE = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2", "#db2777"]
PALETTE_NAMES = ["blue", "green", "amber", "purple", "red", "cyan", "pink"]
GREY = "#8b949e"
START, END = "<!-- stack-diagram:start -->", "<!-- stack-diagram:end -->"
RENDER = Path(__file__).with_name("render.py")


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def parse(spec: str) -> tuple[str, list[str], dict, dict, dict, str | None]:
    stack, owns, touches, notes, body, ticket = [], {}, {}, {}, [], None
    for line in spec.splitlines():
        m = re.match(r"\s*%%\s*(stack|owns|touches|note|ticket)\b\s*(\d*)\s*:\s*(.*)$", line)
        if not m:
            body.append(line)
            continue
        kind, pr, rest = m.groups()
        if kind == "stack":
            stack = rest.split()
        elif kind == "ticket":
            ticket = rest.strip()
        elif kind == "note":
            notes[pr] = rest.strip()
        else:
            for ident in rest.split():
                (owns if kind == "owns" else touches).setdefault(pr, set()).add(ident)
    if not stack:
        sys.exit("spec has no `%% stack:` line")
    unknown = (set(owns) | set(touches) | set(notes)) - set(stack) - {ticket}
    if unknown:
        sys.exit(f"annotations name PRs outside the stack: {sorted(unknown)}")
    if len(stack) > len(PALETTE):
        sys.exit(f"at most {len(PALETTE)} PRs per stack diagram; split the diagram")
    return "\n".join(body).rstrip() + "\n", stack, owns, touches, notes, ticket


def mark_this_pr(src: str, ident: str) -> str:
    """Add a "this PR" line to a node's quoted label, or " · this PR" to a subgraph title."""
    sub = re.compile(rf'(^\s*subgraph\s+{re.escape(ident)}\s*\[")(.*?)("\])', re.M)
    if sub.search(src):
        return sub.sub(lambda m: f"{m[1]}{m[2]} · this PR{m[3]}", src, count=1)
    node = re.compile(rf'(?<![\w-]){re.escape(ident)}([\[\(\{{>]+)"(.*?)"')
    if node.search(src):
        return node.sub(lambda m: f'{ident}{m[1]}"{m[2]}<br/>this PR"', src, count=1)
    print(f"  note: {ident} has no quoted label, so only its border marks it", file=sys.stderr)
    return src


def view(body: str, stack: list[str], owns: dict, touches: dict, pr: str | None) -> str:
    """PR pr's view of the diagram; pr None is the whole stack, each part in its owner's colour."""
    colour = dict(zip(stack, PALETTE))
    owner = {i: p for p in stack for i in owns.get(p, ())}
    ids = set(owner) | {i for p in stack for i in touches.get(p, ())}
    here = stack.index(pr) if pr else len(stack)
    lines = []
    for ident in sorted(ids):
        mine = pr is not None and (owner.get(ident) == pr or ident in touches.get(pr, ()))
        if mine:
            style = f"stroke:{colour[pr]},stroke-width:4px"
            body = mark_this_pr(body, ident)
        elif ident not in owner:
            style = f"stroke:{GREY},stroke-width:1px"
        elif stack.index(owner[ident]) < here:
            style = f"stroke:{colour[owner[ident]]},stroke-width:2px"
        else:
            style = f"stroke:{GREY},stroke-width:1px,stroke-dasharray:5 4,color:{GREY}"
        lines.append(f"  style {ident} fill:transparent,{style}")
    return body + "\n".join(lines) + "\n"


def section(src: str, stack: list[str], notes: dict, pr: str | None, titles: dict, repo: str,
            ticket: str | None = None) -> str:
    if pr is None:
        return overview(src, stack, titles, repo, notes.get(ticket))
    legend = []
    for p, name in zip(stack, PALETTE_NAMES):
        mark = " ← this PR" if p == pr else ""
        legend.append(f"- {name}: [#{p} — {titles[p]}]({repo}/pull/{p}){mark}")
    note = f"{notes[pr]}\n\n" if pr in notes else ""
    return f"""{START}
## Where this fits

{note}```mermaid
{src.rstrip()}
```

A thick border marked **this PR** is what this PR adds or changes. A thin coloured border is an
earlier PR in the stack, which this PR builds on. Grey and dashed is a later PR.

{chr(10).join(legend)}
{END}"""


def overview(src: str, stack: list[str], titles: dict, repo: str, note: str | None) -> str:
    legend = "\n".join(f"- {name}: [#{p} — {titles[p]}]({repo}/pull/{p})" for p, name in zip(stack, PALETTE_NAMES))
    return f"""{START}
## How it fits together

{note + chr(10) + chr(10) if note else ""}```mermaid
{src.rstrip()}
```

Each border colour marks the PR that adds or changes that part. Thin grey is a part the stack
does not change.

{legend}
{END}"""


def place(body: str, sec: str) -> str:
    if START in body and END in body:
        return body[: body.index(START)] + sec + body[body.index(END) + len(END):]
    m = re.search(r"^## (?:Where this fits|How it fits together)\n.*?(?=^## )", body, re.S | re.M)
    if m:
        return body[: m.start()] + sec + "\n\n" + body[m.end():]
    m = re.search(r"^## What this changes\n.*?(?=^## )", body, re.S | re.M) or \
        re.search(r"^## Why\b.*?\n.*?(?=^## )", body, re.S | re.M)
    if m:
        return body[: m.end()] + sec + "\n\n" + body[m.end():]
    m = re.search(r"^## Stack\b", body, re.M)
    if m:
        return body[: m.start()] + sec + "\n\n" + body[m.start():]
    return body.rstrip() + "\n\n" + sec + "\n"


def render(args) -> tuple[list[str], dict, Path, str | None]:
    body, stack, owns, touches, notes, ticket = parse(Path(args.spec).read_text())
    repo = json.loads(gh("repo", "view", "--json", "url"))["url"]
    titles = {p: json.loads(gh("pr", "view", p, "--json", "title"))["title"] for p in stack}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sections, failed = {}, False
    for pr in [*stack, None] if ticket else stack:
        name = pr or f"ticket_{ticket}"
        mmd = out / f"view_{name}.mmd"
        mmd.write_text(view(body, stack, owns, touches, pr))
        sections[pr] = section(mmd.read_text(), stack, notes, pr, titles, repo, ticket)
        (out / f"section_{name}.md").write_text(sections[pr] + "\n")
        check = subprocess.run([str(RENDER), str(mmd), "--out", str(out / f"check_{name}")],
                               capture_output=True, text=True)
        print(f"{name}: " + "; ".join(l for l in check.stdout.splitlines() if "png" not in l))
        failed |= check.returncode != 0
    if failed:
        sys.exit("a view failed the check; fix the spec before applying")
    return stack, sections, out, ticket


def apply(args) -> None:
    stack, sections, out, ticket = render(args)
    targets = [("pr", pr, sections[pr]) for pr in stack] + ([("issue", ticket, sections[None])] if ticket else [])
    for kind, n, sec in targets:
        old = gh(kind, "view", n, "--json", "body", "-q", ".body")
        (out / f"body_{n}.orig.md").write_text(old)
        new = place(old, sec)
        if new.rstrip() == old.rstrip():
            print(f"#{n}: already current")
            continue
        (out / f"body_{n}.new.md").write_text(new)
        gh(kind, "edit", n, "--body-file", str(out / f"body_{n}.new.md"))
        live = gh(kind, "view", n, "--json", "body", "-q", ".body")
        print(f"#{n}: {'updated' if live.rstrip() == new.rstrip() else 'MISMATCH after edit'}"
              f" (original saved as {out / f'body_{n}.orig.md'})")


def discover(args) -> None:
    prs = json.loads(gh("pr", "list", "--state", "open", "--limit", "500",
                        "--json", "number,headRefName,baseRefName"))
    by_head = {p["headRefName"]: p for p in prs}
    by_base = {p["baseRefName"]: p for p in prs}
    start = next((p for p in prs if str(p["number"]) == args.pr), None)
    if not start:
        sys.exit(f"#{args.pr} is not an open PR")
    chain = [start]
    while chain[0]["baseRefName"] in by_head:
        chain.insert(0, by_head[chain[0]["baseRefName"]])
    while chain[-1]["headRefName"] in by_base:
        chain.append(by_base[chain[-1]["headRefName"]])
    print("%% stack: " + " ".join(str(p["number"]) for p in chain))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("render", render), ("apply", apply)):
        p = sub.add_parser(name)
        p.add_argument("spec")
        p.add_argument("--out", required=True)
        p.set_defaults(fn=fn)
    p = sub.add_parser("discover")
    p.add_argument("pr")
    p.set_defaults(fn=discover)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
