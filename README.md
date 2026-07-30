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
- **`host`** - git, git-lfs, openssh, curl, unzip, speedtest-go
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
Kitty OS window
└── Zellij session (one project or Git worktree)
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

Inside Kitty, `Ctrl+Shift+T` and `Ctrl+Shift+Enter` both open a new Kitty OS
window directly at the `zj` picker. They do not create a second layer of Kitty
tabs or panes.

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

#### Main control mode

All entries below follow `Ctrl+;` (or F12):

| Key | Action |
|-----|--------|
| `h/j/k/l` | Focus pane left/down/up/right |
| `H/J/K/L` | Move the focused pane left/down/up/right |
| `n` | Create a pane using Zellij's best available split |
| `s` / `v` | Create a pane below / to the right |
| `x` | Close the focused pane |
| `z` | Toggle focused-pane fullscreen |
| `f` | Show or hide floating panes |
| `e` | Float or embed the focused pane |
| `i` | Pin or unpin the focused pane |
| `c` | Rename the focused pane |
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
| `q` | Enter locked pass-through mode |

Normal mode already passes everything except the gateway and F12. Lock mode is
for an application that specifically needs `Ctrl+;`: it passes that key through
as well, and reserves only F12 for unlocking.

### Agents, Git, and worktrees

New sessions start Neovim immediately, while the default Codex and Claude panes
are suspended to keep many open workspaces cheap. Focus a suspended pane and
press Enter to start it.

`Ctrl+; a` runs `zja`, an fzf picker for:

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
each agent's worktree remains directly switchable. `Ctrl+; g` opens Lazygit for
the current workspace; ordinary Git and stacked-PR aliases remain available in
the shell.

### Kitty and UHK integration

Kitty is installed from the current upstream binary on `personal`/`gui`
profiles. Its configuration uses JetBrainsMono Nerd Font Mono, disables the
audio bell, keeps remote control disabled, and leaves `Ctrl+;` untouched for
Zellij. Terminator remains installed and can still use the F12 gateway, but it
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
| `dot_config/kitty/kitty.conf` | Kitty font, UI, and new-OS-window mappings |
| `run_once_install-kitty.sh.tmpl` | Upstream Kitty install and desktop integration |
| `dot_config/xfce4/helpers.rc` | Makes Kitty XFCE's default terminal |
| `dot_config/zellij/config.kdl` | Complete modal keymap and floating tools |
| `dot_config/zellij/layouts/workspace.kdl` | Neovim/Codex/Claude/terms workspace |
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

| Command / key | Purpose |
|-------|---------|
| `zj` / `Ctrl+; w` | Pick or switch workspace without the noisy full zoxide history |
| `Ctrl+; W` | Open the full session manager (resurrect, rename, detach, delete) |
| `Ctrl+; g` | Open Lazygit in a floating pane |
| `Ctrl+; a` | Pick and open another Codex, Claude, OpenCode, or shell pane (agent choices are labelled unrestricted) |
| `Ctrl+; b` | Open a disposable floating shell |
| `Ctrl+; n/s/v` | Create an automatic/down/right pane; control mode stays active |
| `Ctrl+; x` | Close the focused pane; control mode stays active |
| `Ctrl+; h/j/k/l` | Move focus between panes |
| `Ctrl+; H/J/K/L` | Move the focused pane |
| `Ctrl+; z/f/e` | Fullscreen / show floating panes / float the focused pane |
| `Ctrl+; t`, then `1` … `9` | Enter tab mode and jump directly to a tab (`1` is work, `2` is terms) |
| `Ctrl+; t`, then `n/x/h/l/H/L` | Create/close/select/move tabs |
| `Ctrl+; r` / `m` / `[` | Enter resize / move / Vim-style scroll mode |
| `Ctrl+; o` | Session operations; `w` manager, `d` detach, `q` lock (F12 unlocks) |
| `Ctrl+Shift+T` / `Ctrl+Shift+Enter` | Open another Kitty OS window at the Zellij workspace picker |
| mouse wheel | Scroll the focused pane without entering a mode |

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

**Cause:** Ubuntu's stock `~/.bashrc` only enables the colored `PS1` when `TERM` matches `xterm-color` or `*-256color`. Kitty reports `TERM=xterm-kitty`, which matches neither, so the non-color branch wins. Kitty's own color support and terminfo are fine — it's purely the pattern match.

**Fix:** `private_dot_bash_env` sets the colored `PS1` in a `# === Prompt ===` block, gated on `tput setaf 1` (actual color support) rather than a `TERM` pattern. `.bash_env` is sourced from `.bashrc` *after* the stock prompt block, so it overrides cleanly and covers any terminal with an unrecognized `TERM`.

Setting `term xterm-256color` in `kitty.conf` would also work but is not used — it costs kitty-specific escape sequences (styled underlines, graphics protocol, extended keyboard) that programs discover through terminfo.
