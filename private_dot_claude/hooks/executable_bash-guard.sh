#!/usr/bin/env bash
# PreToolUse (Bash): block commands that have already cost real work, and warn
# on one more.
#
#   - `pkill -f` / `pkill --full` / `killall`, everywhere (host and container).
#     The harness runs each Bash call as `bash -c '<the command>'`, so a
#     `pkill -f <pattern>` matches the shell that runs it and kills it: the
#     call returns "Exit code 144". In the week to 2026-10-05 this cut short 37
#     calls in 17 sessions. `killall` has no safe use here either. This rule
#     also checks a pkill handed to `docker exec` / `docker run` / `dl exec`,
#     and a heredoc body fed to one. Plain `pkill <name>` without -f stays
#     allowed in a container.
#
#   - pkill / killall on the host. On 2026-10-02 a subagent ran, in its host
#     shell, `c=$(docker run -d ...) && ( ... docker exec -i $c ... ) & ...;
#     pkill -KILL -f "docker exec -i $c"`. $c was empty in the foreground
#     shell, so the pattern became "docker exec -i " and matched every devpod
#     tunnel: all 9 Claude sessions in the dl containers died at once. A name
#     pattern on a shared host always reaches further than you meant; a pid you
#     recorded does not. `kill <pid>` stays allowed. Inside a container this
#     rule is off (the blast radius is the container), and so is a pkill handed
#     to `docker exec` / `docker run`, which runs in the container too. The
#     -f / killall rule above still applies there.
#
#   - Force-moving a branch: `git checkout -B`, `git switch -C` /
#     `--force-create`, `git branch -f` / `--force`. Container git 2.43 let
#     `checkout -B` move a branch that another worktree had checked out, which
#     silently rewrote that worktree's HEAD. This rule applies everywhere.
#
#   - A path under /tmp/claude- (a warning, not a block). /tmp is tmpfs (RAM)
#     on Ubuntu 26.04 and inside the kinisi containers; CLAUDE_CODE_TMPDIR
#     (~/.cache/claude-tmp, set in .bash_env) is on disk. Skills and agents
#     kept writing clones and downloads to /tmp/claude-<uid> after the move.
#     The call runs; the model gets a note (additionalContext) that names the
#     on-disk path.
#
# Text that is data, not commands, is not checked: a heredoc body (unless the
# heredoc feeds a shell: `bash <<EOF`, `ssh host <<EOF`, `cat <<EOF | sh`),
# and a quoted message value (`git commit/tag -m/-F`, `gh pr|issue
# create|edit|comment --body/--title`, `gh release create|edit --notes/--title`).
# A $(...) or `...` inside a double-quoted value or an unquoted-delimiter
# heredoc still runs, so it is still checked.
#
# Exit 2 blocks the call and hands stderr to the model as the reason, so each
# message says what to do instead. A warning exits 0 and prints PreToolUse
# JSON with additionalContext on stdout. Anything this script cannot judge -- no jq
# and no python3, unparseable input -- is allowed with a note on stderr: a
# guard that crashes closed would wedge every Bash call in the session. Text
# it can read but cannot tokenize (unbalanced quotes) is blocked when a rule's
# words appear.
#
# Fast path matters (this runs before every Bash call): bash + one jq + one
# grep. The python3 tokenizer runs only when the raw text already matches a
# rule (the git pattern, the word pkill/killall, or /tmp/claude-); it then
# strips the data spans and checks again.
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

git_msg() {
    cat >&2 <<'EOF'
bash-guard: blocked a force-move of a git branch (checkout -B / switch -C / branch -f).
It can move a branch that another worktree has checked out.
Instead: run `git worktree list`. If the branch is checked out in another
worktree, work in that worktree. Otherwise create the branch with
`git checkout -b` / `git switch -c`, or ask the user before you move it.
EOF
}

pkill_msg() {
    cat >&2 <<'EOF'
bash-guard: blocked pkill/killall on the host.
A name pattern on this host can match every devpod tunnel and Claude session
(it did on 2026-10-02). Instead: kill only a pid you recorded (`kill <pid>`,
e.g. from `$!` or `pgrep` output you have read). Do process experiments inside
a throwaway container (`docker run --rm ...`), never in the host shell.
EOF
}

