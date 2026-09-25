#!/usr/bin/env python3
"""Give every PR in a stack a view of one Mermaid diagram that matches its diff.

The spec is one .mmd file: a normal diagram plus `%%` annotation lines, which Mermaid ignores.

    %% stack: 101 102 103              PR numbers, bottom of the stack first
    %% files gate: *rate_gate*         fnmatch patterns (`*` crosses `/`) for the code a node
                                       or subgraph id stands for; a PR's diff lights what it hits
    %% touches 101: bridge             ids a PR changes that no file pattern catches
    %% note 101: One sentence on what this PR is in the picture.
    %% ticket: 100                     optional: the issue that gets the whole-stack view

In PR N's view, the ids N's diff changes are thick in N's colour and labelled "this PR"; an id
only a later PR changes is grey and dashed; everything else, which N uses as it is, is solid
grey. Changed files no pattern catches are listed under the diagram, so it never hides code.
The ticket's view colours each id by the last PR that changes it.

    stack.py render SPEC --out DIR    write each view and section to DIR, and check each view
    stack.py apply SPEC --out DIR     render, then replace the section in each body
    stack.py apply SPEC --out DIR --comment
                                      post it as your own comment instead (someone else's PRs);
                                      a rerun edits that comment rather than adding another
    stack.py discover PR              print the `%% stack:` line for the stack PR belongs to
"""

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

PALETTE = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2", "#db2777"]
PALETTE_NAMES = ["blue", "green", "amber", "purple", "red", "cyan", "pink"]
GREY = "#8b949e"
START, END = "<!-- stack-diagram:start -->", "<!-- stack-diagram:end -->"
RENDER = Path(__file__).with_name("render.py")
PR_LINE = re.compile(r"\s*%%\s*(stack|touches|note|ticket)\b\s*(\d*)\s*:\s*(.*)$")
FILES_LINE = re.compile(r"\s*%%\s*files\s+(\S+)\s*:\s*(.*)$")


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


class Spec:
    def __init__(self, text: str):
        self.stack, self.files, self.touches, self.notes, self.ticket = [], {}, {}, {}, None
        body = []
        for line in text.splitlines():
            if m := FILES_LINE.match(line):
                self.files[m[1]] = m[2].split()
            elif m := PR_LINE.match(line):
                kind, pr, rest = m.groups()
                if kind == "stack":
                    self.stack = rest.split()
                elif kind == "ticket":
                    self.ticket = rest.strip()
                elif kind == "note":
                    self.notes[pr] = rest.strip()
                else:
                    self.touches.setdefault(pr, set()).update(rest.split())
            else:
                body.append(line)
        self.body = "\n".join(body).rstrip() + "\n"
        if not self.stack:
            sys.exit("spec has no `%% stack:` line")
        if len(self.stack) > len(PALETTE):
            sys.exit(f"at most {len(PALETTE)} PRs per stack diagram; split the diagram")
        unknown = (set(self.touches) | set(self.notes)) - set(self.stack) - {self.ticket}
        if unknown:
            sys.exit(f"annotations name PRs outside the stack: {sorted(unknown)}")

    def changes(self, diffs: dict[str, list[str]]) -> tuple[dict[str, set], dict[str, list]]:
        """Per PR: the ids its diff changes, and the changed files no pattern catches."""
        hit, loose = {}, {}
        for pr in self.stack:
            hit[pr] = set(self.touches.get(pr, ()))
            loose[pr] = []
            for path in diffs[pr]:
                ids = {i for i, pats in self.files.items() if any(fnmatch.fnmatch(path, p) for p in pats)}
                hit[pr] |= ids
                if not ids:
                    loose[pr].append(path)
        return hit, loose


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


def pr_view(spec: Spec, hit: dict, pr: str) -> str:
    body, here = spec.body, spec.stack.index(pr)
    later = set().union(*(hit[p] for p in spec.stack[here + 1:])) - hit[pr]
    lines = []
    for ident in sorted(spec.files.keys() | set().union(*hit.values())):
        if ident in hit[pr]:
            style = f"stroke:{PALETTE[here]},stroke-width:4px"
            body = mark_this_pr(body, ident)
        elif ident in later:
            style = f"stroke:{GREY},stroke-width:1px,stroke-dasharray:5 4,color:{GREY}"
        else:
            style = f"stroke:{GREY},stroke-width:1px"
        lines.append(f"  style {ident} fill:transparent,{style}")
    return body + "\n".join(lines) + "\n"


def ticket_view(spec: Spec, hit: dict) -> str:
    last = {i: n for n, pr in enumerate(spec.stack) for i in hit[pr]}
    lines = [f"  style {i} fill:transparent,stroke:{PALETTE[n]},stroke-width:2px" for i, n in sorted(last.items())]
    lines += [f"  style {i} fill:transparent,stroke:{GREY},stroke-width:1px" for i in sorted(spec.files.keys() - last.keys())]
    return spec.body + "\n".join(lines) + "\n"


