#!/usr/bin/env bash
# PreToolUse (Bash): block two commands that have already cost real work.
#
#   - pkill / killall on the host. On 2026-10-02 a subagent ran, in its host
#     shell, `c=$(docker run -d ...) && ( ... docker exec -i $c ... ) & ...;
#     pkill -KILL -f "docker exec -i $c"`. $c was empty in the foreground
#     shell, so the pattern became "docker exec -i " and matched every devpod
#     tunnel: all 9 Claude sessions in the dl containers died at once. A name
#     pattern on a shared host always reaches further than you meant; a pid you
#     recorded does not. `kill <pid>` stays allowed. Inside a container this
#     rule is off (the blast radius is the container), and so is a pkill handed
#     to `docker exec` / `docker run`, which runs in the container too.
#
#   - Force-moving a branch: `git checkout -B`, `git switch -C` /
#     `--force-create`, `git branch -f` / `--force`. Container git 2.43 let
#     `checkout -B` move a branch that another worktree had checked out, which
#     silently rewrote that worktree's HEAD. This rule applies everywhere.
#
# Exit 2 blocks the call and hands stderr to the model as the reason, so each
# message says what to do instead. Anything this script cannot judge -- no jq
# and no python3, unparseable input -- is allowed with a note on stderr: a
# guard that crashes closed would wedge every Bash call in the session.
#
# Fast path matters (this runs before every Bash call): bash + one jq, and the
# python3 tokenizer only when the command contains "pkill" or "killall".
#
# Tests: hooks/tests/test-bash-guard.sh (a table of commands and verdicts).

input=$(cat)

if command -v jq >/dev/null 2>&1; then
    cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || {
        echo "bash-guard: could not parse hook input; allowing" >&2; exit 0; }
elif command -v python3 >/dev/null 2>&1; then
    cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null) || {
        echo "bash-guard: could not parse hook input; allowing" >&2; exit 0; }
else
    echo "bash-guard: no jq or python3 to read the hook input; allowing" >&2
    exit 0
fi
[ -n "$cmd" ] || exit 0

# --- force-moving a branch -------------------------------------------------
# One git invocation: `git`, global options, then the subcommand and its flags,
# all inside one segment (no ; & | between them).
# A backtick does not count as a command start, so a markdown-quoted mention
# in a commit message passes; an unquoted one in prose still blocks.
seg='[^;&|]*'
if printf '%s\n' "$cmd" | grep -Eq \
    "(^|[;&|([:space:]])git[[:space:]]${seg}(checkout${seg}[[:space:]]-[a-zA-Z]*B([[:space:]=]|\$)|switch${seg}[[:space:]](-[a-zA-Z]*C|--force-create)([[:space:]=]|\$)|branch${seg}[[:space:]](-[a-zA-Z]*f|--force)([[:space:]]|\$))"; then
    cat >&2 <<'EOF'
bash-guard: blocked a force-move of a git branch (checkout -B / switch -C / branch -f).
It can move a branch that another worktree has checked out.
Instead: run `git worktree list`. If the branch is checked out in another
worktree, work in that worktree. Otherwise create the branch with
`git checkout -b` / `git switch -c`, or ask the user before you move it.
EOF
    exit 2
fi

# --- pkill / killall on the host -------------------------------------------
case "$cmd" in *pkill*|*killall*) ;; *) exit 0 ;; esac
if [ -f /.dockerenv ] || [ -n "${REMOTE_CONTAINERS:-}${DEVPOD:-}" ]; then
    exit 0
fi

pkill_msg() {
    cat >&2 <<'EOF'
bash-guard: blocked pkill/killall on the host.
A name pattern on this host can match every devpod tunnel and Claude session
(it did on 2026-10-02). Instead: kill only a pid you recorded (`kill <pid>`,
e.g. from `$!` or `pgrep` output you have read). Do process experiments inside
a throwaway container (`docker run --rm ...`), never in the host shell.
EOF
}

if ! command -v python3 >/dev/null 2>&1; then
    # Cannot tell `echo pkill` from `pkill`: when unsure, block.
    if printf '%s\n' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])(pkill|killall)([^[:alnum:]_-]|$)'; then
        pkill_msg; exit 2
    fi
    exit 0
fi

