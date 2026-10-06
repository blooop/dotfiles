#!/bin/bash
# Turns on the user systemd-tmpfiles clean timer, which ages out Claude Code's
# on-disk scratch (~/.config/user-tmpfiles.d/claude-tmp.conf). Ubuntu ships the
# timer with preset "enabled" but leaves it disabled, so nothing reads that file
# until something enables it.
#
# A no-op where there is no user systemd (containers): those share the host's
# ~/.cache, and the host's timer cleans it.

set -euo pipefail

if ! systemctl --user show-environment >/dev/null 2>&1; then
    exit 0
fi

if [ "$(systemctl --user is-enabled systemd-tmpfiles-clean.timer 2>/dev/null || true)" != "enabled" ]; then
    echo "Enabling systemd-tmpfiles-clean.timer (ages out Claude scratch after 7 days)."
    systemctl --user enable --now systemd-tmpfiles-clean.timer || true
fi