def outside(paths: list[str]) -> str:
    if not paths:
        return ""
    def area(p: str) -> str:
        parts = PurePosixPath(p).parts
        return "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else p)
    counts = Counter(area(p) for p in paths)
    listed = ", ".join(f"`{a}` ({n})" for a, n in sorted(counts.items()))
    return f"\nThis diff also changes files that the diagram does not show: {listed}.\n"


def pr_section(src: str, spec: Spec, pr: str, loose: list[str]) -> str:
    note = f"{spec.notes[pr]}\n\n" if pr in spec.notes else ""
    return f"""{START}
## Where this fits

{note}```mermaid
{src.rstrip()}
```

A thick border marked **this PR** is code that this diff changes. Solid grey is code that this PR
uses as it is. Dashed grey is code that a later PR in the stack changes.
{outside(loose)}{END}"""


def ticket_section(src: str, spec: Spec, titles: dict, repo: str) -> str:
    note = f"{spec.notes[spec.ticket]}\n\n" if spec.ticket in spec.notes else ""
    legend = "\n".join(f"- {name}: [#{p} — {titles[p]}]({repo}/pull/{p})" for p, name in zip(spec.stack, PALETTE_NAMES))
    return f"""{START}
## How it fits together

{note}```mermaid
{src.rstrip()}
```

Each border colour marks the last PR that changes that part. Thin grey is a part the stack
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


def render(args) -> tuple[Spec, dict, Path]:
    spec = Spec(Path(args.spec).read_text())
    repo = json.loads(gh("repo", "view", "--json", "url"))["url"]
    titles = {p: json.loads(gh("pr", "view", p, "--json", "title"))["title"] for p in spec.stack}
    diffs = {p: gh("pr", "diff", p, "--name-only").split() for p in spec.stack}
    hit, loose = spec.changes(diffs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    views = {pr: (pr_view(spec, hit, pr), lambda src, pr=pr: pr_section(src, spec, pr, loose[pr])) for pr in spec.stack}
    if spec.ticket:
        views[spec.ticket] = (ticket_view(spec, hit), lambda src: ticket_section(src, spec, titles, repo))
    sections, failed = {}, False
    for n, (src, make) in views.items():
        (out / f"view_{n}.mmd").write_text(src)
        sections[n] = make(src)
        (out / f"section_{n}.md").write_text(sections[n] + "\n")
        check = subprocess.run([str(RENDER), str(out / f"view_{n}.mmd"), "--out", str(out / f"check_{n}")],
                               capture_output=True, text=True)
        lit = sorted(hit[n]) if n in hit else "whole stack"
        print(f"#{n}: lights {lit}; " + "; ".join(l for l in check.stdout.splitlines() if "png" not in l))
        failed |= check.returncode != 0
    if failed:
        sys.exit("a view failed the check; fix the spec before applying")
    return spec, sections, out


def comment(n: str, sec: str, out: Path) -> None:
    """Create or update the one comment of ours on issue or PR n that carries the section."""
    nwo = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
    me = gh("api", "user", "-q", ".login").strip()
    pages = json.loads(gh("api", f"repos/{nwo}/issues/{n}/comments", "--paginate", "--slurp"))
    ours = [c for page in pages for c in page if c["user"]["login"] == me and START in c["body"]]
    path = out / f"comment_{n}.md"
    path.write_text(sec + "\n")
    if ours and ours[0]["body"].rstrip() == sec.rstrip():
        print(f"#{n}: comment already current")
        return
    if ours:
        gh("api", "-X", "PATCH", f"repos/{nwo}/issues/comments/{ours[0]['id']}", "-F", f"body=@{path}")
        print(f"#{n}: comment updated ({ours[0]['html_url']})")
    else:
        url = gh("issue", "comment", n, "--body-file", str(path)).strip()
        print(f"#{n}: comment posted ({url})")


def apply(args) -> None:
    spec, sections, out = render(args)
    for n, sec in sections.items():
        if args.comment:
            comment(n, sec, out)
            continue
        kind = "issue" if n == spec.ticket else "pr"
        old = gh(kind, "view", n, "--json", "body", "-q", ".body")
        new = place(old, sec)
        if new.rstrip() == old.rstrip():
            print(f"#{n}: already current")
            continue
        (out / f"body_{n}.orig.md").write_text(old)
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
        if name == "apply":
            p.add_argument("--comment", action="store_true",
                           help="post as your own comment instead of editing the body")
        p.set_defaults(fn=fn)
    p = sub.add_parser("discover")
    p.add_argument("pr")
    p.set_defaults(fn=discover)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
