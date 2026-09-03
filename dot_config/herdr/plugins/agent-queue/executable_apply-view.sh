#!/usr/bin/env bash
# Make F7 walk a queue of things that need you, rather than a list of everything.
#
# `keys.next_agent` is documented as "focus the next agent shown in the agent
# panel". It is *positional* -- one row from wherever you already are -- not
# priority-seeking. `ui.agent_panel_sort = "priority"` fixes the panel's ORDER,
# so row 1 is the most blocked, but F7 from row 5 still goes to row 6. That gap
# between "the queue is sorted" and "the key walks the queue" is the whole
# reason this plugin exists.
#
# It is made worse by `done` being defined as "idle and not yet seen": focusing
# the ticked agent marks it seen, it collapses to `idle`, and the panel re-sorts
# underneath you, so the *next* F7 lands somewhere unrelated.
#
# `agent.view.set` is the lever, because it "controls the expanded and collapsed
# sidebar, mobile Agents list, mouse targets, indexed focus, and next/previous
# Agent navigation" -- navigation included. Filter the panel to blocked+done and
# F7 cannot physically land on something that does not need you.
#
# There is no CLI for it, only the socket, which is why this is raw JSON rather
# than a `herdr` invocation like the rest of the plugin API.
#
# The cost, stated plainly: `working` agents leave the Agents panel while they
# work, and reappear the moment they finish or block. What is still running is
# read off the Spaces panel rollup, or `herdr agent list`, which this does not
# touch. To keep them visible instead, swap the filter for the hybrid in
# ALT_FILTER below -- the docs' own worked example -- at the cost of F7 walking
# your current workspace's idle agents again.

set -euo pipefail

sock="${HERDR_SOCKET_PATH:-${XDG_CONFIG_HOME:-$HOME/.config}/herdr/herdr.sock}"

[ -S "$sock" ] || {
    echo "agent-queue: no herdr socket at $sock" >&2
    exit 0
}

read -r -d '' request <<'JSON' || true
{"id":"agent-queue-startup","method":"agent.view.set","params":{
  "source":"local.agent-queue",
  "label":"needs me",
  "filter":{"op":"in","field":"status","values":["blocked","done"]},
  "sort":[{"field":"attention","order":"desc"},
          {"field":"state_change_seq","order":"desc"}]}}
JSON

# ALT_FILTER -- everything in the workspace you are looking at, plus anything
# needing attention anywhere else:
#   {"op":"any","filters":[
#     {"op":"eq","field":"workspace_id","value":{"context":"current_workspace_id"}},
#     {"op":"in","field":"status","values":["blocked","done"]}]}

send() {
    if command -v socat >/dev/null 2>&1; then
        printf '%s\n' "$1" | socat -T5 - "UNIX-CONNECT:$sock"
    else
        printf '%s\n' "$1" | python3 -c '
import os, socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(5)
s.connect(os.environ["SOCK"])
s.sendall(sys.stdin.buffer.read())
s.shutdown(socket.SHUT_WR)
sys.stdout.write(s.recv(65536).decode())
'
    fi
}

# One line of JSON: the heredoc above is indented for reading, and the socket
# frames requests by newline, so an embedded newline would be a second request.
response=$(SOCK="$sock" send "$(printf '%s' "$request" | tr -d '\n')")

# A `set` that did not take is worth one line on stderr and nothing more -- a
# startup hook that fails does not stop the server, and a full agent panel is a
# degraded queue, not a broken session.
case "$response" in
    *'"active":true'*) echo "agent-queue: F7 now walks blocked+done only" ;;
    *) echo "agent-queue: agent.view.set did not take: $response" >&2 ;;
esac
