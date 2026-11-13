#!/usr/bin/env bash
# SessionStart: say at once when a login this host's agents depend on is dead.
#
# A retro of the two weeks to 2026-11-12 found 8 "try now" prompts behind three causes:
# the gcloud application-default token had expired (the bazel-lockfile-check prek hook
# then fails every commit; one session lost 52 minutes), the GNOME login keyring was
# locked after a reboot (every gh call hangs with no output), or the gh token was gone.
# Each time an agent worked until it hit the wall, stopped, and waited for the human.
#
# Silent when both logins work. The warning goes to the human as a systemMessage, as
# resource-check.sh does. It never blocks: every probe has a timeout and any error
# means silence. Only the host has these logins; a devcontainer has no `dl` and exits.
command -v dl >/dev/null 2>&1 || exit 0

warn=()
if command -v gcloud >/dev/null 2>&1; then
    timeout 4 gcloud auth application-default print-access-token >/dev/null 2>&1 \
        || warn+=("gcloud application-default login is expired (run: gcloud auth application-default login, then gcloud-sync)")
fi
if command -v gh >/dev/null 2>&1; then
    timeout 3 gh auth token >/dev/null 2>&1
    case $? in
        0) ;;
        124) warn+=("gh hangs, so the login keyring is locked (unlock it; see the gh-hangs-locked-keyring memory)") ;;
        *) warn+=("gh has no token (run: gh auth login)") ;;
    esac
fi
[ ${#warn[@]} -eq 0 ] && exit 0

msg="Login problem: $(IFS=';'; echo "${warn[*]}" | sed 's/;/; /g'). Agents on this host stop on this until you fix it."
printf '{"systemMessage": "%s"}\n' "$msg"
