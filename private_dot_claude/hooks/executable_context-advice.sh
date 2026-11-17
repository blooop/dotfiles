#!/usr/bin/env python3
# PostToolUse (all tools): tell a SUBAGENT its context size once it passes 150k.
#
# CLAUDE.md asks a loop subagent to write its state to a handoff file and return at about
# 150k context. A subagent cannot see its own context size, so the rule never fires: in the
# week to 2026-11-17, 158 subagents peaked at >= 200k and subagent turns above 150k held 37%
# of all tokens (usage-review experiment E018). This hook reads the subagent's own
# transcript, and above 150k it adds one note per 25k step. It only advises. It never
# blocks, denies or delays a tool call (the user's rule since 2026-10-12), and it is silent
# in a parent session. Any error means silence.

import json
import os
import pathlib
import sys

AT = 150_000
STEP = 25_000
STATE = pathlib.Path.home() / ".cache" / "context-advice"
ADVICE = (
    "context-advice: your context is {k}k tokens; every tool call re-reads all of it. "
    "If you are in a loop (runs, retries, CI fixes) or a long task, finish the current step, "
    "write your state (goal, what is done, what is next, pids, paths) to the handoff file "
    "your brief names (or ~/.claude/handoffs/<date>-<topic>.md), and return a short summary "
    "that says where the handoff is. The parent starts a fresh agent from it."
)


def transcript(data: dict) -> pathlib.Path | None:
    agent = data.get("agent_id")
    path = data.get("transcript_path") or ""
    if agent and path:
        p = pathlib.Path(path)
        sub = p.with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
        if sub.exists():
            return sub
    if "/subagents/" in path:
        return pathlib.Path(path)
    return None  # a parent session, or no way to tell: stay silent


def last_context(p: pathlib.Path) -> int:
    with p.open("rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 400_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            u = json.loads(line)["message"]["usage"]
        except (ValueError, KeyError, TypeError):
            continue
        return (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                + u.get("cache_creation_input_tokens", 0))
    return 0


def main() -> None:
    try:
        data = json.load(sys.stdin)
        p = transcript(data)
        if p is None:
            return
        ctx = last_context(p)
        if ctx < AT:
            return
        step = (ctx - AT) // STEP
        STATE.mkdir(parents=True, exist_ok=True)
        mark = STATE / p.stem
        if mark.exists() and int(mark.read_text() or -1) >= step:
            return
        mark.write_text(str(step))
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": ADVICE.format(k=ctx // 1000),
        }}))
    except Exception:  # noqa: BLE001 — advice only; never fail the tool call
        return


main()
