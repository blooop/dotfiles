#!/bin/bash
# Retires prwatch.timer on machines that already enabled it.
#
# prwatch used to be a systemd user timer plus a config file. It is now a
# foreground loop you run in a terminal window (`prwatch OWNER/NAME`), so the
# unit files and their enabler are gone from this repo and .chezmoiremove
# deletes the units. Neither of those disables anything: `enable` wrote a
# symlink into ~/.config/systemd/user/timers.target.wants/, and removing the
# unit file out from under it leaves that symlink dangling, which systemd
# reports at every login -- the same orphan run_onchange_disable-herdr-server.sh
# clears for the herdr unit.
#
# Not gated on .toolbox, for the same reason as that script: the machines that
# need the teardown are the ones that ever ran the enabler, not the ones where
# the flag is true today. The guards make it a no-op everywhere else.
#
# Unlike the herdr one this does `disable --now`: the service is a oneshot
# poll with nothing attached to it, so stopping the timer takes nothing down.

set -euo pipefail

if ! systemctl --user show-environment >/dev/null 2>&1; then
    exit 0
fi

wants="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/timers.target.wants/prwatch.timer"
if [ -L "$wants" ]; then
    echo "Clearing the dangling prwatch.timer enable symlink."
    rm -f "$wants"
    systemctl --user daemon-reload || true
fi

if [ "$(systemctl --user is-enabled prwatch.timer 2>/dev/null || true)" = "enabled" ]; then
    echo "Retiring prwatch.timer (prwatch is now a foreground loop: prwatch OWNER/NAME)."
    systemctl --user disable --now prwatch.timer || true
    systemctl --user daemon-reload || true
fi

# .chezmoiremove runs before this script, so on the apply that retires the units
# the files are already gone by the time it reaches here: is-enabled says
# not-found, and the timer systemd still holds in memory sits there as `failed`.
# Stop it and clear the failed state so `list-units` does not show a ghost.
if systemctl --user list-units --all --plain --no-legend 'prwatch.*' 2>/dev/null | grep -q .; then
    systemctl --user stop prwatch.timer prwatch.service 2>/dev/null || true
    systemctl --user reset-failed prwatch.timer prwatch.service 2>/dev/null || true
    systemctl --user daemon-reload || true
fi
