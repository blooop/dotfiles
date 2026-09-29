#!/bin/sh
# Detach logger.py from the [[startup]] hook, which should not wait on a
# process that runs for the life of the server. A logger that is already
# running holds the lock, and the new one exits at once.
here=$(dirname "$0")
command -v python3 >/dev/null 2>&1 || exit 0
setsid python3 "$here/logger.py" </dev/null >/dev/null 2>&1 &
exit 0
