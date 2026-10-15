#!/usr/bin/env python3
# PostToolUse (Bash): after a foreground wait loop, tell the agent how to wait instead.
#
# "Wait by notification" in CLAUDE.md lost to habit: in the week to 2026-10-15 agents ran
# 167 foreground Bash calls with `sleep` >= 30 s and 644 polling turns (2.2% of all tokens),
# each one a re-read of the whole context. This hook only advises. It never blocks, denies
# or delays a command (the user's rule since 2026-10-12: no check may stop an agent), and
# it says nothing for a command that ran with run_in_background.
#
# It prints a hookSpecificOutput.additionalContext note, which the agent reads with the
# tool result. Any error means silence: the hook must never be the thing that fails.

import json
import re
import sys

ADVICE = (
    "wait-advice: this command waited in the foreground ({why}). Each poll re-reads the "
    "whole context. Next time, run the wait with run_in_background and end the turn; its "
    "exit wakes you. For a timeout and a dead-process check, use "
    "`~/.claude/scripts/run-wait --timeout SECS [--pid PID] -- CHECK` in the background. "
    "For CI, `gh run watch <id> --interval 60 --exit-status` in the background."
)

LONG_SLEEP = re.compile(r"\bsleep\s+(\d+)")
LOOP = re.compile(r"\b(until|while)\b.*\bsleep\b", re.S)
WATCH = re.compile(r"\bgh\s+(run\s+watch|pr\s+checks\b[^|;&]*--watch)")


def reason(cmd: str) -> str | None:
    if LOOP.search(cmd):
        return "an until/while loop with sleep"
    if WATCH.search(cmd):
        return "a gh --watch"
    secs = [int(n) for n in LONG_SLEEP.findall(cmd)]
    if secs and max(secs) >= 30:
        return f"sleep {max(secs)}"
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        if data.get("tool_name") != "Bash" or tool_input.get("run_in_background"):
            return
        why = reason(tool_input.get("command") or "")
        if why is None:
            return
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": ADVICE.format(why=why),
        }}))
    except Exception:  # noqa: BLE001 — advice only; never fail the tool call
        return


main()