# The tokenizer prints "block" when a pkill/killall sits in command position
# anywhere: after ; && || | & ( newline, in $(...) or backticks, behind
# sudo/env/xargs/timeout/nohup/..., or inside the script of bash -c / sh -c /
# eval / ssh. A pkill handed to docker exec/run (or dl exec) runs in the
# container and is allowed. `echo pkill` (an argument) is allowed. Text it
# cannot tokenize (unbalanced quotes) is blocked when the word appears at all.
verdict=$(CMD="$cmd" python3 - <<'PY' 2>/dev/null
import os, re, shlex

KILLERS = {"pkill", "killall"}
SEPS = {";", "&&", "||", "|", "&", "(", ")", "{", "}", "|&", ";;", "!", "\n"}
# Words that run their arguments as a command (sudo pkill, xargs -r pkill).
# Their options are skipped crudely; NUMERIC_ARG ones also take one value
# first (timeout 5 pkill). When a wrapper leads and the resolved command is
# not a container one, any killer word in the command blocks: unsure, block.
WRAPPERS = {"sudo", "doas", "env", "nohup", "nice", "ionice", "xargs", "exec",
            "command", "builtin", "time", "then", "do", "else", "elif", "if",
            "while", "until", "setsid", "stdbuf", "unbuffer", "watch",
            "timeout", "taskset", "chrt", "flock"}
NUMERIC_ARG = {"timeout", "taskset", "chrt", "flock"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
STARTS_KILLER = re.compile(r"\s*(\S*/)?(pkill|killall)\s+\S")
WORD = re.compile(r"(^|[^\w-])(pkill|killall)([^\w-]|$)")

def lex(s):
    s = s.replace("\n", " ; ")
    lx = shlex.shlex(s, posix=True, punctuation_chars=";&|(){}!")
    lx.whitespace_split = True
    return list(lx)

def simple_commands(tokens):
    cur = []
    for t in tokens:
        if t in SEPS or set(t) <= set(";&|(){}!"):
            if cur:
                yield cur
            cur = []
        else:
            cur.append(t)
    if cur:
        yield cur

def blocked(s, depth=0):
    if depth > 6:
        return bool(WORD.search(s))
    if not WORD.search(s):
        return False
    try:
        tokens = lex(s)
    except ValueError:
        return True
    # Command substitutions, quoted or not: "$(pkill x)" or `pkill x`.
    for m in re.finditer(r"\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)|`([^`]*)`", s):
        if blocked(m.group(1) or m.group(2) or "", depth + 1):
            return True
    for words in simple_commands(tokens):
        i = 0
        while i < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]):
            i += 1
        wrapped = False
        while i < len(words):
            base = os.path.basename(words[i])
            if base not in WRAPPERS:
                break
            wrapped = True
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
            if base in NUMERIC_ARG and i < len(words):
                i += 1
            while base == "env" and i < len(words) and "=" in words[i]:
                i += 1
        if i >= len(words):
            continue
        base = os.path.basename(words[i])
        rest = words[i + 1:]
        if base in KILLERS:
            return True
        if base in ("docker", "podman") and any(w in ("exec", "run") for w in rest[:3]):
            continue
        if base == "dl" and "exec" in rest[:3]:
            continue
        if wrapped and any(os.path.basename(w) in KILLERS for w in rest):
            return True
        # An argument that starts with a killer may be a script some runner
        # executes (su -c, nsenter, parallel ...). It may also be a commit
        # message; unsure, block.
        if any(STARTS_KILLER.match(w) for w in rest):
            return True
        if base in SHELLS:
            for j, w in enumerate(rest):
                if w.startswith("-") and "c" in w.lstrip("-") and not w.startswith("--") and j + 1 < len(rest):
                    if blocked(rest[j + 1], depth + 1):
                        return True
                    break
            continue
        if base in ("eval", "ssh"):
            args = [w for w in rest if not w.startswith("-")]
            if base == "ssh":
                args = args[1:]
            if blocked(" ".join(args), depth + 1):
                return True
            continue
    return False

print("block" if blocked(os.environ["CMD"]) else "allow")
PY
)

case "$verdict" in
    block) pkill_msg; exit 2 ;;
    allow) exit 0 ;;
    *) echo "bash-guard: pkill check failed; blocking to be safe" >&2; pkill_msg; exit 2 ;;
esac
