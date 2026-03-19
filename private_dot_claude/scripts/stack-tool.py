#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# ///
"""
stack-tool: Git-notes-based stacked branch management.

Stores branch topology in git notes (refs/notes/stack) so stacked branch
workflows work without requiring GitHub PRs. Notes travel across clones
via explicit fetch/push of the notes ref.

Usage:
    stack-tool.py init <base> <branch1> [<branch2> ...]
    stack-tool.py discover [<top-branch>]
    stack-tool.py fetch-notes
    stack-tool.py push-notes
    stack-tool.py merge <branch> <base>
    stack-tool.py move-note <branch> <base>
    stack-tool.py push-branch <branch>
    stack-tool.py status [<top-branch>]

All output is JSON for easy consumption by Claude skills.
"""

from __future__ import annotations

import json
import subprocess
import sys


NOTES_REF = "refs/notes/stack"
NOTE_PREFIX = "stack-base:"


# ── helpers ──────────────────────────────────────────────────────────────


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def detect_remote() -> str:
    """Detect the remote name. Prefers 'origin', falls back to the first available remote."""
    r = git("remote", check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return "origin"  # fallback even if no remote exists (commands will fail with clear errors)
    remotes = r.stdout.strip().splitlines()
    if "origin" in remotes:
        return "origin"
    return remotes[0]


def default_branch() -> str:
    remote = detect_remote()
    r = git("remote", "show", remote, check=False)
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if "HEAD branch" in line:
                return line.split(":")[-1].strip()
    # fallback
    for name in ("main", "master"):
        if git("rev-parse", "--verify", f"refs/heads/{name}", check=False).returncode == 0:
            return name
    return "main"


def current_branch() -> str:
    return git("branch", "--show-current").stdout.strip()


def branch_tip(branch: str) -> str | None:
    r = git("rev-parse", "--verify", branch, check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def read_note(commit: str) -> str | None:
    """Read the stack-base note for a commit."""
    r = git("notes", "--ref=stack", "show", commit, check=False)
    if r.returncode != 0:
        return None
    for line in r.stdout.strip().splitlines():
        if line.startswith(NOTE_PREFIX):
            return line[len(NOTE_PREFIX) :].strip()
    return None


def find_stack_base(branch: str, max_count: int = 0) -> str | None:
    """Walk back from branch tip to find the nearest commit with a stack note.

    max_count=0 means unlimited (walks entire history). This ensures notes on
    long-lived branches are always found.
    """
    cmd = ["log", "--format=%H", branch]
    if max_count > 0:
        cmd.insert(2, f"--max-count={max_count}")
    r = git(*cmd, check=False)
    if r.returncode != 0:
        return None
    for sha in r.stdout.strip().splitlines():
        base = read_note(sha)
        if base is not None:
            return base
    return None


def resolve_merge_ref(base: str) -> str:
    """Resolve the best ref to merge from for a given base branch.

    Prefers the remote-tracking branch (e.g. origin/base) when it exists,
    falls back to the local branch. This handles local-only bases and repos
    where the remote uses a different name.
    """
    remote = detect_remote()
    remote_ref = f"{remote}/{base}"
    if git("rev-parse", "--verify", remote_ref, check=False).returncode == 0:
        return remote_ref
    if git("rev-parse", "--verify", base, check=False).returncode == 0:
        return base
    return remote_ref  # let git fail with a clear error


def write_note(branch: str, base: str) -> None:
    """Attach a stack-base note to the tip of branch."""
    tip = branch_tip(branch)
    if tip is None:
        raise RuntimeError(f"Branch {branch!r} does not exist")
    git("notes", "--ref=stack", "add", "-f", "-m", f"{NOTE_PREFIX} {base}", tip)


def output(data: dict) -> None:
    print(json.dumps(data, indent=2))


# ── commands ─────────────────────────────────────────────────────────────


def cmd_init(args: list[str]) -> None:
    """init <base> <branch1> [<branch2> ...]"""
    if len(args) < 2:
        output({"ok": False, "error": "Usage: init <base> <branch1> [<branch2> ...]"})
        sys.exit(1)

    base = args[0]
    branches = args[1:]
    results = []

    prev = base
    for br in branches:
        tip = branch_tip(br)
        if tip is None:
            results.append({"branch": br, "ok": False, "error": f"Branch {br!r} not found"})
            continue
        write_note(br, prev)
        results.append({"branch": br, "base": prev, "ok": True})
        prev = br

    output({"ok": True, "stack": results})


def cmd_discover(args: list[str]) -> None:
    """discover [<top-branch>]  — walk notes to find the full stack."""
    top = args[0] if args else current_branch()
    default = default_branch()
    stack: list[dict[str, str]] = []
    visited: set[str] = set()

    branch = top
    while branch and branch not in visited and branch != default:
        visited.add(branch)
        base = find_stack_base(branch)
        if base is None:
            output({
                "ok": False,
                "error": f"No stack-base note found for {branch!r}. Run 'init' first.",
                "partial_stack": list(reversed(stack)),
            })
            sys.exit(1)
        stack.append({"branch": branch, "base": base})
        branch = base

    stack.reverse()  # bottom-up order
    output({
        "ok": True,
        "default_branch": default,
        "top": top,
        "stack": stack,
    })


def cmd_fetch_notes(_args: list[str]) -> None:
    """Fetch stack notes from the remote."""
    remote = detect_remote()
    r = git("fetch", remote, f"{NOTES_REF}:{NOTES_REF}", check=False)
    output({
        "ok": r.returncode == 0,
        "message": r.stderr.strip() if r.returncode != 0 else f"Notes fetched from {remote}",
    })


def cmd_push_notes(_args: list[str]) -> None:
    """Push stack notes to the remote."""
    remote = detect_remote()
    r = git("push", remote, NOTES_REF, check=False)
    output({
        "ok": r.returncode == 0,
        "message": r.stderr.strip() if r.returncode != 0 else f"Notes pushed to {remote}",
    })


def cmd_merge(args: list[str]) -> None:
    """merge <branch> <base>  — checkout branch and merge base into it."""
    if len(args) < 2:
        output({"ok": False, "error": "Usage: merge <branch> <base>"})
        sys.exit(1)

    branch, base = args[0], args[1]

    # checkout
    r = git("checkout", branch, check=False)
    if r.returncode != 0:
        output({"ok": False, "error": f"Failed to checkout {branch}: {r.stderr.strip()}"})
        sys.exit(1)

    # merge — use remote-tracking ref when available, fall back to local
    merge_ref = resolve_merge_ref(base)
    r = git("merge", merge_ref, "--no-edit", check=False)
    if r.returncode != 0:
        # check if it's a conflict
        status = git("diff", "--name-only", "--diff-filter=U", check=False)
        conflicted = [f for f in status.stdout.strip().splitlines() if f]
        if conflicted:
            output({
                "ok": False,
                "conflict": True,
                "branch": branch,
                "base": base,
                "merge_ref": merge_ref,
                "conflicted_files": conflicted,
                "message": "Merge conflicts detected — resolve and continue",
            })
            sys.exit(1)
        output({"ok": False, "error": f"Merge failed: {r.stderr.strip()}"})
        sys.exit(1)

    output({
        "ok": True,
        "branch": branch,
        "base": base,
        "merge_ref": merge_ref,
        "message": f"Merged {merge_ref} into {branch}",
    })


def cmd_move_note(args: list[str]) -> None:
    """move-note <branch> <base>  — update the stack-base note to new branch tip."""
    if len(args) < 2:
        output({"ok": False, "error": "Usage: move-note <branch> <base>"})
        sys.exit(1)

    branch, base = args[0], args[1]
    write_note(branch, base)
    output({"ok": True, "branch": branch, "base": base, "tip": branch_tip(branch)})


def cmd_push_branch(args: list[str]) -> None:
    """push-branch <branch>  — push branch to origin."""
    if not args:
        output({"ok": False, "error": "Usage: push-branch <branch>"})
        sys.exit(1)

    branch = args[0]
    remote = detect_remote()
    r = git("push", remote, branch, check=False)
    output({
        "ok": r.returncode == 0,
        "branch": branch,
        "remote": remote,
        "message": r.stderr.strip() if r.returncode != 0 else f"Pushed {branch} to {remote}",
    })


def cmd_status(args: list[str]) -> None:
    """status [<top-branch>]  — show stack status with ahead/behind counts."""
    top = args[0] if args else current_branch()
    default = default_branch()
    stack: list[dict] = []
    visited: set[str] = set()

    branch = top
    while branch and branch not in visited and branch != default:
        visited.add(branch)
        base = find_stack_base(branch)
        if base is None:
            break

        # ahead/behind vs base — use remote-tracking ref when available, local otherwise
        base_ref = resolve_merge_ref(base)
        r = git("rev-list", "--left-right", "--count", f"{base_ref}...{branch}", check=False)
        behind, ahead = 0, 0
        if r.returncode == 0:
            parts = r.stdout.strip().split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])

        stack.append({
            "branch": branch,
            "base": base,
            "ahead": ahead,
            "behind": behind,
        })
        branch = base

    stack.reverse()
    output({
        "ok": True,
        "default_branch": default,
        "current_branch": current_branch(),
        "stack": stack,
    })


# ── main ─────────────────────────────────────────────────────────────────

COMMANDS = {
    "init": cmd_init,
    "discover": cmd_discover,
    "fetch-notes": cmd_fetch_notes,
    "push-notes": cmd_push_notes,
    "merge": cmd_merge,
    "move-note": cmd_move_note,
    "push-branch": cmd_push_branch,
    "status": cmd_status,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("Commands:", ", ".join(COMMANDS))
        sys.exit(0)

    cmd_name = sys.argv[1]
    cmd_args = sys.argv[2:]

    if cmd_name not in COMMANDS:
        output({"ok": False, "error": f"Unknown command: {cmd_name!r}"})
        sys.exit(1)

    try:
        COMMANDS[cmd_name](cmd_args)
    except Exception as e:
        output({"ok": False, "error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
