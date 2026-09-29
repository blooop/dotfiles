#!/bin/sh
# Append one line per Claude Code lifecycle event to a daily JSONL log, for the
# usage-review skill's timing metrics (response latency, session wall time,
# host vs container). The transcripts already hold every tool call; what they
# lack is where the session ran and how long the human took, and that is all
# this adds.
#
# Registered for SessionStart, UserPromptSubmit, Notification, Stop and
# SessionEnd -- never PreToolUse, which fires too often to be worth a fork.
#
# POSIX sh with no jq and no python3, because a devcontainer has neither for
# sure. That is also why the hook's stdin is embedded raw rather than parsed:
# it is one JSON object, and JSON only allows a raw newline between tokens, so
# deleting newlines keeps it valid on one line.
#
# Devcontainers with the claude-code feature bind-mount the host's ~/.claude,
# so their lines land in the host's log. A container without that mount writes
# a log nobody reads, which costs nothing.
#
# It must never block or fail a session: every error is swallowed, it prints
# nothing on stdout (SessionStart and UserPromptSubmit stdout goes into the
# model's context), and it always exits 0.

dir="${CLAUDE_TELEMETRY_DIR:-$HOME/.claude/telemetry}"

# Env values are ids and hostnames, but escape the two characters that could
# break the line anyway.
esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

{
    mkdir -p "$dir" || exit 0
    ev=$(cat | tr -d '\n\r')
    [ -n "$ev" ] || ev=null
    container=false
    [ -f /.dockerenv ] || [ -n "${REMOTE_CONTAINERS:-}${DEVPOD:-}" ] && container=true
    printf '{"ts":"%s","host":"%s","container":%s,"pane":"%s","tab":"%s","dl_ws":"%s","ev":%s}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" \
        "$(esc "$(hostname 2>/dev/null || cat /etc/hostname)")" \
        "$container" \
        "$(esc "${HERDR_PANE_ID:-}")" \
        "$(esc "${HERDR_TAB_ID:-}")" \
        "$(esc "${DEVLAUNCH_WORKSPACE_ID:-}")" \
        "$ev" >>"$dir/claude-$(date -u +%F).jsonl"
} >/dev/null 2>&1
exit 0
