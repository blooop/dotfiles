#!/usr/bin/env bash
# Stop + UserPromptSubmit: warn when the session context passes ~200k tokens,
# so the agent writes a handoff (CLAUDE.md, "Hand off at ~200k") instead of
# carrying a huge context into every later call. A retro (2026-10-05) found
# sessions running far past 200k with nobody noticing: every tool call re-reads
# the whole context, so the cost grows with each turn.
#
# Context size = the last main-thread assistant message's usage:
# input_tokens + cache_read_input_tokens + cache_creation_input_tokens, read
# from the transcript_path in the hook input. Subagent transcripts live in
# their own files, and isSidechain lines are skipped, so only the parent counts.
# Synthetic messages (model "<synthetic>", e.g. an API error) carry zero
# usage and are skipped too.
#
# Two events, two readers:
#   - UserPromptSubmit: stdout goes into the model's context, so the AGENT
#     reads it at the start of its next turn.
#   - Stop: a systemMessage, which only the HUMAN sees.
# It warns only. It always exits 0 and never returns a block decision. To keep
# the noise down it speaks once per 50k band per session and event (200k,
# 250k, ...), tracked in a small state file.
#
# Threshold: CLAUDE_CONTEXT_WARN_TOKENS (default 200000).

limit=${CLAUDE_CONTEXT_WARN_TOKENS:-200000}
band=50000

command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
read -r event transcript session < <(printf '%s' "$input" |
    jq -r '[.hook_event_name // "", .transcript_path // "", .session_id // "x"] | @tsv' 2>/dev/null) || exit 0
[ -r "$transcript" ] || exit 0

tokens=$(tac "$transcript" 2>/dev/null |
    grep '"type":"assistant"' |
    jq -r 'select(.isSidechain != true and .message.model != "<synthetic>" and .message.usage != null)
           | .message.usage
           | (.input_tokens // 0) + (.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0)' 2>/dev/null |
    head -n1)
case "$tokens" in ''|*[!0-9]*) exit 0 ;; esac
[ "$tokens" -ge "$limit" ] || exit 0

level=$(( (tokens - limit) / band ))
state_dir="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/claude-context-check"
state="$state_dir/$session.$event"
mkdir -p "$state_dir" 2>/dev/null
last=$(cat "$state" 2>/dev/null || echo -1)
[ "$level" -gt "$last" ] 2>/dev/null || exit 0
echo "$level" >"$state" 2>/dev/null

k=$(( tokens / 1000 )) lk=$(( limit / 1000 ))
case "$event" in
    UserPromptSubmit)
        echo "Context check: this session's context is about ${k}k tokens, past the ~${lk}k handoff point. Unless the end is near, write a handoff per CLAUDE.md (Handoffs between agents) and tell the user its path." ;;
    *)
        jq -cn --arg m "Context is ~${k}k tokens (past ${lk}k). Ask Claude to write a handoff and start a fresh session." '{systemMessage: $m}' ;;
esac
exit 0
