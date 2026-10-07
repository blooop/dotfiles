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
#   - A quoted message value is data and is ALLOWED: `git commit/tag -m/-F`,
#     `gh pr|issue create|edit|comment --body/--title`, `gh release
#     create|edit --notes/--title`. A $(...) or `...` inside a double-quoted
#     value still runs, so it is checked. Elsewhere, "pkill ..." at the start
#     of a quoted argument is BLOCKED: it may be a script a runner executes.
#   - A heredoc body is data and is ALLOWED, unless the heredoc feeds a shell
#     (`bash <<EOF`, `ssh host <<EOF`, `cat <<EOF | sh`): then it is BLOCKED.
#     A body fed to `docker exec ... bash` runs in the container: the pkill
#     rule allows it, the git rule still checks it. An unquoted-delimiter
#     body still expands $(...), so that is checked.
#   - pkill passed to `docker exec` / `docker run` / `dl exec` is ALLOWED,
#     also through `sh -c`, but not once a separator ends the docker command.
#   - A markdown-quoted `git checkout -B` is ALLOWED: the git rule does not
#     treat a backtick as a command start. Outside a message value or a
#     heredoc body, an unquoted mention is BLOCKED.
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
  'block|pkill -f "unbalanced'
  "allow|git commit -m 'pkill is bad'"
  'block|git commit -m "$(pkill x)"'
  'block|git commit -m "note `killall x`"'
  'block|git commit -m "x" && pkill y'
  'allow|git commit -am "never pkill on the host"'
  'allow|git commit --message="never pkill on the host"'
  'allow|git tag -a v1 -m "pkill note"'
  'allow|gh issue create --body "never pkill on the host"'
  'allow|gh pr create --title "Block pkill" --body "never killall either"'
  'allow|gh pr comment 12 -b "pkill -f x killed 9 sessions"'
  'allow|gh release create v1 --notes "pkill guard"'
  "block|foo -m 'pkill x'"
  "allow|$(printf "cat <<'EOF' > f\npkill -f x\nEOF")"
  "allow|$(printf "cat <<-EOF > f\n\tpkill -f x\n\tEOF")"
  "allow|$(printf "gh issue create --title t --body-file - <<'EOF'\nnever run pkill on the host.\nDon't.\nEOF")"
  "allow|$(printf "git commit -F - <<'EOF'\npkill (and killall) are bad\nEOF")"
  "allow|$(printf "git commit -m \"\$(cat <<'EOF'\nnever pkill; it's bad\nEOF\n)\"")"
  "block|$(printf "cat <<EOF > f\n\$(pkill x)\nEOF")"
  "block|$(printf "bash <<'EOF'\npkill -f x\nEOF")"
  "block|$(printf "bash -s <<'EOF'\npkill -f x\nEOF")"
  "block|$(printf "ssh host <<'EOF'\npkill -f x\nEOF")"
  "block|$(printf "cat <<'EOF' | sh\npkill -f x\nEOF")"
  "block|$(printf "sudo bash <<'EOF'\npkill -f x\nEOF")"
  "allow|$(printf "docker exec -i c bash <<'EOF'\npkill -f x\nEOF")"
  "block|$(printf "cat <<'EOF' > f\nhi\nEOF\npkill -f x")"
  'allow|git commit -F msg.txt'
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
  "allow|git commit -m 'never git checkout -B a held branch'"
  'block|git commit -m "$(git checkout -B x)"'
  'allow|gh pr create --body "do not git branch -f main"'
  "allow|$(printf "cat <<'EOF' > notes\ngit checkout -B x\nEOF")"
  "block|$(printf "bash <<'EOF'\ngit checkout -B x\nEOF")"
  "block|$(printf "docker exec -i c bash <<'EOF'\ngit checkout -B x\nEOF")"
  'block|git commit -m "x"; git checkout -B y'
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
