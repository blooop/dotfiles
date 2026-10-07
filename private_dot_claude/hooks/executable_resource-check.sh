#!/usr/bin/env bash
# SessionStart: warn before a new session piles onto a host that is already short
# of memory. A week of usage review (2026-09-29) found 15 prompts about CPU, RAM
# or a crashed machine, and every crash lost timers and in-flight work -- the
# cause was many devlaunch workspaces and their Bazel servers at once (see the
# ags-beast memory guard). Catching it at session start costs one line.
#
# The trigger is low RAM or too many Bazel servers; the workspace count rides
# along as the likely cause, since a count alone fires on a healthy host.
# Silent unless a threshold trips, so a healthy host adds nothing to the screen.
# The warning goes to the human as a systemMessage, not into the model's context.
# It names ags-who for idle agents and tmpfs inside containers or in
# /tmp/claude-<uid> (a retro on 2026-10-05), and `ags-who --workspaces` for the
# workspaces that can go: `dl --ls` shows no PR or merge state at all.
# Only the host runs `dl`; inside a devcontainer there is none and this exits.
command -v dl >/dev/null 2>&1 || exit 0

MIN_AVAIL_GB=${CLAUDE_MIN_AVAIL_GB:-12}
MAX_BAZEL=${CLAUDE_MAX_BAZEL:-6}

avail_gb=$(awk '/^MemAvailable:/ {printf "%d", $2/1048576}' /proc/meminfo)
workspaces=$(timeout 3 dl --ls 2>/dev/null | awk 'NR>2 && NF' | wc -l)
bazel=$(pgrep -fc 'bazel.*A-server|java.*bazel' 2>/dev/null); bazel=${bazel:-0}

warn=()
[ "${avail_gb:-99}" -lt "$MIN_AVAIL_GB" ] && warn+=("${avail_gb}G RAM available")
[ "$bazel" -gt "$MAX_BAZEL" ] && warn+=("$bazel Bazel servers")
[ ${#warn[@]} -eq 0 ] && exit 0

warn+=("$workspaces dl workspaces")
msg="Host is busy: $(IFS=,; echo "${warn[*]}" | sed 's/,/, /g'). Run ags-who to see which sessions are idle and what holds the RAM (tmpfs included); run ags-who --workspaces to find the workspaces you can remove (PR merged or closed, nothing to lose) before starting heavy builds."
printf '{"systemMessage": "%s"}\n' "$msg"
