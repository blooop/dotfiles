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
# repair was always just `kbash` and never a reinstall. Claude Code fails a
# missing statusLine command silently, so all of that surfaced as a blank bar
# with no error, and got rediagnosed from scratch three times.
#
# So the resolution moves here, where it can be written down. This file lives in
# ~/.claude deliberately: it is the one tree guaranteed to be visible everywhere
# settings.json is, because it arrives by the same mount that carries it.

set -uo pipefail

# Ordered by how much the answer can be trusted, not by how likely it is.
#
# PATH first, always: a bootstrapped shell has already chosen which pixi root
# wins (see _path_promote in .bash_env), and re-deciding it here would silently
# override that. PIXI_HOME next, for a shell that exported it but whose PATH some
# later block reshuffled.
#
# The per-arch container root goes last because its trampolines embed an absolute
# prefix under the *container's* HOME, so on a host they point at a path that
# does not exist. Reaching it there means PATH and ~/.pixi both already missed --
# i.e. the status line was not installed at all -- and a binary that fails loudly
# beats the blank bar this whole file exists to end.
for candidate in \
    "$(command -v claude-statusline 2>/dev/null || true)" \
    "${PIXI_HOME:+$PIXI_HOME/bin/claude-statusline}" \
    "$HOME/.pixi/bin/claude-statusline" \
    "$HOME/.local/share/pixi-container-$(uname -m)/bin/claude-statusline"; do
    [ -n "$candidate" ] && [ -x "$candidate" ] || continue
    # exec, so the session JSON on our stdin becomes its stdin untouched.
    exec "$candidate"
done

# Genuinely nowhere. Print something rather than nothing: a blank status line is
# indistinguishable from a working one with nothing to say, which is precisely
# what made this expensive. One short token -- this is a prompt, not a log.
printf 'statusline: run kbash\n'
