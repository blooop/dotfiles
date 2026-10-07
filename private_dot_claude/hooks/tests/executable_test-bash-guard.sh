#!/usr/bin/env bash
# Table test for bash-guard.sh: each row is an expected verdict and a command.
# Run: hooks/tests/test-bash-guard.sh [path/to/bash-guard.sh]
# It runs the hook as on the host (the container env vars are cleared); the
# ct_cases rows run it with DEVPOD=1, as in a container: there the host pkill
# rule is off, and the -f / killall rule and the git rule still hold.
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
#   - `pkill -f` / `pkill --full` / `killall` is BLOCKED everywhere: the
#     harness runs the call as `bash -c '<command>'`, and the pattern matches
#     that shell (the call dies with exit 144). This holds in a container,
#     for a pkill passed to `docker exec` / `dl exec`, and for a heredoc body
#     fed to one. Signal names (`-KILL`, `-HUP`) are not -f.
#   - plain pkill passed to `docker exec` / `docker run` / `dl exec` is
#     ALLOWED, also through `sh -c`, but not once a separator ends the docker
#     command.
#   - A markdown-quoted `git checkout -B` is ALLOWED: the git rule does not
#     treat a backtick as a command start. Outside a message value or a
#     heredoc body, an unquoted mention is BLOCKED.
#   - pkill behind a wrapper (sudo, xargs, timeout, ...) is BLOCKED even when
#     the wrapper then runs docker; a wrapper hides intent.
#   - A path under /tmp/claude- gets a WARNING (exit 0 plus additionalContext),
#     never a block. A message value or a data heredoc body that names it does
#     not; ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-... does not either. A body fed
#     to a container does, since /tmp is a tmpfs there too. A block wins over
#     the warning.

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
  "block|$(printf "docker exec -i c bash <<'EOF'\npkill -f x\nEOF")"
  "allow|$(printf "docker exec -i c bash <<'EOF'\npkill x\nEOF")"
  "block|$(printf "cat <<'EOF' > f\nhi\nEOF\npkill -f x")"
  'allow|git commit -F msg.txt'
  'allow|kill 1234'
  'allow|kill -TERM 1234'
  'allow|kill -9 $pid'
  'allow|docker exec c pkill x'
  'block|docker exec -i c pkill -f x'
  'block|docker exec c pkill --full x'
  'block|docker exec c killall x'
  "block|docker exec c sh -c 'pkill -f x'"
  'block|dl exec ws pkill -KILL -f x'
  'allow|docker exec -i c pkill -KILL x'
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
  'warn|ls /tmp/claude-1000'
  'warn|git clone https://x/y /tmp/claude-$(id -u)/y'
  'warn|cd "/tmp/claude-1000/sess/scratchpad" && make'
  'warn|du -sh /tmp/claude-*'
  "warn|$(printf "bash <<'EOF'\ncp f /tmp/claude-1000/f\nEOF")"
  "warn|$(printf "docker exec -i c bash <<'EOF'\nls /tmp/claude-1000\nEOF")"
  'warn|echo "$(ls /tmp/claude-1000)"'
  'block|git checkout -B x && ls /tmp/claude-1000'
  'allow|ls "${CLAUDE_CODE_TMPDIR:-/tmp}/claude-$(id -u)"'
  'allow|ls ~/.cache/claude-tmp/claude-1000'
  'allow|ls /tmp/other'
  'allow|git commit -m "Move clones out of /tmp/claude-<uid>"'
  'allow|gh pr create --title t --body "it filled /tmp/claude-1000"'
  "allow|$(printf "cat <<'EOF' > notes.md\nNever use /tmp/claude-1000.\nEOF")"
)

pass=0 fail=0
run() { # expected, command, extra env...
    local want=$1 cmd=$2; shift 2
    local json got
    json=$(jq -n --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')
    local out rc
    out=$(env -u REMOTE_CONTAINERS -u DEVPOD "$@" "$hook" <<<"$json" 2>/dev/null)
    rc=$?
    case $rc in 0) got=allow ;; 2) got=block ;; *) got="exit$rc" ;; esac
    if [ "$got" = allow ] && [ -n "$out" ]; then
        # A warning: exit 0 and valid PreToolUse JSON with additionalContext.
        if printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext | length > 0' >/dev/null 2>&1; then
            got=warn
        else
            got="badjson"
        fi
    fi
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
# In a container the host pkill rule is off; the -f / killall rule and the
# git rule still hold.
ct_cases=(
  'allow|pkill foo'
  'allow|pkill -KILL foo'
  'allow|pkill -HUP -x foo'
  'allow|sudo pkill foo'
  "allow|bash -c 'pkill foo'"
  'allow|echo pkill -f foo'
  "allow|git commit -m 'never pkill -f x or killall'"
  'allow|gh pr create --body "pkill -f killed the shell"'
  "allow|$(printf "cat <<'EOF' > notes\npkill -f x\nEOF")"
  'allow|pgrep -f foo | grep -vx $$'
  'allow|kill $pid'
  'block|pkill -f foo'
  'block|pkill --full foo'
  'block|pkill -KILL -f foo'
  'block|pkill -fx foo'
  'block|pkill foo -f'
  'block|/usr/bin/pkill -f foo'
  'block|killall foo'
  'block|sleep 1; pkill -f "sleep 1000"'
  'block|sudo pkill -f foo'
  'block|timeout 5 pkill -f foo'
  'block|pgrep foo | xargs -r killall'
  'block|echo $(pkill -f foo)'
  "block|bash -c 'pkill -f foo'"
  'block|eval "pkill -f foo"'
  "block|$(printf "bash <<'EOF'\npkill -f x\nEOF")"
  'block|pkill -f "unbalanced'
  "block|$incident"
  'block|git checkout -B x'
  'warn|ls /tmp/claude-1000'
)
for row in "${ct_cases[@]}"; do
    run "${row%%|*}" "${row#*|}" DEVPOD=1
done

# Bad input never blocks.
for bad in '' 'not json' '{"tool_input":{}}'; do
    printf '%s' "$bad" | "$hook" >/dev/null 2>&1
    rc=$?
    if [ $rc -eq 0 ]; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL bad input '$bad' exit $rc"; fi
done

echo "bash-guard: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
