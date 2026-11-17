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
    "whole context. If you are the parent session: run the wait with run_in_background and "
    "end the turn; its exit wakes you. Use `~/.claude/scripts/run-wait --timeout SECS "
    "[--pid PID] -- CHECK` for a timeout and a dead-process check, and for CI "
    "`gh pr checks <n> --watch --fail-fast --interval 60`, which stops at the first failed "
    "check. If you are a subagent: you may not end the turn to wait, so make ONE foreground "
    "call, `~/.claude/scripts/run-wait --timeout 590 --every 30 [--pid PID] -- CHECK` with "
    "the Bash timeout at 600000, and repeat it only when it exits 124. No shorter windows."
)

LONG_SLEEP = re.compile(r"\bsleep\s+(\d+)")
# A real shell loop: `until|while <cond>; do ... sleep ...`. Prose such as "no until/sleep
# loops" in a heredoc matched the old pattern (2026-11-16: a script write got the advice).
LOOP = re.compile(r"\b(until|while)\b[^\n]*?[;\n]\s*do\b.*\bsleep\b", re.S)
WATCH = re.compile(r"\bgh\s+(run\s+watch|pr\s+checks\b[^|;&]*--watch)")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?:\n|$)", re.S)
# A short run-wait window in the foreground: subagents copied `--timeout 140` from their
# briefs, so the 590 s rule never reached them (usage-review E019, 2026-11-17).
SHORT_RUN_WAIT = re.compile(r"run-wait\b[^|;&\n]*?--timeout\s+(\d+)")
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", re.S)


def code_only(cmd: str) -> str:
    """Drop heredoc bodies and quoted strings: they hold data and prose, not the loop."""
    return QUOTED.sub("''", HEREDOC.sub("\n", cmd))


def reason(cmd: str) -> str | None:
    cmd = code_only(cmd)
    if LOOP.search(cmd):
        return "an until/while loop with sleep"
    if WATCH.search(cmd):
        return "a gh --watch"
    short = [int(n) for n in SHORT_RUN_WAIT.findall(cmd) if int(n) < 500]
    if short:
        return f"a run-wait window of {min(short)} s"
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