pkill_full_msg() {
    cat >&2 <<'EOF'
bash-guard: blocked `pkill -f` / `pkill --full` / `killall`.
Your Bash call runs as `bash -c '<your command>'`. `pkill -f <pattern>` matches
that shell too and kills it: the call ends with "Exit code 144".
Instead, do one of these:
  - Record the pid when you start the process (`cmd & pid=$!`), then `kill $pid`.
  - Run `pgrep -f '<pattern>' | grep -vx $$`, read the pids, then `kill <pid> ...`.
On the host, also do process experiments inside a throwaway container.
EOF
}

# A warning: exit 0, with a note for the model. The text is fixed, so no
# JSON escaping is needed beyond what is written here.
tmp_warn() {
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"bash-guard warning: this command uses a path under /tmp/claude-. /tmp is tmpfs, so files there are held in RAM until a reboot. Put temporary files in \"${CLAUDE_CODE_TMPDIR:-$HOME/.cache/claude-tmp}/claude-$(id -u)\" (on disk) or in your scratchpad. If your scratchpad itself is under /tmp/claude-, the session started before CLAUDE_CODE_TMPDIR was set: use ~/.cache/claude-tmp/claude-$(id -u) instead."}}'
}

# --- cheap prefilters on the raw text -----------------------------------------
# Git: one git invocation -- `git`, global options, then the subcommand and its
# flags, all inside one segment (no ; & | between them). A backtick does not
# count as a command start, so a markdown-quoted mention passes.
# The python check below applies the same pattern (GIT_RE) to the stripped text.
seg='[^;&|]*'
GIT_ERE="(^|[;&|([:space:]])git[[:space:]]${seg}(checkout${seg}[[:space:]]-[a-zA-Z]*B([[:space:]=]|\$)|switch${seg}[[:space:]](-[a-zA-Z]*C|--force-create)([[:space:]=]|\$)|branch${seg}[[:space:]](-[a-zA-Z]*f|--force)([[:space:]]|\$))"
git_hit=0
printf '%s\n' "$cmd" | grep -Eq "$GIT_ERE" && git_hit=1

in_ct=0
if [ -f /.dockerenv ] || [ -n "${REMOTE_CONTAINERS:-}${DEVPOD:-}" ]; then in_ct=1; fi
pk_hit=0
case "$cmd" in *pkill*|*killall*) pk_hit=1 ;; esac
tmp_hit=0
case "$cmd" in */tmp/claude-*) tmp_hit=1 ;; esac
[ "$git_hit$pk_hit$tmp_hit" = 000 ] && exit 0

if ! command -v python3 >/dev/null 2>&1; then
    # Cannot strip data spans: when unsure, block.
    [ "$git_hit" = 1 ] && { git_msg; exit 2; }
    if printf '%s\n' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])killall([^[:alnum:]_-]|$)|(^|[^[:alnum:]_-])pkill([^[:alnum:]_-].*)?[[:space:]](-[a-z]*f[a-z]*|--full)([^[:alnum:]_-]|$)'; then
        pkill_full_msg; exit 2
    fi
    if [ "$in_ct" = 0 ] && printf '%s\n' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])(pkill|killall)([^[:alnum:]_-]|$)'; then
        pkill_msg; exit 2
    fi
    [ "$tmp_hit" = 1 ] && tmp_warn
    exit 0
fi

