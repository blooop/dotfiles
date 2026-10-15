#!/bin/sh
# PermissionRequest: answer "allow" to every permission prompt, and log it.
#
# Bypass mode still stops for a human on Claude Code's built-in safety checks,
# such as "This shell -c script runs rm and could not be checked". An agent
# left running overnight then waits until morning. Since 2026-10-12, at the
# user's request, no check may stop the session: bash-guard.sh
# is unhooked (its blocks got in the way), and this hook answers the
# prompts that are left. It cannot answer an AskUserQuestion: "allow" only
# shows the question, which still waits for a human.
#
# Each answer is one JSON line in ~/.cache/claude-tmp/permission-autoallow.jsonl,
# so you can read in the morning what it let through. POSIX sh, no jq: the
# hook input is one JSON object, embedded raw on one line (as telemetry.sh
# does). A failure to log never stops the answer.

input=$(cat | tr -d '\n')
log=${CLAUDE_CODE_TMPDIR:-$HOME/.cache/claude-tmp}/permission-autoallow.jsonl
{ mkdir -p "$(dirname "$log")" &&
  printf '{"time":"%s","host":"%s","input":%s}\n' \
      "$(date -Iseconds)" "$(hostname)" "${input:-null}" >> "$log"; } 2>/dev/null

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}'
exit 0
