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

ADVICE_MAIN = (
    "wait-advice: this command waited in the foreground ({why}). Each poll re-reads the "
    "whole context. Run the wait with run_in_background and end the turn; its exit wakes "
    "you. Use `~/.claude/scripts/run-wait --timeout SECS [--pid PID] -- CHECK` for a "
    "timeout and a dead-process check, and for CI "
    "`gh pr checks <n> --watch --fail-fast --interval 60`, which stops at the first failed "
    "check."
)
# The harness moves a subagent's foreground Bash call to the background after 180 s
# (seen since 2026-11-10; CLAUDE_CODE_AUTO_BACKGROUND_TIMEOUT_MS covers only the main
# agent). The old 590 s advice made 1372 of 2584 long run-wait calls move (usage-review
# E022, 2026-11-21), so a subagent waits in 170 s windows.
ADVICE_SUB = (
    "wait-advice: this command waited in the foreground ({why}). You are a subagent: the "
    "harness moves any Bash call over 180 s to the background. Wait with "
    "`~/.claude/scripts/run-wait --timeout 170 --every 30 [--pid PID] -- CHECK` and the "
    "Bash timeout at 175000, and repeat it only when it exits 124. No sleep or until loops."
)
SUB_WINDOW_MAX = 175

LONG_SLEEP = re.compile(r"\bsleep\s+(\d+)")
# A real shell loop: `until|while <cond>; do ... sleep ...`. Prose such as "no until/sleep
# loops" in a heredoc matched the old pattern (2026-11-16: a script write got the advice).
LOOP = re.compile(r"\b(until|while)\b[^\n]*?[;\n]\s*do\b.*\bsleep\b", re.S)
WATCH = re.compile(r"\bgh\s+(run\s+watch|pr\s+checks\b[^|;&]*--watch)")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?:\n|$)", re.S)
# A subagent run-wait window longer than the harness's 180 s cap (usage-review E022).
RUN_WAIT = re.compile(r"run-wait\b[^|;&\n]*?--timeout\s+(\d+)")
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", re.S)


def code_only(cmd: str) -> str:
    """Drop heredoc bodies and quoted strings: they hold data and prose, not the loop."""
    return QUOTED.sub("''", HEREDOC.sub("\n", cmd))


def reason(cmd: str, sub: bool) -> str | None:
    cmd = code_only(cmd)
    if LOOP.search(cmd):
        return "an until/while loop with sleep"
    if WATCH.search(cmd):
        return "a gh --watch"
    long = [int(n) for n in RUN_WAIT.findall(cmd) if int(n) > SUB_WINDOW_MAX]
    if sub and long:
        return f"a run-wait window of {max(long)} s"
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
        sub = bool(data.get("agent_id"))
        why = reason(tool_input.get("command") or "", sub)
        if why is None:
            return
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (ADVICE_SUB if sub else ADVICE_MAIN).format(why=why),
        }}))
    except Exception:  # noqa: BLE001 — advice only; never fail the tool call
        return


main()
