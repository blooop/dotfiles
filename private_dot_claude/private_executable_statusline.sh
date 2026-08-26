#!/usr/bin/env bash
# Find claude-statusline wherever it actually is, then hand it the session JSON.
#
# settings.json names this file as statusLine.command, and that command string has
# to work in two places at once. ~/.claude is not applied inside a container --
# claudecfg is false for both container profiles -- so the container does not get
# its own settings.json; it inherits the host's through the ~/.claude bind mount.
# One string, two very different PATHs, and the host cannot know the container's.
#
# Naming `claude-statusline` bare did not survive that. A kinisi dev container
# keeps /home/kinisi container-local, so recreating it wipes .bash_env and the
# .bashrc hook; PIXI_HOME is never redirected to the private per-arch root, and
# the binary drops off PATH. The binary itself is still there -- ~/.local/share
# IS bind-mounted, so the pixi root outlives the container -- which is why the
# repair was always just re-running the bootstrap, never a reinstall. Claude Code fails a
# missing statusLine command silently, so all of that surfaced as a blank bar
# with no error, and got rediagnosed from scratch three times.
#
# So the resolution moves here, where it can be written down. This file lives in
# ~/.claude deliberately: it is the one tree guaranteed to be visible everywhere
# settings.json is, because it arrives by the same mount that carries it.

set -uo pipefail

# PATH first, always: a bootstrapped shell has already chosen which pixi root
# wins (see _path_promote in .bash_env), and re-deciding it here would silently
# override that. It is also the only branch that costs nothing, so it returns
# before the roots below fork `uname`.
if resolved=$(command -v claude-statusline 2>/dev/null) && [ -n "$resolved" ]; then
    exec "$resolved"
fi

# Then each pixi root in turn, by env prefix rather than by exposed name.
#
# `envs/<name>/bin/<name>`, NOT `bin/<name>`: the latter is a pixi trampoline,
# and a trampoline resolves itself through an absolute prefix baked in when it
# was written. The per-arch root is written from inside a container, so its
# trampolines name a path under the *container's* HOME -- and every one of them
# fails the moment the same bind-mounted tree is read from the host, which is
# exactly when this fallback is reached. It failed silently, too: the error goes
# to stderr and Claude Code renders stdout, so the bar came back blank, which is
# the failure this file exists to remove. The env binary carries no such prefix
# and runs from either side of the mount.
#
# bootstrap.sh already reached this conclusion for chezmoi, for the same reason.
for root in "${PIXI_HOME:-}" "$HOME/.pixi" "$HOME/.local/share/pixi-container-$(uname -m)"; do
    [ -n "$root" ] || continue
    candidate="$root/envs/claude-statusline/bin/claude-statusline"
    # -f as well as -x: a directory is executable, and exec'ing one would abort
    # the loop and take the hint below with it.
    [ -f "$candidate" ] && [ -x "$candidate" ] || continue
    # exec, so the session JSON on our stdin becomes its stdin untouched.
    exec "$candidate"
done

# Genuinely nowhere. Print something rather than nothing: a blank status line is
# indistinguishable from a working one with nothing to say, which is precisely
# what made this expensive. One short token -- this is a prompt, not a log.
printf 'statusline: not installed\n'