# The python check prints "git", "pkillf" (the -f / killall rule), "pkill"
# (the host rule), "tmp" (the /tmp/claude- warning) or "allow".
#
# strip() returns the text with the data spans replaced: a non-shell heredoc
# body goes (an unquoted-delimiter body keeps its $(...) and `...`), and a
# quoted message value becomes '' (a double-quoted one keeps its $(...) and
# `...`). A shell-fed heredoc body stays, itself stripped. A body fed to
# `docker exec/run ... bash` or `dl exec` runs in the container: it goes for
# the pkill rules and stays for the git rule; the -f / killall rule then
# checks it on its own.
#
# The pkill rule prints "pkill" when a pkill/killall sits in command position
# anywhere in the stripped text: after ; && || | & ( newline, in $(...) or
# backticks, behind sudo/env/xargs/timeout/nohup/..., or inside the script of
# bash -c / sh -c / eval / ssh. `echo pkill` (an argument) is allowed. The
# -f / killall rule (host=False) blocks only a killer that is killall or has
# -f / --full after it, and it also looks inside docker exec / run, dl exec.
verdict=$(CMD="$cmd" GIT_HIT=$git_hit PK_HIT=$pk_hit TMP_HIT=$tmp_hit IN_CT=$in_ct python3 - <<'PY' 2>/dev/null
import os, re, shlex

class Unbalanced(Exception):
    pass

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
# A heredoc fed to one of these is commands, not data.
RUNNERS = SHELLS | {"ssh", "su", "eval", "source", ".", "nsenter", "script"}
STARTS_KILLER = re.compile(r"\s*(\S*/)?(pkill|killall)\s+\S")
WORD = re.compile(r"(^|[^\w-])(pkill|killall)([^\w-]|$)")
FULL_FLAG = re.compile(r"(-[a-z]*f[a-z]*|--full)$")
# Raw-text form of the -f / killall rule, for text that cannot be tokenized.
RAW_FULL = re.compile(r"(^|[^\w-])killall([^\w-]|$)"
                      r"|(^|[^\w-])pkill(?![\w-]).*\s(-[a-z]*f[a-z]*|--full)(?![\w-])", re.S)
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GIT_RE = re.compile(
    r"(^|[;&|(\s])git\s[^;&|\n]*(checkout[^;&|\n]*\s-[a-zA-Z]*B([\s=]|$)"
    r"|switch[^;&|\n]*\s(-[a-zA-Z]*C|--force-create)([\s=]|$)"
    r"|branch[^;&|\n]*\s(-[a-zA-Z]*f|--force)(\s|$))", re.M)
GIT_MSG_SUBS = {"commit", "tag"}
GH_MSG = {("pr", "create"), ("pr", "edit"), ("pr", "comment"),
          ("issue", "create"), ("issue", "edit"), ("issue", "comment")}
GH_PR_FLAGS = {"-b", "--body", "-t", "--title"}
GH_REL_FLAGS = {"-n", "--notes", "-t", "--title"}
META = set(";&|()<>")

def resolve(vals):
    """Skip VAR=x and wrappers. Return (base, rest, wrapped); base None if nothing is left."""
    i = 0
    while i < len(vals) and ASSIGN.match(vals[i]):
        i += 1
    wrapped = False
    while i < len(vals):
        base = os.path.basename(vals[i])
        if base not in WRAPPERS:
            break
        wrapped = True
        i += 1
        while i < len(vals) and vals[i].startswith("-"):
            i += 1
        if base in NUMERIC_ARG and i < len(vals):
            i += 1
        while base == "env" and i < len(vals) and "=" in vals[i]:
            i += 1
    if i >= len(vals):
        return None, [], wrapped
    return os.path.basename(vals[i]), vals[i + 1:], wrapped

def is_container(base, rest):
    return (base in ("docker", "podman") and any(w in ("exec", "run") for w in rest[:3])) or \
           (base == "dl" and "exec" in rest[:3])

def feed_kind(vals):
    """What a heredoc on this command feeds: 'shell', 'container' or 'data'."""
    base, rest, _ = resolve(vals)
    if base is None or base in RUNNERS:
        return "shell"   # `sudo -s <<EOF`, a bare `<<EOF`: unsure, treat as commands
    if is_container(base, rest):
        return "container"
    return "data"

def message_flag(vals, flag):
    """True when `flag` (the word before a quoted value) takes a message on this command."""
    base, rest, _ = resolve(vals)
    if base == "git":
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            j += 2 if rest[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
        if j < len(rest) and rest[j] in GIT_MSG_SUBS:
            return flag in ("--message", "--file") or bool(re.fullmatch(r"-[a-zA-Z]*[mF]", flag))
    elif base == "gh" and len(rest) >= 2:
        if (rest[0], rest[1]) in GH_MSG:
            return flag in GH_PR_FLAGS
        if rest[0] == "release" and rest[1] in ("create", "edit"):
            return flag in GH_REL_FLAGS
    return False

def unquote(raw):
    return re.sub(r"""['"\\]""", "", raw)

class Scanner:
    """Walk one shell text with quotes, $(...), backticks and heredocs, and
    record which spans to replace. Indices are absolute in self.s."""

    def __init__(self, s, mode, bodies=None):
        self.s, self.mode, self.repl = s, mode, []
        # Heredoc bodies fed to a container, cut out in pkill mode.
        self.bodies = [] if bodies is None else bodies

    # -- replacements -----------------------------------------------------
    def add(self, a, b, text):
        self.repl = [r for r in self.repl if not (r[0] >= a and r[1] <= b)] + [(a, b, text)]

    def render(self, a, b):
        out, i = [], a
        for ra, rb, t in sorted(r for r in self.repl if r[0] >= a and r[1] <= b):
            if ra < i:
                continue
            out.append(self.s[i:ra]); out.append(t); i = rb
        out.append(self.s[i:b])
        return "".join(out)

    def run(self):
        self.parse(0, None)
        return self.render(0, len(self.s))

    # -- lexing pieces ----------------------------------------------------
    def squote(self, i):          # s[i] == "'"
        j = self.s.find("'", i + 1)
        if j < 0:
            raise Unbalanced
        return j + 1

    def ansi(self, i):            # s[i:i+2] == "$'"
        s, j = self.s, i + 2
        while j < len(s):
            if s[j] == "\\":
                j += 2; continue
            if s[j] == "'":
                return j + 1
            j += 1
        raise Unbalanced

    def backtick(self, i):        # s[i] == "`"
        s, j = self.s, i + 1
        while j < len(s):
            if s[j] == "\\":
                j += 2; continue
            if s[j] == "`":
                return j + 1
            j += 1
        raise Unbalanced

    def dquote(self, i, subs):    # s[i] == '"'; returns end, appends (a, b) of $(...) / `...`
        s, j = self.s, i + 1
        while j < len(s):
            c = s[j]
            if c == "\\":
                j += 2
            elif c == '"':
                return j + 1
            elif s.startswith("$(", j):
                e = self.parse(j + 2, ")"); subs.append((j, e)); j = e
            elif c == "`":
                e = self.backtick(j); subs.append((j, e)); j = e
            else:
                j += 1
        raise Unbalanced

    def word(self, i):
        """Read one word. Returns (end, whole_quote, subs): whole_quote is the
        quote char when the word is exactly one quoted string."""
        s, n, j, subs = self.s, len(self.s), i, []
        first_end = None
        while j < n:
            c = s[j]
            if c in " \t\n" or (c in META and not s.startswith(("<(", ">("), j)):
                break
            if c == "\\":
                j += 2
            elif c == "'":
                j = self.squote(j)
            elif c == '"':
                j = self.dquote(j, subs)
            elif s.startswith("$'", j):
                j = self.ansi(j)
            elif s.startswith(("$(", "<(", ">("), j):
                e = self.parse(j + 2, ")"); subs.append((j, e)); j = e
            elif s.startswith("${", j):
                e = s.find("}", j)
                if e < 0:
                    raise Unbalanced
                j = e + 1
            elif c == "`":
                e = self.backtick(j); subs.append((j, e)); j = e
            else:
                j += 1
            if first_end is None:
                first_end = j
        whole = s[i] if s[i] in "'\"" and first_end == j else None
        return min(j, n), whole, subs

    def keep_subs(self, quote, subs):
        inner = " ".join(self.render(a, b) for a, b in subs)
        return f'"{inner}"' if quote == '"' else "''"

    def body_subs(self, a, b):
        """The $(...) and `...` in an unquoted-delimiter heredoc body."""
        s, j, out = self.s, a, []
        while j < b:
            if s[j] == "\\":
                j += 2
            elif s.startswith("$(", j):
                e = self.parse(j + 2, ")"); out.append(self.render(j, e)); j = e
            elif s[j] == "`":
                e = self.backtick(j); out.append(s[j:e]); j = e
            else:
                j += 1
        return "".join(x + "\n" for x in out)

    # -- the command list ---------------------------------------------------
    def parse(self, i, stop):
        """Parse a command list from i. With stop=")", end at the unmatched ")"
        and return the index after it; otherwise run to the end."""
        s, n = self.s, len(self.s)
        words, line_cmds, pending, depth = [], [], [], 0

        def finish():
            nonlocal words
            if words:
                line_cmds.append(words)
            words = []

        while i < n:
            c = s[i]
            if c in " \t":
                i += 1
            elif s.startswith("\\\n", i):
                i += 2
            elif c == "\n":
                finish()
                i += 1
                for h in pending:
                    i = self.heredoc(i, h, line_cmds)
                pending, line_cmds = [], []
            elif c == "#":
                e = s.find("\n", i)
                i = n if e < 0 else e
            elif c == ")":
                finish()
                if stop and depth == 0:
                    return i + 1
                depth -= 1; i += 1
            elif c == "(":
                finish(); depth += 1; i += 1
            elif c in ";&|":
                finish()
                while i < n and s[i] in ";&|":
                    i += 1
            elif s.startswith("<<<", i):
                i += 3
            elif s.startswith("<<", i) and not s.startswith("<<(", i):
                j = i + 2
                dash = j < n and s[j] == "-"
                if dash:
                    j += 1
                while j < n and s[j] in " \t":
                    j += 1
                if j >= n or s[j] in " \t\n;&|()<>":
                    raise Unbalanced
                e, _, _ = self.word(j)
                raw = s[j:e]
                pending.append((dash, unquote(raw), any(q in raw for q in "'\"\\"), words))
                i = e
            elif c in "<>" and not s.startswith(("<(", ">("), i):
                i += 1
                if i < n and s[i] in "&|>":
                    i += 1
            else:
                e, whole, subs = self.word(i)
                raw = s[i:e]
                vals = [unquote(self.s[a:b]) for a, b in words]
                m = re.match(r"(--[a-z-]+)=(['\"])", raw)
                if whole and vals and message_flag(vals, vals[-1]):
                    self.add(i, e, self.keep_subs(whole, subs))
                elif m and message_flag(vals + [m.group(1)], m.group(1)):
                    vs = len(m.group(1)) + 1
                    e2, whole2, subs2 = self.word(i + vs)
                    if e2 == e and whole2:
                        self.add(i + vs, e, self.keep_subs(whole2, subs2))
                words.append((i, e))
                i = e
        finish()
        if stop:
            raise Unbalanced
        return n

    def heredoc(self, i, h, line_cmds):
        """Handle one heredoc body starting at i. Returns the index after its terminator."""
        dash, delim, quoted, own = h
        s, n = self.s, len(self.s)
        a, j, end = i, i, None
        while j <= n:
            e = s.find("\n", j)
            line_end = n if e < 0 else e
            line = s[j:line_end]
            if (line.lstrip("\t") if dash else line) == delim:
                end, after = j, (line_end + 1 if e >= 0 else n)
                break
            if e < 0:
                break
            j = e + 1
        if end is None:
            end = after = n
        vals = lambda ws: [unquote(s[x:y]) for x, y in ws]
        kind = feed_kind(vals(own))
        if kind == "data":
            kinds = {feed_kind(vals(ws)) for ws in line_cmds}
            kind = "shell" if "shell" in kinds else "container" if "container" in kinds else "data"
        if kind == "shell" or (kind == "container" and self.mode == "git"):
            self.add(a, end, Scanner(s[a:end], self.mode, self.bodies).run())
        elif kind == "container" or quoted:
            if kind == "container":
                self.bodies.append(s[a:end])
            self.add(a, end, "")
        else:
            self.add(a, end, self.body_subs(a, end))
        return after

def strip(s, mode):
    return Scanner(s, mode).run()

# --- pkill rule ----------------------------------------------------------------
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

def full_kill(words):
    """True when these words run killall, or pkill with -f / --full after it.
    A word that is a whole script (sh -c 'pkill -f x') is split too."""
    toks = []
    for w in words:
        try:
            toks += shlex.split(w)
        except ValueError:
            toks += w.split()
    seen = False
    for t in toks:
        base = os.path.basename(t.strip(";&|(){}!`$"))
        if base == "killall":
            return True
        if base == "pkill":
            seen = True
        elif seen and FULL_FLAG.match(t):
            return True
    return False

def pkill_blocked(s, host, depth=0):
    """host=True: the host rule (any killer). host=False: the -f / killall rule."""
    unsure = (lambda t: bool(WORD.search(t))) if host else (lambda t: bool(RAW_FULL.search(t)))
    hit = (lambda ws: True) if host else full_kill
    if depth > 6:
        return unsure(s)
    if not WORD.search(s):
        return False
    sc = Scanner(s, "pkill")
    try:
        s2 = sc.run()
    except (Unbalanced, IndexError, RecursionError):
        return unsure(s)
    s = s2
    # A body fed to a container runs there: only the -f / killall rule.
    if any(pkill_blocked(b, False, depth + 1) for b in sc.bodies):
        return True
    if not WORD.search(s):
        return False
    try:
        tokens = lex(s)
    except ValueError:
        return unsure(s)
    # Command substitutions, quoted or not: "$(pkill x)" or `pkill x`.
    for m in re.finditer(r"\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)|`([^`]*)`", s):
        if pkill_blocked(m.group(1) or m.group(2) or "", host, depth + 1):
            return True
    for words in simple_commands(tokens):
        base, rest, wrapped = resolve(words)
        if base is None:
            continue
        if base in KILLERS:
            if hit([base] + rest):
                return True
            continue
        if is_container(base, rest):
            # Runs in the container: the host rule is off, -f / killall is not.
            if full_kill(rest):
                return True
            continue
        if wrapped and any(os.path.basename(w) in KILLERS for w in rest) and hit(rest):
            return True
        # An argument that starts with a killer may be a script some runner
        # executes (su -c, nsenter, parallel ...). Message values are already
        # stripped, so what is left is unsure: block.
        if any(STARTS_KILLER.match(w) for w in rest) and hit(rest):
            return True
        if base in SHELLS:
            for j, w in enumerate(rest):
                if w.startswith("-") and "c" in w.lstrip("-") and not w.startswith("--") and j + 1 < len(rest):
                    if pkill_blocked(rest[j + 1], host, depth + 1):
                        return True
                    break
            continue
        if base in ("eval", "ssh"):
            args = [w for w in rest if not w.startswith("-")]
            if base == "ssh":
                args = args[1:]
            if pkill_blocked(" ".join(args), host, depth + 1):
                return True
            continue
    return False

# --- git rule ------------------------------------------------------------------
def git_blocked(s):
    try:
        return bool(GIT_RE.search(strip(s, "git")))
    except (Unbalanced, IndexError, RecursionError):
        return True

# --- /tmp/claude- warning ---------------------------------------------------------
def tmp_used(s):
    # Same spans as the git rule: a body fed to a container is still checked,
    # since /tmp in a kinisi container is a tmpfs too. Unsure: warn.
    try:
        return "/tmp/claude-" in strip(s, "git")
    except (Unbalanced, IndexError, RecursionError):
        return True

cmd = os.environ["CMD"]
if os.environ.get("GIT_HIT") == "1" and git_blocked(cmd):
    print("git")
elif os.environ.get("PK_HIT") == "1" and pkill_blocked(cmd, False):
    print("pkillf")
elif os.environ.get("PK_HIT") == "1" and os.environ.get("IN_CT") != "1" and pkill_blocked(cmd, True):
    print("pkill")
elif os.environ.get("TMP_HIT") == "1" and tmp_used(cmd):
    print("tmp")
else:
    print("allow")
PY
)

case "$verdict" in
    git) git_msg; exit 2 ;;
    pkillf) pkill_full_msg; exit 2 ;;
    pkill) pkill_msg; exit 2 ;;
    tmp) tmp_warn; exit 0 ;;
    allow) exit 0 ;;
    *)
        if [ "$git_hit$pk_hit" = 00 ]; then tmp_warn; exit 0; fi
        echo "bash-guard: check failed; blocking to be safe" >&2
        if [ "$git_hit" = 1 ]; then git_msg; else pkill_full_msg; fi
        exit 2 ;;
esac
