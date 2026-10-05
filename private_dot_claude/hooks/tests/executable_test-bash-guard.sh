#!/usr/bin/env bash
# Table test for bash-guard.sh: each row is an expected verdict and a command.
# Run: hooks/tests/test-bash-guard.sh [path/to/bash-guard.sh]
# It runs the hook as on the host (the container env vars are cleared); the
# last rows check that the pkill rule is off in a container and the git rule
# is not.
#
# Decisions the table records:
#   - `echo pkill` is ALLOWED: pkill is an argument there, not a command.
#     A commit message that merely mentions pkill must not be blocked.
#   - "pkill ..." at the start of a quoted string is BLOCKED: the hook cannot
#     tell `bash -c 'pkill x'` from `git commit -m 'pkill is bad'` cheaply,
#     and when unsure it blocks.
#   - pkill passed to `docker exec` / `docker run` / `dl exec` is ALLOWED,
#     also through `sh -c`, but not once a separator ends the docker command.
#   - A markdown-quoted `git checkout -B` in a message is ALLOWED: the git
#     rule does not treat a backtick as a command start. Unquoted in prose,
#     it is BLOCKED.
#   - pkill behind a wrapper (sudo, xargs, timeout, ...) is BLOCKED even when
#     the wrapper then runs docker; a wrapper hides intent.

hook=${1:-"$(dirname "$0")/../bash-guard.sh"}
[ -x "$hook" ] || hook="$(dirname "$0")/../executable_bash-guard.sh"

# The exact command from the 2026-10-02 incident (agent-ac4b7a9a638296460).
incident=$(cat <<'CMD'
cd /tmp && c=$(docker run -d --rm ubuntu:24.04 sleep 300) && sleep 1 && \
( sleep 1000 | docker exec -i $c bash -c 'ps -o pid,pgid,sid,cmd -p $$ > /tmp/ps; cat > /dev/null; echo EOF > /tmp/x' ) & sleep 2; pkill -KILL -f "docker exec -i $c"; sleep 1; docker exec $c bash -c 'cat /tmp/ps; cat /tmp/x 2>&1; ps -ef'; pkill -f "sleep 1000"; docker kill $c >/dev/null
CMD
)

cases=(
  "block|$incident"
  'block|pkill -f "docker exec -i $c"'
  'block|pkill node'
  'block|killall python3'
  'block|/usr/bin/pkill -f foo'
  'block|sleep 1; pkill -f foo'
  'block|true && pkill -f foo'
  'block|ps aux | grep foo | xargs pkill'
  'block|pgrep foo | xargs -r pkill'
  'block|sudo pkill foo'
  'block|sudo -n killall foo'
  'block|timeout 5 pkill foo'
  'block|env FOO=1 pkill foo'
  'block|echo $(pkill foo)'
  'block|echo "$(pkill foo)"'
  'block|echo `killall foo`'
  "block|bash -c 'pkill foo'"
  'block|sh -lc "sleep 1; pkill foo"'
  'block|eval "pkill foo"'
  'block|( pkill foo )'
  "block|$(printf 'echo hi\npkill foo')"
  'block|docker exec c true; pkill foo'
  "block|git commit -m 'pkill is bad'"
  'block|pkill -f "unbalanced'
  'allow|kill 1234'
  'allow|kill -TERM 1234'
  'allow|kill -9 $pid'
  'allow|docker exec c pkill x'
  'allow|docker exec -i c pkill -f x'
  "allow|docker exec c sh -c 'pkill x'"
  'allow|docker run --rm ubuntu:24.04 pkill x'
  'allow|dl exec ws pkill x'
  'allow|echo pkill'
  'allow|grep -rn killall docs/'
  'allow|git commit -m "Block pkill on the host"'
  'allow|pgrep -f foo'
  'allow|ls -la'
  'block|git checkout -B x'
  'block|git checkout -B x origin/main'
  'block|git checkout --force -B x'
  'block|git checkout -fB x'
  'block|git -C /tmp/repo checkout -B x'
  'block|git switch -C x'
  'block|git switch --force-create x'
  'block|git branch -f x HEAD'
  'block|git branch --force x HEAD'
  'block|cd repo && git checkout -B x'
  'allow|git checkout -b new'
  'allow|git switch -c new'
  'allow|git checkout main'
  'allow|git branch -d old'
  'allow|git branch --list'
  'allow|git worktree list'
  'allow|git commit -m "Container git let `git checkout -B` move a branch"'
)

pass=0 fail=0
run() { # expected, command, extra env...
    local want=$1 cmd=$2; shift 2
    local json got
    json=$(jq -n --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')
    env -u REMOTE_CONTAINERS -u DEVPOD "$@" "$hook" <<<"$json" >/dev/null 2>&1
    case $? in 0) got=allow ;; 2) got=block ;; *) got="exit$?" ;; esac
    if [ "$got" = "$want" ]; then
        pass=$((pass + 1))
    else
        fail=$((fail + 1)); printf 'FAIL want=%s got=%s: %s\n' "$want" "$got" "$cmd"
    fi
}

if [ -f /.dockerenv ]; then
    echo "note: running inside a container; the host-only pkill rows will be skipped"
fi
for row in "${cases[@]}"; do
    want=${row%%|*} cmd=${row#*|}
    if [ -f /.dockerenv ] && printf '%s' "$cmd" | grep -Eq 'pkill|killall'; then continue; fi
    run "$want" "$cmd"
done
# In a container the pkill rule is off and the git rule still holds.
run allow 'pkill foo' DEVPOD=1
run block 'git checkout -B x' DEVPOD=1

# Bad input never blocks.
for bad in '' 'not json' '{"tool_input":{}}'; do
    printf '%s' "$bad" | "$hook" >/dev/null 2>&1
    rc=$?
    if [ $rc -eq 0 ]; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL bad input '$bad' exit $rc"; fi
done

echo "bash-guard: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
