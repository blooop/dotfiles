# Dotfiles

Personal development environment configuration managed with [Chezmoi](https://www.chezmoi.io/) and [Pixi](https://pixi.sh/).

## Profiles

Every install picks a **machine profile** — the level of invasivity. The profile is
resolved once at `chezmoi init` (interactive prompt, or `CHEZMOI_PROFILE` env var, or
auto-detected from `AGS_SHELL`/`DEVPOD`), persisted in `~/.config/chezmoi/chezmoi.toml`,
and every later `chezmoi apply`/`update` uses it — no env vars needed after setup.

Profiles map to **capability flags**; templates gate on the flags, never on profile
names. The matrix lives in one place: `.chezmoi.toml.tmpl`.

| Flag | personal | shared | robot | container | Controls |
|------|----------|--------|-------|-----------|----------|
| `identity` | ✓ | ✗ | ✗ | ✓ | git user name/email |
| `gui` | ✓ | ✗ | ✗ | ✗ | Kitty, nerd fonts, uhk-agent, nvtop |
| `heavy` | ✓ | ✗ | ✗ | ✗ | rust, neovim + config, nodejs, devpod, ccache, pi |
| `host` | ✓ | ✗ | ✓ | ✗ | git, git-lfs, openssh, curl, unzip |
| `monitor` | ✓ | ✓ | ✓ | ✗ | htop, btop |
| `agents` | ✓ | ✓ | ✗ | ✗ | codex, opencode (AI coding CLIs) |

- **personal** — your own machine: everything.
- **shared** — shared account (ags isolated shells, lab PCs): core CLI tools + system monitors + AI coding agents (codex, opencode), git identity omitted so others on the account can't impersonate you.
- **robot** — robots/appliances: core + host tools (git, ssh, monitoring), no identity, no GUI, no toolchains.
- **container** — devcontainers/DevPod: core tools only; identity kept (DevPod injects git credentials; `.gitconfig` is skipped in favor of the XDG fallback).

Adding a new machine class = one row in the matrix in `.chezmoi.toml.tmpl`, no other
template changes.

To change an existing machine's profile, re-run init (apply alone reuses the stored one):
```bash
CHEZMOI_PROFILE=robot chezmoi init --apply
```

## Usage

### Quick Install

One-liner that handles cache permissions and installs everything. The profile is
auto-detected (DevPod → `container`, ags → `shared`, otherwise `personal`) or set
explicitly with `CHEZMOI_PROFILE`:

```bash
# personal machine
curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/install.sh | bash

# robot / shared machine / container — set the profile explicitly
curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/install.sh | CHEZMOI_PROFILE=robot bash
```

### Manual Installation

```bash
sudo apt update && sudo apt install -y curl && \
curl -fsSL https://pixi.sh/install.sh | bash && \
export PATH="$HOME/.pixi/bin:$PATH" && \
pixi global install chezmoi && \
CHEZMOI_PROFILE=personal chezmoi init --apply git@github.com:blooop/dotfiles.git && \
pixi global sync
```

Replace `personal` with `shared`, `robot`, or `container` to match the machine. Omit
`CHEZMOI_PROFILE` entirely to be prompted interactively.

> **Note:** Always inspect scripts before running. You can review files at [github.com/blooop/dotfiles](https://github.com/blooop/dotfiles)

### Development Containers

For development containers, you have two options:

**DevPod (automated):**

First-time setup - add the Docker provider and configure automatic dotfiles:
```bash
devpod provider add docker
devpod context set-options -o DOTFILES_URL=https://github.com/blooop/dotfiles
```

This configures devpod to automatically install dotfiles for all new workspaces.

Alternatively, use the `--dotfiles` argument for individual workspaces:
```bash
devpod up <project-repo> --dotfiles https://github.com/blooop/dotfiles
```
DevPod will automatically detect and run the `install.sh` script to configure your environment.

**Manual (any devcontainer):**

Use the DevContainers installation command above, or add to your devcontainer configuration.

## What's Included

### Core Tools (all profiles)
- **Search & navigation** - fzf, fd, ripgrep, zoxide (smart cd), broot (tree browser)
- **Git** - lazygit, forgit, gh, git-forgit
- **Terminal** - zellij (multiplexer), zjsh, vim
- **Management** - chezmoi, pixi, topgrade, prek, isd
- **Utilities** - jq, xclip, sshpass, go, claude-shim (`claude`, `cld`, `cldr`)

### Capability-Gated Tools (see Profiles matrix above)
- **`host`** - git, git-lfs, openssh, curl, unzip, speedtest-go, `nvidia-upgrades` script
- **`monitor`** - htop, btop
- **`heavy`** - neovim (+ full config), nodejs, rust toolchain, devpod, lazydocker, ccache, pi, yq
- **`agents`** - codex, opencode (AI coding CLIs)
- **`gui`** - Kitty, nvtop, uhk-agent, JetBrainsMono nerd fonts

## Git Configuration

The git configuration (included in DevContainers and Full installations) provides:

- **Useful aliases** - `com` (checkout main), `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push), `pushf` (push --force-with-lease)
- **Sensible defaults** - Auto-setup remotes, `push.default = simple`
- **Stacked-PR friendly** - `rebase.updateRefs` (rewrite stacked refs in one rebase) and `rerere` (remember conflict resolutions across restacks)
- **Personal credentials** - Uses Austin Gregg-Smith's git user info on profiles with the `identity` flag (`personal`, `container`); omitted on `shared` and `robot` profiles so commits made by others on the account can't impersonate you

## Terminal Vibe-Coding Workflow

The terminal environment is deliberately layered:

```text
Kitty OS window                      (shell = zjshell, so this is already Zellij)
└── Zellij session
    ├── a new session is one bare pane      ← default_layout "simple"
    └── a project session, via zj or Ctrl+; t w
        ├── work tab
        │   ├── Neovim (58%, focused)
        │   └── agent stack (42%)
        │       ├── Codex (suspended until Enter)
        │       └── Claude (suspended until Enter)
        └── terms tab
            └── shell
```

Kitty is only the graphical terminal frontend. Zellij owns persistence, tabs,
panes, floating tools, and session restoration. Avoid Kitty panes and tabs in
this workflow: use another Kitty **OS window** when a separate terminal is
useful, and use Zellij for everything inside it.

Kitty's `shell` is `zjshell`, so every window is a Zellij session from the
moment it opens and can be split and tabbed without typing anything first. Each
window gets **its own** session. Attaching several windows to one shared session
instead makes them clients of it, so Zellij mirrors them — three windows showing
one screen, annotated `MY FOCUS AND: FOCUSED USERS`, which is its multiplayer
indicator rather than an error. SSH deliberately differs, because there a single
resumable session is exactly the point.

The cost is that sessions accumulate: closing a window with the window manager
only detaches, and `session_serialization` keeps them. `zjclean` prunes them with
an fzf picker showing each session's pane count and tab names, because from the
outside an abandoned session is indistinguishable from one holding four tabs and a
waiting agent.

`exit` in the last pane ends the session and closes the window, which takes two
cooperating pieces. Zellij quits when the last pane in a session closes, but the
zjstatus bar is itself a pane, so a tab is never empty: on its own, `exit` in the
only shell closes its pane and leaves the session running with nothing but the
bars in it, in a window that no longer answers `exit`. Zellij has no option for
this and no `quit` CLI action, so `.bash_env` gives each pane shell an `EXIT` trap
that counts terminal panes with `zellij action list-panes` and ends the session
when the one it is about to close is the last. The count spans every tab, so a
shell in another tab keeps the session alive, and a query that answers nothing
leaves it alone — being wrong the other way would kill panes still in use. Only
panes running a shell are covered: Neovim and the agents are command panes with no
shell in them, so a session whose last pane is one of those still needs `F7` or
`Ctrl+; x`.

`zjshell` does not `exec` Zellij, so that a Zellij which cannot start does not take
the window with it. Only that case falls through to a login shell: it exits
non-zero, whereas a session that ended — its last pane exited, or the client
detached — exits `0` and closes the window. Leaving a bare login shell in a window
that is no longer a Zellij session is the surprising outcome, and it is what made
`exit` need typing twice. A new session is deliberately **one bare pane**: opening
a terminal should be cheap and should never start processes that were not asked
for. The Neovim-and-agents grid is opt-in — `zj` applies it to configured zjsh
projects, and `Ctrl+; t w` opens it as a tab in the session you are already in.

`zjshell` sets PATH explicitly rather than inheriting it. The graphical session's
PATH is fixed at login and contains neither `~/.pixi/bin` nor `~/.local/bin`, and
running through `bash -lc` does **not** fix that: `~/.profile` sources `~/.bashrc`,
but Ubuntu's `~/.bashrc` returns immediately for non-interactive shells, so
`~/.bash_env` — where PATH is actually built — is never reached. Zellij would then
be missing and every desktop-launched window would quietly fall back to a plain
shell. It also falls back to an interactive login shell when Zellij is genuinely
absent or already owns the process, so a broken Zellij cannot make windows
unusable.

Note that Kitty reads `shell` at startup, so after changing it an already-running
Kitty keeps handing new windows the old shell until it is restarted.

#### Over SSH

An SSH login is the same idea by a different route: `private_dot_bash_env`
attaches to one persistent session per client machine, creating it if necessary. A
dropped connection therefore costs nothing — reconnecting reattaches the same
session rather than starting over — and projects are switched inside it with
`F10`. Detaching exits `0`, which ends the SSH session exactly as closing a Kitty
window does locally.

Bash sources `.bashrc` for *remote non-interactive* shells too, which is how a
naive version of this breaks `scp`, `rsync`, and `ssh host <command>`. The
autostart is guarded on an interactive shell with a real tty on both stdin and
stdout, `SSH_CONNECTION` present, `SSH_ORIGINAL_COMMAND` absent, neither `ZELLIJ`
nor `TMUX` already set, `TERM_PROGRAM` not `vscode` (Remote-SSH and the
integrated terminal manage their own tabs), and `TERM` not `dumb`. It sits at the
very end of the file, after `~/.bash_env.local`, so a machine can opt out with
`ZELLIJ_AUTOSTART=0`.

If Zellij is what breaks, it exits non-zero and the login falls through to a
normal shell rather than dropping the connection. `ssh -t <host> 'bash --norc
-i'` skips the file altogether.

##### One session per client, not one named `main`

The session is named `main-<client hostname>` rather than plain `main`, because
some hosts are logged into with a *shared account* — a CI box reached as one
service user. Two people attaching to the same session become clients of it and
Zellij mirrors them: both see one screen, annotated `MY FOCUS AND: FOCUSED USERS`.
Nothing is lost, but it is a baffling thing to walk into, and an account being
shared only occasionally is exactly when it happens.

The client's name reaches the far end in `LC_ZJ_CLIENT`. `LC_`-prefixed because
sshd's stock `AcceptEnv` is `LANG LC_*`, so an `LC_` variable crosses without any
server-side configuration — the usual trick for propagating a value you control
to a host you may not. It still needs the client to send it, which is one block
in `~/.ssh/config`:

```sshconfig
Host *
  SendEnv LC_ZJ_CLIENT
```

Without that the variable simply does not arrive, the far end falls back to
`main`, and behaviour is exactly what it was before. Set `ZJ_SSH_SESSION` in a
host's `~/.bash_env.local` to override the name outright.

##### Two multiplexers

SSHing from a Kitty window into a host that autostarts Zellij gives you two of
them, one inside the other. The local `ZELLIJ` variable does not cross the
connection, so the remote guard cannot see it and starts a session of its own.

Zellij itself only refuses the pathological case — attaching a session to itself,
which is an infinite render loop (`src/commands.rs`). Nesting *different* sessions
is allowed, and there is no env-var guard against it. But it costs real things
here: two status bars and doubled pane frames, every plugin loaded twice
(`autolock`, `attention`, `which-key`, `zjstatus` all run again on the remote),
session accumulation on the remote with nobody pruning it, and clipboard and
mouse behaviour that has to pass through two emulators. The worst of them is
autolock: the outer one inspects the pane's foreground command, sees `ssh`, and
never triggers, while the inner one locks and unlocks on its own — two mode
machines and only one of them in the status bar you are reading.

**The recommendation is not to nest.** Multiplex at exactly one end, and for a
remote host that end is the remote one, because persistence across a dropped
connection can only live there. That means the local terminal for such a window
should not be a Zellij session — which is what `Ctrl+Shift+Y` is for: a Kitty
window that bypasses `zjshell` and gives a plain login shell. SSH from it and the
remote Zellij is the only Zellij in the stack, so every key, the mouse, the
clipboard, and the scrollback belong to it unambiguously.

The cost is that such a window has no local splitting. Open another window
instead; `confirm_os_window_close 0` makes that cheap.

`Ctrl+; d` exists for when you nest anyway.

### Starting and switching workspaces

On a personal GUI machine, `Super+T` or `Ctrl+Alt+T` opens Kitty through XFCE's
default-terminal helper. Run:

```bash
zj
```

`zj` presents a focused fzf picker containing:

- active and resurrectable Zellij sessions;
- configured zjsh projects;
- the current directory;
- every worktree belonging to the current Git repository;
- immediate children of `~/projects`.

Each selected project or worktree becomes a persistent Zellij session. Closing
Kitty detaches the client without killing the workspace. Run `zj` from any
other terminal to attach that terminal to the same workspace or choose another
one. Session resurrection restarts commands, so the standard editor-and-agents
layout is restored after a restart.

An ordinary new Kitty window is a fresh single-pane session. `Ctrl+Shift+T` and
`Ctrl+Shift+Enter` open a window at the `zj` picker instead, for attaching to an
existing project. Neither creates a second layer of Kitty tabs or panes. From
inside a session, `F10` opens the same picker without a new window.

Closing a window never prompts for confirmation (`confirm_os_window_close 0`).
Kitty's default asks when a foreground process is running, but with Zellij
owning persistence there is nothing to lose by closing.

### The Zellij gateway

Normal Zellij mode belongs to the focused application. All inherited Zellij
bindings are cleared, so Neovim, shells, TUIs, and coding agents receive their
usual keys—including Neovim/Blink's `Ctrl+Space`.

Press `Ctrl+;` to enter a sticky, Vim-shaped Zellij control mode. On the UHK,
Caps is left Ctrl, making the gateway `Caps+;`. Kitty's extended keyboard
protocol makes this modified punctuation key unambiguous. `F12` is an
ergonomic-independent fallback that also works in traditional terminals.

Control mode stays active after navigation and layout edits so several actions
can be performed without repeating the gateway. Press Space, Esc, `Ctrl+;`, or
F12 to return input to the application.

#### The function-key layer

The gateway costs two keystrokes, which is the wrong price for the dozen actions
used constantly. Those are duplicated onto **bare function keys**, in the spirit
of byobu. No modifier is ever required, and they are bound in every mode, locked
included, so they behave identically from a shell, from Neovim, and from an agent
pane. The one exception is the pass-through mode described below, which exists
precisely to be the place they are *not* bound.

They are grouped by **what the key does** rather than by byobu's numbering, which
`F4`-as-close breaks in any case: create, destroy, move, leave. Only `F2` and `F7`
still line up with byobu.

| Key | Action | Group |
|-----|--------|-------|
| `F1` | Lazygit in a large floating pane | tool |
| `F2` | New tab | create |
| `F3` | New pane, Zellij's best available split | create |
| `F4` | Close the focused pane | destroy |
| `F5` | Previous tab | move |
| `F6` | Next tab | move |
| `F7` | Detach, leaving the session running; closes the window, ends an SSH connection | leave |
| `F8` | Quit: end this session, leaving it resurrectable | leave |
| `F9` | Jump to a tab by name | tool |
| `F10` | Leap between projects: jump to any session by name | tool |
| `F11` | Agent picker | |
| `F12` | Control-mode gateway | escape |

Two costs. `F4` closes a pane with no confirmation, and it borrows `Alt+F4`'s
meaning from the desktop precisely because it is easy to hit. And applications inside
Zellij no longer see `F1`-`F11`, which matters for htop and Midnight Commander;
both have letter equivalents, and `Ctrl+; o a` hands the whole layer back for the
rare TUI that genuinely needs function keys (`Ctrl+; o A` restores it).

#### What `F4` actually does

`F4` is one action — `CloseFocus`, close the focused pane — but it is worth
knowing that it cascades, because the result looks like three different keys:

| Focused pane is… | What you see |
|------------------|--------------|
| one of several in a tab | the pane closes |
| the last pane in its tab | the pane **and the tab** close |
| the last pane in the last tab | the session ends, and the window closes with it |

Nothing is conditional in the binding; the depth is. Two things hide which depth
you are at. Fullscreen (`Ctrl+; z`) conceals that a tab holds four panes, and `Ctrl+h` /
`Ctrl+l` are `MoveFocusOrTab`, which at a tab edge crosses silently into the next
tab — so the pane `F4` closes is not always in the tab you think you are in.

`Ctrl+; x` is the same action spelled out, and `Ctrl+; X` closes the whole tab
deliberately rather than by cascade.

#### Pass-through, for a nested Zellij

`Ctrl+; d` descends: Zellij stops intercepting and every key, function keys
included, goes to whatever is inside the pane. `F12` comes back up. The status bar
shows a mauve `PASS` while this is on, because it is the one mode where the keys
you press are not going to the Zellij in front of you.

This is for SSHing into a host that runs its own Zellij. It is **not** the
recommended way to work — see [Two multiplexers](#two-multiplexers) — but nesting
happens, and without this the outer Zellij eats every function key before the
inner one ever sees it.

Locked mode cannot do this job, which is worth recording because the config
claimed otherwise for a while. Locked stops *mode* keys, but `F1`-`F11` come from
a `shared` block, and Zellij parses a bare `shared` block as `shared_except` with
an empty exclusion list, applying it to every input mode — Locked included
(`zellij-utils/src/kdl/mod.rs`). A locked Zellij still swallows every function
key. Zellij has no "forward everything" mode, so one of its input modes has to be
emptied out to become one; `tmux` is the only mode this config never otherwise
uses, which is why the mode is internally called that and labelled `PASS`.

The one key that cannot be forwarded is the one that gets you back, so `F12` stays
with the outer Zellij and the inner one is driven with `Ctrl+;`.

#### The status bar

The bottom bar is `zjstatus`, not Zellij's built-in `status-bar`, because the
built-in one cannot show this keymap. It renders a fixed vocabulary of mode-switch
hints introspected from the config, so `keybinds clear-defaults=true` leaves it
nearly empty — in Normal mode only `Ctrl+;` matches — and direct action bindings
such as `F2` → `NewTab` are outside its vocabulary altogether. It has no way to
express "F2 makes a tab".

So the function-key legend is written by hand in
`.chezmoitemplates/zellij-status-bar.kdl` and **must be updated whenever a
function key changes**. It is a chezmoi template partial because zjstatus can only
be configured where it is instantiated — in a layout file, not `config.kdl` — and
both `simple.kdl` and `workspace.kdl` need it without keeping two copies that
drift. The bar occupies one line where the built-in took two, so it is cheaper
than what it replaces; on a narrow window the centre legend truncates first.

Tabs deliberately stay on `zellij:tab-bar` at the top rather than folding into
zjstatus's `{tabs}`: it already renders the `⏳`/`✅` that `zellij-attention`
writes into tab names, and keeping tabs out of the bottom bar means many tabs
never squeeze out the legend.

The modal layer is covered instead by `zj-which-key`, which reads the real
keybinds and so cannot fall out of date. With `auto_show`, entering the `Ctrl+;`
layer and pausing 0.4s lists what is available; `Ctrl+; ?` opens the full
searchable browser.

#### Cycling versus selecting

Three levels, three shapes of movement, chosen so nothing is merely a duplicate:

| Level | Cycle | Select by name |
|-------|-------|----------------|
| Pane | `Ctrl+,` / `Ctrl+.`, or `Ctrl+hjkl` directionally | `Ctrl+; p` |
| Tab | `F5` / `F6` | `F9` |
| Session | — | `F10` (leap), `Ctrl+; w` (`zj`, also creates), or `Ctrl+; W` |

`Ctrl+,`/`Ctrl+.` deliberately cycle **panes** rather than tabs. Tabs have
`F5`/`F6` and a name jump, whereas nothing cycled panes once detach took a key.

They are not `Ctrl+Tab`, which would be the obvious choice and does not work.
Zellij accepts a `bind "Ctrl Tab"` — its parser is strict and rejects an invalid
key name — but never fires it: `Tab` is ASCII `0x09`, indistinguishable from
`Ctrl+I` in legacy encoding, and Zellij's handling of modified special keys is
incomplete even with the Kitty protocol enabled (compare
[zellij#3852](https://github.com/zellij-org/zellij/issues/3852), where
`Ctrl+Backspace` collapses to `Ctrl+H`). `Ctrl` with punctuation is the same class
as `Ctrl+;`, which this config already depends on, so it resolves for the same
reason. The `Ctrl+Tab` pair is kept bound as an alias in case a later Zellij
delivers it.

Selection is the `zellij-leap` plugin: type characters occurring in the name, the
candidate list filters live, and it jumps the moment one candidate remains, so
distinct names cost one keystroke. This is what makes many tabs across many
projects practical, since cycling stops scaling at about four. Floating panes lost
their bare key to `F9` and keep their toggle at `Ctrl+; f`.

Minimising a pane is `stacked_resize`, which has no byobu equivalent and stays in
resize mode: `Ctrl+; r` then `=` past a neighbour's minimum collapses that
neighbour to a single title line rather than refusing, and `-` pulls it back out.
A tab therefore holds far more panes than it has room for, with the inactive ones
reduced to a list of titles.

#### Seamless Ctrl+hjkl

`Ctrl+h/j/k/l` moves between panes, and across tabs at the left and right edges.
It is the one context-sensitive layer, and arbitrating it is the *sole* remaining
job of the `zellij-autolock` plugin: it watches the command running in the focused
pane and locks Zellij for the applications listed in `triggers`, which therefore
receive `Ctrl+hjkl` themselves. On the Neovim side `zellij-nav.nvim` moves between
splits and only crosses into the neighbouring Zellij pane once the cursor is
already at the editor's edge, so one set of keys covers both. Inside fzf,
`Ctrl+j`/`Ctrl+k` stay list movement.

The trigger list is deliberately short — `nvim|vim|hx|fzf`. Locking also prevents
`Ctrl+hjkl` moving focus *out* of a pane, so pagers, htop, and Lazygit are
excluded: none of them want those keys, and all are easier to leave without the
lock. The function keys are unaffected either way, being bound in `shared`.

Two consequences worth knowing. A plain shell pane loses `Ctrl+h` as a synonym
for Backspace — the Backspace key itself is unaffected. And autolock reassesses
roughly 0.3s after the foreground process changes, so an immediate keystroke
after launching a TUI can land in the wrong layer; `Ctrl+; o a` suspends autolock
entirely if it ever gets in the way.

#### Waiting-agent indicators

`zellij-attention` renames a tab with `⏳` when a pane in it is waiting for input
and `✅` when a long task finishes, which is what makes several projects
watchable from one screen. Claude Code drives it through `Notification` and
`Stop` hooks in `private_dot_claude/settings.json`; the hooks are no-ops outside
Zellij. Codex and OpenCode have no equivalent hook, so their panes stay silent.

Both hooks redirect stdin from `/dev/null`, which is load-bearing rather than
tidiness. `zellij pipe` reads its payload from stdin when none is given on the
command line, and a *non-empty* payload makes the CLI call block until a plugin
releases it — which `zellij-attention` never does, since the pipe name carries
the whole message. Claude Code writes the hook's JSON event to stdin, so without
the redirect every hook inherited that JSON as a payload and hung until the hook
timeout (~60s per turn). With it, the call returns in ~20ms.

Both plugins request permissions the first time a session loads them. Accept the
prompt once and the grant is cached.

#### Main control mode

All entries below follow `Ctrl+;` (or F12):

| Key | Action |
|-----|--------|
| `h/j/k/l` | Focus pane left/down/up/right |
| `H/J/K/L` | Move the focused pane left/down/up/right |
| `n` | Create a pane using Zellij's best available split |
| `s` / `v` | Create a pane below / to the right |
| `S` | Create a pane stacked on the focused one |
| `x` | Close the focused pane |
| `z` | Toggle focused-pane fullscreen |
| `f` | Show or hide floating panes |
| `e` | Float or embed the focused pane |
| `i` | Pin or unpin the focused pane |
| `c` | Rename the focused pane |
| `p` | Jump to a pane in this tab by name |
| `?` | Searchable keybinding browser |
| `]` | Select the next swap layout |
| `t` / `r` / `m` / `[` | Enter tab / resize / move / scroll mode |
| `a` | Open the agent picker in a new pane |
| `b` | Open a disposable floating shell |
| `g` | Open Lazygit in a large floating pane |
| `w` | Open the focused workspace picker |
| `W` | Open Zellij's full session manager |
| `o` | Enter session-operations mode |
| `q` | Lock Zellij for pass-through; F12 unlocks |

Pane navigation, creation, movement, closing, and layout changes stay modal.
Interactive tools (`a`, `b`, `g`, `w`, and `W`) return to Normal mode
automatically so they can immediately receive input.

#### Tab mode

Enter with `Ctrl+; t`.

| Key | Action |
|-----|--------|
| `h` or `k` | Previous tab |
| `j` or `l` | Next tab |
| `H` / `L` | Move the current tab left / right |
| `1` … `9` | Jump directly to a numbered tab |
| `n` / `x` | Create / close a tab |
| `w` | Create a tab from the Neovim/agents workspace layout |
| `r` | Rename the tab |
| `s` | Toggle synchronized input for the tab |
| `b` | Break the focused pane into a new tab |

#### Resize and move modes

Enter resize mode with `Ctrl+; r`. Lowercase `h/j/k/l` increases space at the
corresponding edge; uppercase decreases it. `+` and `-` resize without choosing
an edge.

Enter move mode with `Ctrl+; m`. Use `h/j/k/l` to move spatially, `n` or Tab to
rotate forward, and `p` to rotate backward. Moving a pane is also available
directly from main control mode with uppercase motions.

#### Scroll and search modes

Enter with `Ctrl+; [`.

| Key | Action |
|-----|--------|
| `j/k` | Scroll down/up |
| `d/u` | Half-page down/up |
| `Ctrl+F` / `Ctrl+B` | Full page down/up |
| `g/G` | Top/bottom |
| `/` | Search |
| `e` | Open scrollback in Neovim |
| `n/N` | Next/previous result after starting a search |
| `c/w/o` | Toggle case sensitivity / wrapping / whole-word search |

Leaving scroll or search mode returns to the bottom before handing input back
to the application.

#### Session operations and lock mode

Enter with `Ctrl+; o`.

| Key | Action |
|-----|--------|
| `w` | Session manager: attach, resurrect, rename, detach, or delete |
| `d` | Detach this client |
| `c` / `p` / `l` | Configuration / plugin / layout manager |
| `q` | Enter locked mode |
| `a` / `A` | Suspend autolock and hand the application the function keys / restore it |
| `x` | Quit: end this session, leaving it resurrectable |
| `X` | End this session **and** delete its record, via `zjkill` |

**Three ways to leave, and only one of them shrinks anything.** This is the
distinction that matters, because two of the three look identical on screen — the
window closes either way.

| | Keys | Processes | In `list-sessions` | Use when |
|---|------|-----------|--------------------|----------|
| **Detach** | `F7`, `Ctrl+; o d`, closing the window | keep running | listed, live | you are coming back to *this* work |
| **Quit** | `F8`, `Ctrl+; o x`, `exit` in the last pane | killed | listed, `EXITED` | done, but you may want to resurrect it |
| **Delete** | `Ctrl+; o X`, `zjclean` | killed | gone | the project is genuinely finished |

Detach is a bookmark, not a close. `on_force_close "detach"` means closing the
Kitty window is a detach too, and `session_serialization` restores the layout and
commands on the way back in. Since every window is its own session, closing
windows is a bookmark-per-window machine: this is why sessions accumulate, and
why the status bar now shows a count once the list gets long.

Quit still leaves a resurrectable record behind — that is the point of
serialization, and it is why `Ctrl+; o X` exists as the "actually finished"
version. `Ctrl+; o q` is *lock*, not quit, so the obvious guess deliberately does
nothing destructive.

`F7` and `F8` are deliberately neighbours: leave for now, leave for good. Quit is
the one that gets the bare key precisely *because* it is recoverable — reaching
for `F7` and hitting `F8` costs the running processes but not the session, which
`zellij attach` brings back. `zjkill` deletes the record as well and therefore
stays three keystrokes deep, on the same reasoning that kept Quit itself away from
`q`. `exit` in the last pane is the same level as `F8`, since the `EXIT` trap ends
the session rather than detaching from it.

`F10` switches to another project without leaving this one, and the project just
left is one of its candidates, so it is also how you get back.

To clean up in bulk, `zjclean --dead` deletes every `EXITED` session without
asking and leaves live ones alone; `zjclean --stale [N]` restricts that to records
older than N days, which is the version to automate. `zjclean` with no arguments
is the interactive pass for live sessions, showing pane counts and tab names so
one holding four tabs and a waiting agent is distinguishable from an abandoned
one.

`zjclean --dead` deletes sessions one at a time rather than calling
`zellij delete-all-sessions`, which is deliberate: that command accepts a
`--force` that also kills *live* sessions, including the one you are sitting in,
and a bulk verb one typo away from that is a poor habit to build. Naming each
session as it goes also leaves a record of what was removed.

#### What "attach to resurrect" means

A session in `leap` or `list-sessions` marked `EXITED - attach to resurrect` is
one whose **server process is gone** but whose serialized layout survived. On disk
that is exactly the difference, and it is visible:

| | `session-layout.kdl` | `session-metadata.kdl` | live socket |
|---|---|---|---|
| live | ✓ | ✓ | ✓ |
| `EXITED` | ✓ | — | — |
| deleted | — | — | — |

The layout is written periodically — roughly a minute after a session gets real
content, which is why a session created and killed inside a few seconds vanishes
without a trace rather than becoming resurrectable.

Attaching to one **restores the shape and restarts the commands**: the tabs, the
pane geometry, the working directories, and Neovim and the agents running again.
Because `serialize_pane_viewport` is on it also restores the scrollback, so a
resurrected pane comes back showing what was on it rather than blank. What cannot
come back is anything that lived *inside* those processes — unsaved buffers, an
in-flight command, an agent's context. That is what `claude --resume` is for.

A screen full of resurrectable sessions means every server died at once —
normally a reboot. This is not a failure mode; **it is the restore path**. A
shutdown is not a detach and cannot be made into one: detaching leaves the server
running, and a shutdown kills it, so there is nothing left to detach from.
Serialization is the only thing that crosses a reboot.

Which is why the two prune modes are not interchangeable:

- `zjclean --dead` clears **everything** exited. Right for a deliberate sweep,
  wrong immediately after a reboot, when those records are your desk as you left
  it.
- `zjclean --stale [N]` clears only what was last alive more than N days ago
  (default 7). Recent restore points survive a reboot; the archaeology goes. This
  is the one that is safe to run unattended.

Age comes from the layout file's mtime rather than the "Created" time Zellij
reports, because creation is when a session *started* — for a long-lived workspace
that can be weeks before it died — while the layout is rewritten on every
serialization pass, so its mtime is the last moment the session was alive.

Normal mode already passes everything except the gateway and F12. Locked mode is
for an application that specifically needs `Ctrl+;`: it passes that key through as
well, and reserves only F12 for unlocking. It does **not** pass the function keys
through — `Ctrl+; d` is the mode that does.

### Agents, Git, and worktrees

A session opened from `zj` or `Ctrl+; t w` starts Neovim immediately, while its
Codex and Claude panes are suspended to keep many open workspaces cheap. Focus a
suspended pane and press Enter to start it. A plain session — any new Kitty
window — has none of this and stays a single pane until asked otherwise.

`F11` or `Ctrl+; a` runs `zja`, an fzf picker for:

- new or resumed Codex with unrestricted permissions;
- new or resumed Claude with unrestricted permissions;
- new or continued OpenCode with automatic permissions;
- a plain shell.

Multiple agents in one Zellij workspace share one working tree. That is useful
for coordinated roles such as implementation plus review, but independent
agents should edit separate Git worktrees:

```bash
git worktree add -b feature ../project-feature
cd ../project-feature
zj
```

The workspace picker discovers all worktrees for the current repository, so
each agent's worktree remains directly switchable. `F1` opens Lazygit for the
current workspace; ordinary Git and stacked-PR aliases remain available in the
shell.

### Kitty and UHK integration

Kitty is installed on `personal`/`gui` profiles as the `kitty-bin` pixi global
env from the [blooop channel](https://prefix.dev/channels/blooop), which
repackages upstream's current Linux binary. It is named `kitty-bin` rather than
`kitty` because conda-forge ships a stale 0.23.1 source build under that name.
Its configuration uses JetBrainsMono Nerd Font Mono, disables the audio bell,
keeps remote control disabled, leaves `Ctrl+;` and `F1`-`F12` untouched for
Zellij, and sets `shell` to `zjshell` so a window is a Zellij session on open.

`Super+T` and `Ctrl+Alt+T` run `exo-open --launch TerminalEmulator`, which reads
`~/.config/xfce4/helpers.rc`. That points at a **custom** helper shipped in
`private_dot_local/private_share/xfce4/private_helpers/` naming
`~/.pixi/bin/kitty` by absolute path, rather than at the stock
`/usr/share/xfce4/helpers/kitty.desktop`. The stock helper declares
`X-XFCE-Binaries=kitty;`, and exo resolves that against the PATH of the
graphical session — which is fixed at login and never contains `~/.pixi/bin`,
since that entry is added by the shell rc files. Exo therefore concludes the
helper is unavailable and *silently rewrites* `helpers.rc` with the
`TerminalEmulator` line deleted, so Super+T falls back to `xfce4-terminal` and
`chezmoi status` starts reporting drift on `helpers.rc`. Any future pixi-installed
GUI helper needs the same absolute-path treatment.

`xterm-kitty` terminfo is installed into `~/.terminfo` because Kitty only exposes
it through the `TERMINFO` variable pointing inside its own install, and neither
Ubuntu's nor conda-forge's ncurses ships the entry. Without it, pixi-installed
TUIs (htop, btop, isd, broot, lazygit, lazydocker) fail with
`cannot initialize terminal type ($TERM="xterm-kitty")` when run directly in a
Kitty window — Zellij normally hides this by setting its own `TERM`. It is
installed twice on purpose: Ubuntu's ncurses looks in `x/`, while conda-forge's
uses hex-named directories (`78/` for `x`), and neither reads the other's layout.
To refresh both after a Kitty upgrade changes the entry:

```bash
KT=~/.pixi/envs/kitty-bin/lib/kitty-bin/lib/kitty/terminfo
cp "$KT/x/xterm-kitty" ~/.terminfo/x/xterm-kitty
cp "$KT/x/xterm-kitty" ~/.terminfo/78/xterm-kitty
chezmoi add ~/.terminfo/x/xterm-kitty ~/.terminfo/78/xterm-kitty
``` Terminator remains installed and can still use the F12 gateway, but it
cannot reliably distinguish `Ctrl+;` from unmodified punctuation.

The UHK Caps key previously activated the mouse layer. It is now a basic left
Ctrl modifier on the base layer of all six saved layouts:

- Colemak for Mac and PC;
- Dvorak for Mac and PC;
- QWERTY for Mac and PC.

The unused mouse layers remain present in the UHK configuration, making the
change easy to reverse. To re-upload the managed configuration to a connected
keyboard without opening the GUI:

```bash
xvfb-run -a uhk-agent --restore-user-configuration
```

### Managed files and reproduction

| Source file | Responsibility |
|-------------|----------------|
| `dot_config/kitty/kitty.conf.tmpl` | Kitty font, UI, `shell` = `zjshell`, and new-OS-window mappings |
| `private_dot_local/private_bin/executable_zjshell` | Kitty's shell: opens straight into Zellij, falls back to bash |
| `private_dot_local/private_bin/executable_zjclean` | Prunes accumulated sessions with an fzf picker; `--dead` purges exited ones, `--stale N` only old ones |
| `private_dot_local/private_bin/executable_zjkill` | Ends the current session and deletes its record |
| `private_dot_local/private_bin/executable_zjcount` | Session-count widget for the status bar; silent below its threshold |
| `private_dot_bash_env` | Attaches SSH logins to the persistent `main` session (`# === Zellij on SSH ===`) |
| `dot_pixi/manifests/pixi-global.toml.tmpl` | Installs Kitty as the `kitty-bin` pixi global env |
| `run_onchange_install-kitty-desktop.sh.tmpl` | Kitty desktop-menu entry (pixi does not create one) |
| `dot_terminfo/x/xterm-kitty`, `dot_terminfo/78/xterm-kitty` | `xterm-kitty` terminfo for non-Kitty ncurses builds (applied on **all** profiles, not just `gui` — `$TERM` follows you over SSH) |
| `dot_config/xfce4/helpers.rc` | Makes Kitty XFCE's default terminal |
| `dot_config/zellij/config.kdl.tmpl` | Modal keymap, function-key layer, floating tools, plugin registration |
| `dot_config/zellij/layouts/workspace.kdl.tmpl` | Neovim/Codex/Claude/terms workspace |
| `dot_config/zellij/layouts/simple.kdl.tmpl` | Default layout: one bare pane plus the UI |
| `.chezmoitemplates/zellij-status-bar.kdl` | zjstatus bar shared by both layouts; **holds the hand-written F-key legend** |
| `.chezmoiexternal.toml` | Downloads the `zellij-autolock`, `zellij-attention`, `zellij-leap`, `zjstatus`, and `zj-which-key` WASM plugins |
| `dot_config/nvim/lua/plugins/zellij.lua` | `zellij-nav.nvim`, the Neovim half of `Ctrl+hjkl` |
| `private_dot_claude/settings.json` | Claude hooks that drive the waiting-agent tab icons |
| `dot_config/zjsh/config.kdl.tmpl` | Workspace resurrection behavior |
| `private_dot_local/private_bin/executable_zj` | Workspace and worktree picker |
| `private_dot_local/private_bin/executable_zja` | Coding-agent picker |
| `dot_config/private_uhk-agent/UserConfiguration.json` | UHK layouts and Caps-as-Ctrl |

On another personal machine, the normal install or `chezmoi update` reproduces
the managed configuration. Useful verification commands are:

```bash
zellij --config ~/.config/zellij/config.kdl setup --check
kitty +runpy 'import os, kitty.config; bad=[]; kitty.config.load_config(os.path.expanduser("~/.config/kitty/kitty.conf"), accumulate_bad_lines=bad); print(bad)'
jq empty ~/.config/uhk-agent/UserConfiguration.json
```

If `Ctrl+;` does not open control mode, confirm the terminal is Kitty and start
a fresh Zellij client; F12 remains available. If input appears stuck in a
Zellij mode, press Space or Esc. If locked mode is active, press F12.

## Cheatsheet

### Navigation
| Alias | Command |
|-------|---------|
| `..` | `cd ..` |
| `...` | `cd ../..` |
| `....` | `cd ../../..` |
| `br` | broot: browse with type-to-filter; `→`/Enter goes into a dir, `←` goes up. Press `alt-t` (or type `:t`) to cd the terminal to the selected dir and quit. Default search is token-based: type comma-separated fragments in any order, e.g. `kin,ros` matches `kinisi_ros`. Prefix `f/` for fuzzy, `\|`/`&`/`!` for or/and/not |
| `z <name>` | zoxide: jump to most-used dir matching name |
| `Alt+C` | fzf: fuzzy-pick a subdirectory and cd into it |
| `Ctrl+T` | fzf: fuzzy-pick a file and paste its path at the prompt |

### Terminal Workspaces
Quick reference for the full [terminal vibe-coding workflow](#terminal-vibe-coding-workflow):

Bare function keys are the one-keystroke hot path; they work in
every mode, including from inside Neovim and agent panes:

| Key | Purpose |
|-------|---------|
| `Ctrl+h/j/k/l` | Move focus between panes, and across tabs at the left/right edge; passes through to Neovim, Lazygit, fzf, and pagers |
| `Ctrl+,` / `Ctrl+.` | Previous / next pane |
| `F1` | Floating Lazygit |
| `F2` / `F3` | New tab / new pane |
| `F4` | Close the focused pane, no confirmation; cascades to the tab, then the session, when it is the last one |
| `F5` / `F6` | Previous tab / next tab |
| `F7` | Detach: closes the window, ends an SSH connection, session stays |
| `F8` | Quit: end this session; resurrectable, so a mis-hit for `F7` is recoverable |
| `F9` | Jump to a tab by name |
| `F10` / `F11` | Leap between projects / agent picker |
| `F12` | Control-mode gateway |
| tab shows `⏳` / `✅` | A Claude pane in that tab wants input / has finished |
| bar shows `N sessions, M dead` | The session list has grown past the threshold — run `zjclean` |

Applications inside Zellij do not see `F1`-`F11`; `Ctrl+; d` hands them back
(`F12` returns), and `Ctrl+; o a` does the same while also suspending autolock
for a long-lived TUI (`Ctrl+; o A` restores it). Locked mode does *not* pass
function keys through — a bare `shared` block covers every mode, Locked included.

**Leaving a session** — three levels, and only the last shrinks the list:

| | Keys | Processes | Record |
|---|------|-----------|--------|
| Detach | `F7`, `Ctrl+; o d`, closing the window | keep running | stays, live |
| Quit | `F8`, `Ctrl+; o x`, `exit` in the last pane | killed | stays, `EXITED` |
| Delete | `Ctrl+; o X`, `zjclean` | killed | gone |

The full modal layer remains available for everything else:

| Command / key | Purpose |
|-------|---------|
| `zj` / `Ctrl+; w` | Create or open a workspace from a project dir or worktree, without the noisy full zoxide history |
| `zjclean` | Prune accumulated sessions; shows pane and tab counts, Tab marks several |
| `zjclean --dead` | Delete every `EXITED` session unattended; live ones untouched |
| `zjclean --stale [N]` | Delete `EXITED` sessions last serialized over N days ago (default 7); the one that is safe to automate |
| `zjclean --dead` | Delete every `EXITED` session, no prompt; live ones untouched. Also sweeps empty session dirs |
| `zjkill` / `Ctrl+; o X` | End this session *and* delete its record, for a project that is finished |
| `exit` / `Ctrl+D` | Close the pane; in the last pane of a session it ends the session and closes the window |
| `Ctrl+; W` | Open the full session manager (resurrect, rename, detach, delete) |
| `Ctrl+; g` | Open Lazygit in a floating pane |
| `Ctrl+; a` | Pick and open another Codex, Claude, OpenCode, or shell pane (agent choices are labelled unrestricted) |
| `Ctrl+; b` | Open a disposable floating shell |
| `Ctrl+; n/s/v/S` | Create an automatic/down/right/stacked pane; control mode stays active |
| `Ctrl+; x` / `Ctrl+; X` | Close the focused pane / the whole tab; control mode stays active |
| `Ctrl+; d` | Pass-through: hand every key, function keys included, to a nested Zellij. `F12` returns |
| `Ctrl+; h/j/k/l` | Move focus between panes |
| `Ctrl+; H/J/K/L` | Move the focused pane |
| `Ctrl+; z/f/e` | Fullscreen / show floating panes / float the focused pane |
| `Ctrl+; p` | Jump to a pane in this tab by name |
| `Ctrl+; ?` | Searchable keybinding browser; the popup also auto-shows on entering the layer |
| `Ctrl+; t`, then `1` … `9` | Enter tab mode and jump directly to a tab (`1` is work, `2` is terms) |
| `Ctrl+; t`, then `n/x/h/l/H/L` | Create/close/select/move tabs |
| `Ctrl+; t`, then `w` | Open a tab running the Neovim/agents workspace layout |
| `Ctrl+; r`, then `=`/`-` | Grow/shrink; growing minimises neighbours into a title-line stack |
| `Ctrl+; r` / `m` / `[` | Enter resize / move / Vim-style scroll mode |
| `Ctrl+; o` | Session operations; `w` manager, `d` detach, `x` quit, `X` quit and delete, `q` lock (F12 unlocks) |
| `Super+T` / `Ctrl+Alt+T` | Open Kitty from the desktop via XFCE's TerminalEmulator helper (`gui` profiles) |
| new Kitty window | Already a fresh single-pane Zellij session (`shell` is `zjshell`) |
| `ssh <host>` | Attaches to a persistent `main-<client>` session there; `ZELLIJ_AUTOSTART=0` opts out |
| `Ctrl+Shift+T` / `Ctrl+Shift+Enter` | Open another Kitty OS window at the Zellij workspace picker |
| `Ctrl+Shift+Y` | Open a Kitty window with a **plain** login shell, no Zellij — SSH from here so the remote Zellij is the only one |
| mouse wheel | Scroll the focused pane without entering a mode |

The focused pane's frame is **magenta** in normal mode and **cyan** while the
`Ctrl+;` layer is active; every other pane keeps a plain white frame. Zellij will
not let a theme colour unfocused frames — they always use the terminal's default
foreground — so the focused pane has to win on hue, which is why the bundled
`blade-runner` theme is re-declared as `blade-runner-focus` in
`dot_config/zellij/config.kdl.tmpl` with just those two colours changed.

Use a separate Git worktree and Zellij workspace for agents that may edit in
parallel. Multiple agents inside one workspace share one working tree and are
best used for coordinated roles such as implementation plus review.

### File Listing
| Alias | Command |
|-------|---------|
| `ll` | `ls -alF` |
| `la` | `ls -A` |
| `l` | `ls -CF` |

### Git
| Alias | Command |
|-------|---------|
| `gs` | `git status` |
| `gp` | `git push` |
| `lg` | `lazygit` |
| `git diff` | side-by-side, line-numbered output via delta |
| `gg` | `glo --all` — fuzzy all-branches commit graph (forgit log) |
| `ga` | forgit: interactive add |
| `gd` | forgit: interactive diff |
| `glo` | forgit: interactive log |
| `gcb` | forgit: checkout branch |
| `gss` | forgit: stash show |
| `pushf` | `git push --force-with-lease` (safe force-push for restacks) |

### Pull Requests
`/pr` takes the current branch to an open PR and stops there. It merges the base branch (resolving conflicts), commits outstanding work, lints **only the diff range**, self-reviews once, pushes, and prints the URL. It does not wait on CI unless you ask it to.

| Command | Purpose |
|-------|---------|
| `/pr` | Fast path: sync, lint, one self-review pass, push, create the PR, print the URL. Returns while CI is still pending. |
| `/pr --watch` | Same, then babysit: watch checks, fix red CI, re-merge on conflicts, answer review comments (resolving bot threads, never human ones). Max 5 rounds. |
| `/pr --no-review` | Skip the self-review pass. Third-party comment handling still runs under `--watch`. |

A trailing argument is a base-branch override (`/pr --watch release/2.1`). Reach for `--watch` when you're walking away from a PR you expect to go green; leave it off when you just want the PR open.

### Stacked PRs
A stack is a chain of branches/PRs from `main` up to your top branch. The agent commits each change onto the branch it belongs to; `/stack sync` does the bookkeeping. GitHub PRs are the source of truth for topology. Two commands:

| Command | Purpose |
|-------|---------|
| `/stack create <N>` | Slice the current branch into an N-PR stack (N−1 interior branches + the original kept as top). Shows the proposed split first. |
| `/stack sync` | Idempotent bookkeeping from any state: restack each branch onto its parent (bottom→top, onto latest `main`), reconcile/create/retarget PRs, prune merged branches, `push --force-with-lease`. |

Commit each change onto whichever branch it belongs to, then run `/stack sync`; descendants restack and every PR updates. `gh pr checkout <n>` jumps to any PR's branch natively.

### Utilities
| Alias | Command |
|-------|---------|
| `grep` | `grep --color=auto` |
| `mkdir` | `mkdir -pv` |
| `df` / `du` / `free` | `-h` (human-readable sizes) |
| `rm` / `cp` / `mv` | `-i` (prompt before overwrite) |

### NVIDIA and Kernel Upgrades (nvidia-upgrades)
Gated on `host`. Stops unattended-upgrades from touching the NVIDIA driver or the kernel, so neither ever changes under a running session. Ubuntu ships both in `<codename>-security`, an allowed origin, and when the driver's userspace libs are swapped while the old kernel module is still loaded, CUDA and GL die with `Failed to initialize NVML: Driver/library version mismatch` until you reboot. A silent kernel upgrade likewise leaves a reboot owed.

It works by writing `Unattended-Upgrade::Package-Blacklist` drop-ins to `/etc/apt/apt.conf.d` (`52unattended-upgrades-nvidia`, `53unattended-upgrades-kernel`). That key is read **only** by the `unattended-upgrade` script — apt and dpkg ignore it — so `sudo apt dist-upgrade` still upgrades kernel and driver together in one consistent transaction. This is deliberately not `apt-mark hold`, which *would* block manual upgrades too. Everything else (browsers, Docker, CLI tools) keeps updating automatically.

Run it without `sudo`; it re-execs itself under sudo.

| Command | Action |
|---------|--------|
| `nvidia-upgrades hold` | Write both drop-ins, then verify: dumps the effective blacklist and dry-runs `unattended-upgrade` to confirm it agrees. Idempotent (default subcommand) |
| `nvidia-upgrades status` | Hold state per drop-in, loaded kernel module vs installed userspace version (flags a mismatch needing a reboot), pending held upgrades, and any reboot already owed |
| `nvidia-upgrades upgrade` | Convenience wrapper: `apt update && apt dist-upgrade`, then the `status` report |
| `nvidia-upgrades unhold` | Remove both drop-ins and return to automatic upgrades |

The trade: kernel and driver security updates now wait for you, so run `sudo apt dist-upgrade` every few weeks.

### Claude CLI
| Alias | Command |
|-------|---------|
| `cld` | `claude --dangerously-skip-permissions` |
| `cldr` | `claude --dangerously-skip-permissions --resume` |

### Codex CLI
| Alias | Command |
|-------|---------|
| `cdy` | `codex --yolo` |

### VS Code Container Attach (vs)
Attaches VS Code windows to existing dev containers, local or on another machine over SSH — no F1 menu, no manual ssh. Candidates come from VS Code's own history (every container you've attached to before, with its workspace path) plus any currently running containers; live status is checked with `docker ps` locally and over ssh. Stopped containers are started automatically before attaching. The picker lists running containers first, then stopped ones, each block ordered by most recent use — the later of when VS Code last opened the workspace and when you last launched it from `vs` (tracked in `~/.local/state/vs/launches.json`). In the picker, `ctrl-x` *forgets* the selected entries — it deletes VS Code's `workspaceStorage` record so they stop cluttering the list, leaving the container and its data untouched — then reopens the picker so you can prune several in a row. Container *creation* is `dl`'s job; `vs` only re-attaches.

| Command | Purpose |
|-------|---------|
| `vs` | fzf picker — `TAB` to multi-select, `ctrl-x` to forget selected entries, `Enter` to launch all selected |
| `vs <token> ...` | batch launch every workspace whose `container@host` matches a token (e.g. `vs k1ci k2ci`); exact container names win over substring matches |
| `vs -a [token ...]` | launch everything (optionally filtered) without the picker |
| `vs -l` | list known workspaces with live container status |
| `vs -H <host>` | also scan an ssh host with no attach history (repeatable) |
| `vs -n ...` | dry-run — print the `docker start` / `code --folder-uri` commands only |
| `vst [token]` | terminal sibling of `vs`: pick one local/remote container and open its workspace with ags + the Neovim/Codex/Claude Zellij layout |
| `vst -l`, `vst -H <host>`, `vst -n [token]` | list, scan an extra host, or dry-run using the same inventory as `vs` |

### Isolated Shell (ags)
| Command | Purpose |
|-------|---------|
| `ags` | Enter an isolated shell with full dotfiles (bootstraps into `~/.local/share/ags` on first run, never touches the real HOME) |
| `ags <container>` | Same, inside a running docker container — injects itself and bootstraps there |
| `ags [<container>] -- <command>` | Run one command inside the isolated environment (used by `vst`) |
| `ags update` | Re-run the dotfiles install in the isolated environment |
| `ags uninstall` | Remove ags and its cached environment |

Install on a remote machine or container (one time, then just type `ags` in any later login shell):

```bash
mkdir -p ~/.local/bin && curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/private_dot_local/private_bin/executable_ags -o ~/.local/bin/ags && chmod +x ~/.local/bin/ags && ~/.local/bin/ags
```

Safe on shared machines (robots, lab PCs): the entire footprint is `~/.local/bin/ags` plus the `~/.local/share/ags` cache — no rc files or other shared state are modified, and ags installs exclude personal info (git identity is omitted, so commits made by others on the account can't impersonate you; set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` per-session when you need to commit). The dotfiles repo is public and contains no credentials.

For containers you launch yourself (rocker with user mapping), mount the host cache to skip the bootstrap entirely: `-v ~/.local/share/ags:/home/$USER/.local/share/ags`. Requires matching username/home path and a glibc-based image.

## Compatibility

This dotfiles repository is compatible with:

- **DevPod & DevContainers** - Automated or manual setup in development containers
- **Traditional Chezmoi workflow** - Manual installation and management
- **Any Unix-like system** - Linux, macOS, WSL

## Managing Changes

After initial setup, use Chezmoi commands to manage your configuration:

```bash
chezmoi update    # Pull and apply latest changes
chezmoi edit      # Edit configuration files
chezmoi apply     # Apply pending changes
```

### Machine-specific overrides

For settings you want on one machine but **not** committed to this (public) repo,
use the untracked local override files. They are sourced/included automatically
and chezmoi never manages or overwrites them, so they survive `chezmoi apply` and `/sync`:

- `~/.bash_env.local` — sourced at the end of `~/.bash_env` (per-machine env vars, e.g. `WS_EXCLUDE`)
- `~/.gitconfig.local` — included from `~/.gitconfig` (per-machine git config, e.g. the `gh` credential helper)

## Troubleshooting

### Lost SSH config entries after a sync

**Symptom:** manually-added `Host` blocks disappear from `~/.ssh/config`, seemingly around the time you ran `chezmoi apply` / `/sync`.

**Cause:** not chezmoi. This repo does **not** manage `~/.ssh/config` (`chezmoi managed` lists no ssh files, and the file has never been in git history), and `chezmoi apply` never touches unmanaged files. The real culprit is **DevPod**, which rewrites `~/.ssh/config` in place every time a workspace is created, recreated, or deleted. It inserts/prunes blocks between `# DevPod Start <ws>` / `# DevPod End <ws>` markers, and when those markers get unbalanced (e.g. an orphaned `Start` with no matching `End`) a prune can delete everything down to the next marker — taking your hand-written entries with it. The chezmoi correlation is indirect: `run_once_configure-devpod.sh` and `dl`/devpod activity tend to happen right after a sync, and that's what rewrites the file.

**Fix — move your personal entries out of DevPod's blast radius.** DevPod only edits `~/.ssh/config` itself, never files it `Include`s:

```sshconfig
# ~/.ssh/config — keep this near the top (or end); leave the rest for DevPod
Include config.d/*
```

Put your own `Host` entries in `~/.ssh/config.d/personal`. DevPod keeps churning `config`; your entries live in a file it never opens.

**Hardening:**

- Delete any orphaned `# DevPod Start …` line that has no matching `# DevPod End` — those are what make a prune over-delete.
- To sync personal SSH entries across machines, manage `~/.ssh/config.d/personal` with chezmoi. This repo is **public**, so only do this with [age encryption](https://www.chezmoi.io/user-guide/encryption/age/) (`encrypted_` prefix) — the file contains internal hostnames/IPs that should not be committed in plaintext.

### `gh` is unauthenticated inside a `dl` devcontainer

**Symptom:** `gh` works on the host, but inside a container started by `dl` (e.g. `dl blooop/bencher`) it reports `Failed to log in to github.com account … The token in default is invalid.`

**Cause:** not `dl`, and not a missing mount. The devcontainers already bind-mount `~/.config/gh` into the container, but that directory only carries `hosts.yml` — and `hosts.yml` contains a token only when `gh` uses **file** credential storage. If `gh` is storing the token in the **system keyring** (`gh auth status` on the host prints `(keyring)`), the mounted `hosts.yml` has the account entry but no `oauth_token`, and the container has no secret-service to fall back to. Note that `gh auth login` and `gh auth refresh` both default to the keyring — running either **without** `--insecure-storage` silently migrates you off file storage and breaks every container, even if it worked before.

**Fix — put the token back in `hosts.yml`:**

```bash
gh auth token | gh auth login --hostname github.com --git-protocol ssh --with-token --insecure-storage
```

`gh auth status` should then report the source as `~/.config/gh/hosts.yml` rather than `(keyring)`. The existing bind mount carries it into every container; no `devcontainer.json` change is needed. Verify with `dl <workspace> "gh auth status"`.

**Hardening:** always pass `--insecure-storage` to `gh auth login` / `gh auth refresh` on a host that runs devcontainers, otherwise the next scope change re-breaks it. The tradeoff is the token at rest in a `0600` file instead of the keyring — which is the point: the whole mechanism is a read-write bind mount of that directory into containers, so the container is trusted with the credential either way.

### Uncolored `user@host` in the shell prompt

**Symptom:** the `user@host:path` prompt is plain white in Kitty, but colored in gnome-terminal or Terminator.

**Cause:** Ubuntu's stock `~/.bashrc` only enables the colored `PS1` when `TERM` matches `xterm-color` or `*-256color`. Kitty reports `TERM=xterm-kitty`, which matches neither, so the non-color branch wins. Kitty's own color support is fine — it's purely the pattern match.

**Fix:** `private_dot_bash_env` sets the colored `PS1` in a `# === Prompt ===` block, gated on `tput setaf 1` (actual color support) rather than a `TERM` pattern. `.bash_env` is sourced from `.bashrc` *after* the stock prompt block, so it overrides cleanly and covers any terminal with an unrecognized `TERM`.

**If the prompt is still uncolored after that fix:** the `tput setaf 1` guard fails when the `xterm-kitty` terminfo entry is missing, so the override never fires. Check with `ls ~/.terminfo/x/xterm-kitty` and `tput setaf 1; echo $?`. This is why `.terminfo` is *not* gated on `.gui` in `.chezmoiignore.tmpl` — Kitty runs locally, but `TERM=xterm-kitty` travels over SSH into headless `shared`/`robot`/`container` boxes that need the entry just as much.

Setting `term xterm-256color` in `kitty.conf` would also work but is not used — it costs kitty-specific escape sequences (styled underlines, graphics protocol, extended keyboard) that programs discover through terminfo.
