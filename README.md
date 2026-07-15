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
| `gui` | ✓ | ✗ | ✗ | ✗ | nerd fonts, uhk-agent, nvtop |
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
- **`gui`** - nvtop, uhk-agent, JetBrainsMono nerd fonts

## Git Configuration

The git configuration (included in DevContainers and Full installations) provides:

- **Useful aliases** - `com` (checkout main), `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push), `pushf` (push --force-with-lease)
- **Sensible defaults** - Auto-setup remotes, `push.default = simple`
- **Stacked-PR friendly** - `rebase.updateRefs` (rewrite stacked refs in one rebase) and `rerere` (remember conflict resolutions across restacks)
- **Personal credentials** - Uses Austin Gregg-Smith's git user info on profiles with the `identity` flag (`personal`, `container`); omitted on `shared` and `robot` profiles so commits made by others on the account can't impersonate you

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

### Isolated Shell (ags)
| Command | Purpose |
|-------|---------|
| `ags` | Enter an isolated shell with full dotfiles (bootstraps into `~/.local/share/ags` on first run, never touches the real HOME) |
| `ags <container>` | Same, inside a running docker container — injects itself and bootstraps there |
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
