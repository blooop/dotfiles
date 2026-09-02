# Dotfiles

Personal development environment configuration managed with [Chezmoi](https://www.chezmoi.io/) and [Pixi](https://pixi.sh/).

## Profiles

Every install picks a **machine profile** — the level of invasivity. The profile is
resolved once at `chezmoi init` (interactive prompt, or `CHEZMOI_PROFILE` env var, or
auto-detected from `AGS_SHELL`/`DEVPOD`), persisted in `~/.config/chezmoi/chezmoi.toml`,
and every later `chezmoi apply`/`update` uses it — no env vars needed after setup.

Profiles map to **capability flags**; templates gate on the flags, never on profile
names. The matrix lives in one place: `.chezmoi.toml.tmpl`.

| Flag | personal | shared | robot | container | kinisi | Controls |
|------|----------|--------|-------|-----------|--------|----------|
| `identity` | ✓ | ✗ | ✗ | ✓ | ✗ | git user name/email |
| `gui` | ✓ | ✗ | ✗ | ✗ | ✗ | Kitty, nerd fonts, uhk-agent, nvtop |
| `heavy` | ✓ | ✗ | ✗ | ✗ | ✗ | rust, nodejs, devpod, ccache, pi, yq, lazydocker |
| `host` | ✓ | ✗ | ✓ | ✗ | ✗ | git, git-lfs, openssh, curl, unzip |
| `monitor` | ✓ | ✓ | ✓ | ✗ | ✗ | htop, btop |
| `agents` | ✓ | ✓ | ✗ | ✗ | ✗ | codex, opencode (AI coding CLIs) |
| `toolbox` | ✓ | ✓ | ✓ | ✗ | ✗ | the interactive toolbox — zellij (+ its wasm plugins), ripgrep, fd, zoxide, broot, vim, lazygit, xclip, prek, go, topgrade, isd, zjsh, herdr, sshpass, wf, devlaunch |
| `editor` | ✓ | ✗ | ✗ | ✓ | ✗ | neovim + its `.config/nvim` tree; xclip (also under `toolbox`, so every profile but `kinisi` gets it) |
| `pixi` | ✓ | ✓ | ✓ | ✓ | ✗ | `~/.pixi/manifests/pixi-global.toml` |
| `xdg` | ✓ | ✓ | ✓ | ✓ | ✗ | `~/.config`, `~/.cache`, `~/.local/share` |
| `gitconfig` | ✓ | ✓ | ✓ | ✗ | ✗ | `~/.gitconfig` |
| `claudecfg` | observed | observed | observed | observed | observed | `~/.claude` |

The last four are **ownership** flags: they say whether chezmoi may write a path at all,
and are off only where something else owns it — a host bind-mount, the image, or the
container runtime. `claudecfg` says **observed** rather than ✓/✗ because it is the one
flag no column can answer: `install.sh` reads the mount table and reports whether
`~/.claude` is this machine's or somebody else's, and the flag is that answer. See
[Who owns `~/.claude`](#who-owns-claude). Note that they are all still ✓ on `shared`, which is why the
fallback below limits the *capability* damage of an unidentified machine but not the
*ownership* damage: see [When nothing identifies the machine](#when-nothing-identifies-the-machine). They are not a way to make a profile "smaller": every path not listed
there is applied in a container, which is how a fresh devcontainer comes up with the same
shell and config as the host.

Making a profile smaller is `toolbox`'s job, and it is a capability flag precisely
because the ownership flags are not allowed to be one. A container wants the host's
config; what it does not want is the host's tool payload. Every `dl` workspace was
syncing ~25 pixi envs / ~1.27GB — go, isd, vim, zellij, a second devlaunch — plus
8.4MB of zellij wasm plugins, on every create (a fresh container has no package
cache), in order to run `claude` and `gh`. With `toolbox` off, a container installs
eight envs: fzf, git-delta, forgit, chezmoi, gh, jq, claude-shim, claude-statusline.
Every profile a human logs into keeps the lot.

`editor` is the second size knob, and it points the other way — it gives a container
back the two tools the shell config never stopped naming. `.bash_env` exported
`EDITOR=nvim` and sourced forgit's plugin with no gate, and `.bash_aliases` builds
`gg` on forgit, so a container ran with a dangling `EDITOR` and six dead git aliases
that the cheatsheet below still listed. That is the floor's own bar — "the config
wires it in unconditionally" — so forgit moved into the floor outright. neovim did
not: it costs 1.1GB, of which 18 of the env's 20 packages are the gcc/gxx toolchain
that nvim-treesitter needs to build parsers (neovim itself is ~50MB), so it sits
behind `editor` and lands only where it is actually driven. `shared` and `robot`
keep vim: neither had nvim before the flag existed, and a lab PC or an appliance is
the last place to want a compiler.

- **personal** — your own machine: everything.
- **shared** — shared account (ags isolated shells, lab PCs): the full toolbox + system monitors + AI coding agents (codex, opencode), git identity omitted so others on the account can't impersonate you. vim, not nvim — `$EDITOR` resolves to whichever is on PATH.
- **robot** — robots/appliances: toolbox + host tools (git, ssh, monitoring), no identity, no GUI, no toolchains, vim rather than nvim.
- **container** — devcontainers/DevPod: the eight-env floor + nvim and its config via `editor` + the full `~/.config` tree and pixi manifest (both container-local). No toolbox — no zellij or launchers *from here*, because the only things otherwise run in a workspace are `claude` and `gh` (devlaunch 0.15.0+ skips [its own zellij install](#dev-containers-dl--aid) by default, so nothing here has to ask it to). Identity kept, but `~/.gitconfig` is skipped in favor of the XDG fallback because DevPod overwrites it with credential injection, and `~/.claude` is skipped because `dl` bind-mounts the host's.
- **kinisi** — `kinisi_ros` dev containers: `container`, minus every path the compose files bind-mount from the host (`~/.config`, `~/.cache`, `~/.local/share`) and minus `~/.pixi`, whose manifest the image symlinks into the `kinisi_ros` checkout. Selected only by `container/bootstrap.sh`, never prompted for.

Adding a new machine class = one row in the matrix in `.chezmoi.toml.tmpl`, no other
template changes.

To change an existing machine's profile, re-run init (apply alone reuses the stored one):
```bash
CHEZMOI_PROFILE=robot chezmoi init --apply
```

### When nothing identifies the machine

The fall-through profile is **`shared`**, and that is a deliberate fail-closed choice
rather than a guess at the common case.

It used to be `personal`, which is the worst available answer to "I do not recognise
this machine": `personal` is the only row with `identity`, `gui`, `heavy` and `host`
all ✓, so an unidentified environment received the most invasive install in the
matrix. Nothing ever detects a machine as *yours* — `personal` was simply what was
left when the `AGS_SHELL` and `DEVPOD` probes both missed.

The two entry points reach that default differently, which is worth knowing.
`promptChoiceOnce` does *not* silently fall back when there is no tty: it fails with
`could not open a new TTY`, and returns its default only under `--promptDefaults`.
So the template's default governs a hand-run interactive `chezmoi init`. Every
scripted path — including every container — goes through `install.sh`, which picks a
profile itself and passes `CHEZMOI_PROFILE=<profile> chezmoi init --apply --force`,
bypassing the prompt altogether. `install.sh`'s fall-through is therefore the one
that actually fired; both are now `shared`.

What it cost, once: a `kinisi_ros` container that never ran `container/bootstrap.sh`
(a VS Code Remote-Containers attach, say) never gets the `KINISI_INSTANCE` handshake
that `container/bootstrap.sh` needs, so it never reaches the `kinisi` row. It fell
through to `personal` instead — and since the compose files bind-mount `~/.config`,
`~/.cache` and `~/.local/share` from the host, "the container's `~/.config`" and
"the host's `~/.config`" are the same directory. It wrote a `kitty.conf` rendered for
`/home/kinisi` onto the host, and left 79 `/home/kinisi` keys in the host's chezmoi
state DB. (The bootstrap avoids exactly this by keeping the container's chezmoi config and
state in `~/.local/state`; nothing else does.)

`shared` closes the **capability** half: no git identity, and the GUI and toolchain
trees (`.config/kitty`, `.config/nvim`) are left alone. The trade is that a personal
machine must now say so.

It does not close the **ownership** half on its own — `pixi`, `xdg`, `gitconfig` and
`claudecfg` are all ✓ on `shared`. That half is closed by the check below, which is
where it has to be: `~/.config/chezmoi/chezmoi.toml` is written by `chezmoi init`
itself, so no flag the config template sets can protect the file that template's own
output lives in.

### Who owns `~/.claude`

`claudecfg` is the one ownership flag that is not read off the profile name, and the
reason is a bug it caused. It used to be `not containerish` — off for every container —
on the stated grounds that "devlaunch bind-mounts the host's `~/.claude` into the
container read-write". devlaunch does not do that and never did. It lends the host's
`claude` *binary* over the ssh channel and injects the login as the environment
variable `CLAUDE_CODE_OAUTH_TOKEN`, and it mounts nothing.

So nothing carried the config. `claude-statusline` was installed in every workspace
(it is in the container floor) and the `settings.json` naming it as `statusLine.command`
was skipped, and a `statusLine` command that is not found fails silently — hence a
blank bar in `dl kinisi-robotics/team-tracker`, and hence a Claude problem that was
really a dotfiles problem.

What does mount `~/.claude` is a repo's *own* devcontainer opting in. devlaunch's
`claude-code` feature binds it read-write, so it holds in the repos that ship that
feature and nowhere else — which is why the same launch against a repo you own looked
fine. The two sides each believed the other delivered this.

The flag is therefore an observation, made by `install.sh` before `chezmoi init` and
passed in as `DOTFILES_CLAUDE_MOUNT`:

- **`local`** — no mount at or under `${CLAUDE_CONFIG_DIR:-~/.claude}`. chezmoi owns it
  and applies it, container or not.
- **`foreign`** — something is mounted there whose source subpath is under another
  `$HOME`. Whoever mounted it owns it, and every path that writes `~/.claude` stands
  down: the ignore entry, the 21 skill externals, the wayfinder link script and the
  removal list.

It scans `/proc/self/mountinfo` rather than asking `findmnt --target`, because
`findmnt` answers for the *nearest* mount at or above a path and the shape that
matters most sits below one. devlaunch's feature mounted nine individual paths under
`~/.claude` before it switched to mounting the directory — `settings.json` read-only,
`.credentials.json` read-write — and against that shape a check on the directory says
"ours" and the apply writes through the file mounts onto the host's real config. A
scan sees descendants for free.

It convicts on the same evidence `is_foreign_tree` requires (a source subpath under
some other home) and spares the same cases (a whole separate filesystem, so a volume
or a tmpfs). It is deliberately *not* another entry in the foreign-tree list above:
that list refuses the whole install, and a devlaunch workspace has a mounted
`~/.claude` while its `~/.config` is container-local, so listing it there would leave
every such workspace with no shell config at all to protect one directory that one
flag protects on its own.

A hand-run `chezmoi init` that skips `install.sh` has observed nothing, and keeps the
old conservative guess: containers do not write `~/.claude`.

### Refusing a home that is not this machine's

`install.sh` exits early, before touching anything, when `$HOME`'s config trees turn
out to belong to another machine. The observed fact it gates on has two halves, and
both are required:

1. the tree is on a **different filesystem from `$HOME`**, so something mounted it in
   from outside, and
2. `findmnt` reports a **source subpath that is not under `$HOME`** — i.e. it names
   some *other* home.

|                     | `$HOME` | `~/.config` | verdict |
| ------------------- | ------- | ----------- | ------- |
| host                | dev 64513 | dev 64513 | ours |
| DevPod workspace    | dev 179 (overlay) | dev 179 (overlay) | ours |
| `kinisi_ros` container | dev 85 (overlay) | dev 64513, `[/home/ags/.config]` | **foreign** |

The first half alone would trip on a legitimately separate `/home` partition. The
second alone cannot see a bind mount whose subpath happens to sit under `$HOME` —
which is a mount of our own, and fine. A separate filesystem with no such subpath is
a volume or a tmpfs, which is a devcontainer caching `~/.config` rather than this
bug, so it is left alone.

Skipping costs nothing that is mounted: the trees that triggered the check *are* the
host's already-applied dotfiles, so the container already has every file the install
would have written into them. It exits 0, because a container start must not fail over
this. `DOTFILES_ALLOW_FOREIGN_HOME=1` overrides it for whoever means it.

It does cost everything **container-local** — `.bashrc`, `.bash_env`, `.bash_aliases`,
the private pixi root — none of which is mounted from anywhere. So when
`KINISI_INSTANCE` says this is a kinisi container, the refusal branch hands off to
[`container/bootstrap.sh`](container/bootstrap.sh) rather than leaving the container
bare: same `kinisi` profile the bootstrap uses, same container-local config, same private
pixi root, and still nothing written to a host tree. Without that handoff a
`dl kinisi-robotics/kinisi_ros` workspace came up with no personal environment at all,
which surfaced as a blank Claude status line — `~/.claude/settings.json` rides the bind
mount in and names `claude-statusline`, a `statusLine` command that is not on `PATH`
fails silently, and the same launch against a plain DevPod repo showed the bar fine.

What this prevents, concretely — all of it observed, on a host running kinisi
containers with DevPod's `DOTFILES_URL` set globally, so `install.sh` ran inside
every one of them:

- `chezmoi init` writing `profile = "shared"` into the **host's**
  `~/.config/chezmoi/chezmoi.toml`. The host loses `identity`, `gui`, `heavy` and
  `host`; the next `pixi global sync` uninstalls `kitty-bin`; and XFCE's Super+T dies
  with *Failed to execute child process `~/.pixi/bin/kitty`*, because the
  `TerminalEmulator` helper still names a binary that is no longer there.
- every template rendered with `homeDir=/home/kinisi`, so the host's zellij config
  names `file:/home/kinisi/.config/zellij/plugins/*.wasm` plugins it cannot load.
- `rm -rf "$HOME/.local/share/chezmoi"` deleting the **host's** chezmoi source dir,
  `.git` and all. That one is fixed twice over: the clone branch now fast-forwards an
  existing source dir instead of replacing it, and leaves anything a fast-forward
  cannot resolve exactly as it is. Being one commit behind is a far cheaper failure
  than a deleted `.git`, and uncommitted edits waiting to be committed are that
  directory's normal state.

## Usage

### Quick Install

One-liner that handles cache permissions and installs everything. The profile is
auto-detected (DevPod → `container`, ags → `shared`) and otherwise falls back to
`shared`, so **your own machine has to ask for `personal` explicitly**:

```bash
# personal machine — the profile is required; without it you get `shared`
curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/install.sh | CHEZMOI_PROFILE=personal bash

# robot / shared machine / container
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
`CHEZMOI_PROFILE` entirely to be prompted interactively — the prompt now defaults to
`shared`, so accepting it on your own machine gives you the shared profile.

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

*Where pixi installs, in any container:* `~/.pixi` unless something else has claimed it,
and the test for claimed is that `~/.pixi/manifests/pixi-global.toml` is a **symlink** —
which means an image put it there. A manifest symlinked into a checkout (kinisi_ros's
devcontainer does exactly this from `.devcontainer/on_create.sh`) turns every
`pixi global install` into a write through the link, and the workspace's `git status`
never comes up clean again. Where that is found, both `install.sh` and
`private_dot_bash_env` fall back to the same private root the bootstrap uses
(`~/.local/share/pixi-container-<arch>`) and the checkout is left alone. Asking about
the symlink rather than about `KINISI_INSTANCE` is what makes this cover a DevPod launch
of such a repo: the compose files set that variable, `devpod up` does not.

**Manual (any devcontainer):**

Use the DevContainers installation command above, or add to your devcontainer configuration.

**Kinisi dev containers:**

`kinisi_ros` containers are *not* DevPod workspaces. `kinisi_env start` launches them,
and it already handles X11, NVIDIA, `privileged`/host-network mode and the per-clone
mounts that keep `k1`…`k5`, `kreal` and `kr2map` as separate containers off one image.
Routing that through `dl` would fight it for no gain — but `kinisi_env` installs nobody's
dotfiles, which is the gap `container/bootstrap.sh` fills:

```bash
# Bootstrap dotfiles into a running container. Idempotent; re-run after any
# dotfiles change, and after the container is recreated (it keeps /home/kinisi
# container-local, so recreation wipes .bash_env and the .bashrc hook).
docker exec kinisi_jazzy_k1 bash -c 'bash "$HOME/.local/share/chezmoi/container/bootstrap.sh"'
```

Nothing in `kinisi_ros` is modified, so teammates are unaffected. It works through the
`~/.local/share` bind-mount the compose files already provide, which puts the chezmoi
source dir inside every container for free. Two things are kept off the shared paths:

- **chezmoi config** goes to `~/.local/state` (container-local), never `~/.config` —
  that directory is bind-mounted from the host and holds the host's `personal` profile,
  so a plain `chezmoi init` inside a container would rewrite it.
- **pixi globals** go to `$PIXI_HOME=~/.local/share/pixi-container-<arch>`, never
  `~/.pixi` — the kinisi entrypoint symlinks that manifest into the `kinisi_ros`
  checkout, so installing there would write through to a shared work tree.

Because every kinisi container has `HOME=/home/kinisi`, that pixi root resolves to the
same host directory at the same absolute path in all of them: **one install serves every
clone's container and survives recreation** (the second container takes ~15s and downloads
nothing). The arch suffix keeps x64 envs away from the arm64 thor/nanopi containers.

`~/.pixi` stays on `PATH` behind the personal root, so the image's own tools still resolve
and only the ones in [`container/pixi-global.toml`](container/pixi-global.toml) are
overridden. Edit that file and re-run the bootstrap to change what you get; it is a plain list
with no capability gating, because a container is a single known machine class.

One entry there is not about the shell at all: `claude-statusline`. `~/.claude` is
bind-mounted from the host, so `settings.json` names that binary inside every kinisi
container whether or not anything installed it — and a `statusLine` command that is not on
`PATH` fails silently, leaving the bar blank instead of erroring. This manifest is the only
thing that puts it there; the host manifest's floor never reaches these containers. Nothing
else agent-side is needed, since the image already ships `claude` in `~/.pixi`.

That install is still right to have, but it is no longer what the bar depends on.
`settings.json` names [`~/.claude/statusline.sh`](private_dot_claude/private_executable_statusline.sh)
now, and that script resolves `claude-statusline` from `PATH`, `PIXI_HOME`, `~/.pixi` and
the per-arch container root in turn. The reason is recreation: `/home/kinisi` is
container-local, so a rebuilt container loses `.bash_env` and the `.bashrc` hook and the
binary drops off `PATH` — while `~/.local/share` is bind-mounted, so the pixi root holding
it survives untouched. The blank bar was therefore never a missing install, only a missing
`PATH`, and it came back on every recreation until something could work that out at render
time. The script sits in `~/.claude` because that is the one tree guaranteed to be wherever
`settings.json` is, arriving by the same mount. Finding nothing at all, it prints
`statusline: not installed` rather than nothing — a blank bar is indistinguishable from a
working one with nothing to say, which is what made this expensive to diagnose.

`.chezmoiignore.tmpl` keeps the kinisi apply off every host-mounted tree (`.config`,
`.claude`, `.cache`, `.local/share`, `.pixi`), leaving it exactly what is container-local
and actually missing — `.bashrc`, `.bash_aliases`, `.bash_env`, `.vimrc`, `.terminfo`,
`.local/bin`. The `.bashrc` handling is a `modify_` script, so it *inserts* the
`.bash_env` hook into the image's ROS bashrc rather than replacing it: the personal
environment and `bm`/ROS coexist in the same shell.

**Where** it inserts is the interesting part, and on a ROS bashrc it inserts *twice*,
because the two halves of `.bash_env` want opposite positions.

The ROS bashrc opens with a section it declares runs in "BOTH interactive and
non-interactive login shells … so LLM agents can execute commands with full environment
loaded", and then returns. A hook after that return is reachable only to an interactive
shell — which is why `dl` (attaches a shell) showed a Claude status line and `aid`
(`dl … -- claude`, a *command*) did not: same container, same files, different shell mode,
and `claude-statusline` on `PATH` in one but not the other. So the environment half is
hooked in **before** the return, as `_BASH_ENV_ENV_ONLY=1 . ~/.bash_env`.

But the whole file cannot go there. Between that point and the end of the file sits the
image's copy of Debian's prompt block, which picks a plain `PS1` unless `TERM` is
`xterm-color` or `*-256color` — and kitty reports `xterm-kitty`. Sourcing everything early
let that block overwrite the prompt `.bash_env` had just set, so `dl` came back with an
uncolored prompt. The interactive half is therefore hooked in **late**, at the same
`.bash_aliases` anchor Ubuntu's bashrc uses, where it lands after the image's block and
wins. Ubuntu's bashrc gets only that late hook, for the same reason.

`.bash_env` splits itself on a `_BASH_ENV_ENV_ONLY` flag plus a `case $-` guard, so the
early source stops at the end of the environment and a one-command shell pays for `PATH`
and not for fzf keybindings, zoxide, forgit or the zellij handling. Being sourced twice is
part of the contract: `PATH` goes through a `_path_prepend` helper that skips a directory
already present, and everything else in that half is an idempotent export.

### PATH hygiene

Nothing that writes `PATH` here knows about the others, and there are more of them than
this repo owns: Ubuntu's `.profile` re-adds `~/.local/bin` *after* it has already sourced
`.bashrc`; the generated `KINISI_ENVIRONMENT` block re-adds `~/.pixi/bin` and
`~/.local/bin` below the hook; an old `install.sh` line named a variable set nowhere. The
host carried `~/.pixi/bin` three times, `~/.local/bin` three times, and one **empty**
element — which bash reads as the current directory, so any directory you `cd` into could
shadow a command.

Three helpers in `.bash_env`, applied in two places:

| helper | what it does |
| ------ | ------------ |
| `_path_prepend` | adds a directory only if absent — makes this file safe to source twice |
| `_path_dedupe` | drops empty elements and later copies, keeping first occurrence so precedence is unchanged |
| `_path_promote` | moves one directory to the front, for precedence that must survive blocks sourced later |

`.bash_env` dedupes when sourced, but it cannot be last — the kinisi block sits below it
and is regenerated by someone else's script, so it is not ours to guard. `modify_private_dot_bashrc`
therefore appends a final `_path_dedupe` + `_path_promote "$PIXI_HOME/bin"` at the very end
of `.bashrc`, which is the only position after every writer.

A one-command login shell never reaches that line. `bash -lc <cmd>` — which is how `dl`
runs a launched agent's payload — reads `.profile`, which sources `.bashrc`, which returns
at its non-interactive guard before any of this. `modify_dot_profile` hooks the
environment half of `.bash_env` onto the end of `.profile` so that shell gets `PATH`,
`PIXI_HOME` and `SSH_AUTH_SOCK` at all, and `.bash_env` now runs the dedupe and the
promote itself, above the environment-only return, so both hooks land on the same
precedence. Without that second promote a login shell had the personal `PATH` with the
wrong order in it, and `claude` resolved to `~/.local/bin`'s installer symlink there while
the same `claude` in a terminal resolved to the pixi shim.

The promote is not cosmetic. On 2026-08-25 Claude Code's native installer put a `claude`
symlink in `~/.local/bin`, colliding with the `claude` this repo exposes from `claude-shim`.
That is the *only* overlap between the two directories, and until then `claude` resolved to
the shim because nothing else offered it. Promoting the pixi root keeps it that way; without
it, deduplication alone silently handed `claude` to the other binary.

That is what the separate `kinisi` profile buys: those skips are gated on ownership flags
(`xdg`, `pixi`), so a plain DevPod workspace — where none of those paths are mounted and
`~/.pixi` is its own — keeps them. Applying them to every container was a real bug: with
`.pixi` skipped, `pixi global sync` synced the *image's* manifest, printed "Nothing to do",
and left the workspace with no fzf, zoxide, fd or ripgrep at all.

> Distinct from `ags`, which gives you an *isolated* HOME and is the right tool on shared
> or foreign machines. The bootstrap applies into the container's real HOME precisely so the ROS
> environment stays intact.

## What's Included

### The Floor (every profile, containers included)
Eight envs, and the bar for adding one is "the floor stops working without it":
- **Agent** - claude-shim (`claude`, `cld`, `cldr`), gh, claude-statusline (what `~/.claude/statusline.sh` resolves and the status line runs — that file rides the `~/.claude` bind mount into every container, and containers have no python3 for the script it replaced)
- **Wiring** - chezmoi (so a container can keep applying), fzf, git-delta and forgit (`.bash_env` and `.gitconfig` wire all three in unconditionally — delta is git's configured pager, and `.bash_aliases` builds `gg` on forgit), jq

### Capability-Gated Tools (see Profiles matrix above)
- **`toolbox`** - everything below, on every profile except the container ones:
  - **Search & navigation** - fd, ripgrep, zoxide (smart cd), broot (tree browser)
  - **Git** - lazygit (forgit is in the floor, not here)
  - **Terminal** - zellij (multiplexer) + its wasm plugins, zjsh, herdr (agent workspace manager), wf (wayfinder ticket picker), devlaunch (`dl`/`aid`), vim
  - **Management** - topgrade, prek, isd
  - **Utilities** - sshpass, go (xclip is shared with `editor`, above)
- **`host`** - git, git-lfs, openssh, curl, unzip, speedtest-go, `nvidia-upgrades` script
- **`monitor`** - htop, btop
- **`editor`** - neovim (+ full config), on personal machines and containers. 1.1GB, because nvim-treesitter compiles its parsers and so the env carries gcc/gxx; `shared` and `robot` use the toolbox's vim instead
- **`toolbox` or `editor`** - xclip, installed wherever there is an editor to yank from. It cannot work in a `dl` container — it is an X11 client and nothing forwards a display there — so nvim falls back to OSC 52 (see [Clipboard](#clipboard)) and the shell uses [`clip`](#clip-copying-from-the-shell), which makes the same choice
- **`heavy`** - nodejs, rust toolchain, devpod, lazydocker, ccache, pi, yq (and `dl`/`aid` split their exposure with the `toolbox` devlaunch env)
- **`agents`** - codex, opencode (AI coding CLIs)
- **`gui`** - Kitty, nvtop, uhk-agent, JetBrainsMono nerd fonts

pixi itself is installed by `install.sh`, not by the manifest, so it is present everywhere.

## Git Configuration

The git configuration (included in DevContainers and Full installations) provides:

- **Useful aliases** - `com` (checkout main), `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push), `pushf` (push --force-with-lease)
- **Sensible defaults** - Auto-setup remotes, `push.default = simple`
- **Stacked-PR friendly** - `rebase.updateRefs` (rewrite stacked refs in one rebase) and `rerere` (remember conflict resolutions across restacks)
- **Personal credentials** - Uses Austin Gregg-Smith's git user info on profiles with the `identity` flag (`personal`, `container`); omitted on `shared` and `robot` profiles so commits made by others on the account can't impersonate you

## Terminal Vibe-Coding Workflow

> **Multiplexer trial in progress: herdr.** Kitty's `shell` is a plain login
> shell and SSH logins land in a plain shell, so a window does not open into the
> Zellij layering described below — you type `herdr` when you want a multiplexer.
> Nothing Zellij-related has been removed, so this section stays accurate for the
> reverted state and for any machine that opts out. See
> [Multiplexer trial: herdr](#multiplexer-trial-herdr).

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
attaches to one persistent session named `main`, creating it if necessary. A
dropped connection therefore costs nothing — reconnecting reattaches the same
session rather than starting over, from whichever device reconnects — and projects
are switched inside it with `Shift+F5`. Detaching exits `0`, which ends the SSH session
exactly as closing a Kitty window does locally.

Bash sources `.bashrc` for *remote non-interactive* shells too, which is how a
naive version of this breaks `scp`, `rsync`, and `ssh host <command>`. The
autostart is guarded on an interactive shell with a real tty on both stdin and
stdout, `SSH_CONNECTION` present, `SSH_ORIGINAL_COMMAND` absent, neither `ZELLIJ`
nor `TMUX` already set, `TERM_PROGRAM` not `vscode` (Remote-SSH and the
integrated terminal manage their own tabs), `TERM` not `dumb`, and `HERDR_ENV`
unset. It sits at the very end of the file, after `~/.bash_env.local`, so a
machine can opt out with `ZELLIJ_AUTOSTART=0`.

If Zellij is what breaks, it exits non-zero and the login falls through to a
normal shell rather than dropping the connection. `ssh -t <host> 'bash --norc
-i'` skips the file altogether.

##### Why `HERDR_ENV` is one of the guards

herdr is a multiplexer of its own, and it is the guard that cost the most to
learn. A pane it spawns inherits the
environment of the SSH login that started the herdr client — `SSH_CONNECTION`
included — while setting no `ZELLIJ` and holding a real tty on both ends. Every
other test above therefore passes, and a herdr pane autostarts Zellij as though
it were a fresh login.

The damage is not the nesting. herdr's server outlives its client, and on the way
out the departing client's geometry is written onto the panes it leaves behind
rather than being restored — measured at `cols=4 rows=2` on the CI box, and
reproduced independently against herdr 0.8.2 as a pane that goes from `39x93` to
`2x5` and stays there for the life of the server. The bash still sitting in that
pane then attaches to the *shared* `main` session as a second client, and **Zellij
sizes a session to its smallest client**. One 4x2 ghost is enough to crush a
full-screen session with two dozen agents in it.

`HERDR_ENV=1` is the discriminator because herdr injects it, along with
`HERDR_PANE_ID`, `HERDR_TAB_ID`, `HERDR_WORKSPACE_ID`, `HERDR_SOCKET_PATH` and
`HERDR_BIN_PATH`, into every pane it spawns. A resident server is easy to miss —
one went unnoticed for thirteen days — so `herdr server stop` is the clean
shutdown, and `herdr-server.log` records the `client resize` walk when a session
mysteriously collapses.

##### One session for every device, not one per device

The session is plain `main`, so every device you own reaches the same one. This
was per-client for a while, and per-client is the wrong default because it cannot
name the *person*: this repo is applied under several usernames and every machine
has its own hostname, so both `$USER` and `$HOSTNAME` differ between two devices
belonging to one person. Naming the session after either guarantees the laptop
never finds the desktop's session — which defeats the only reason a remote session
is persistent at all.

Per-client naming still exists for the case it was written for: a *shared account*
— a CI box reached as one service user. Two people attaching to one session become
clients of it and Zellij mirrors them, both seeing one screen annotated `MY FOCUS
AND: FOCUSED USERS`. Nothing is lost, but it is a baffling thing to walk into. Opt
in per host, in that host's `~/.bash_env.local`:

```bash
export ZJ_SSH_PER_CLIENT=1
```

The session is then `main-<client hostname>`, with the name reaching the far end in
`LC_ZJ_CLIENT`. `LC_`-prefixed because sshd's stock `AcceptEnv` is `LANG LC_*`, so
an `LC_` variable crosses without any server-side configuration — the usual trick
for propagating a value you control to a host you may not. It still needs the
client to send it, which is one block in `~/.ssh/config`:

```sshconfig
Host *
  SendEnv LC_ZJ_CLIENT
```

Note that `~/.ssh/config` is **not** chezmoi-managed, because DevPod writes its own
blocks into it. Without that `SendEnv` the variable does not arrive and an opted-in
host falls back to `main` anyway. `ZJ_SSH_SESSION` overrides the name outright and
wins over both.

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

Since the remote runs this same config, applied by chezmoi, the keymap is
identical — `F2`, `F3`/`F4`, `F8`, `F9`, `F12` and the whole `Ctrl+;` layer do
exactly what they do locally, acting on the remote. Nothing is remapped and no
pass-through mode is involved. That is the entire benefit of one multiplexer.

`Ctrl+Shift+R` is the same window with the hostname built in: it runs `sshz`, an
fzf picker over `~/.ssh/config` and the `ssh` lines in history, which then `exec`s
the connection. Two steps beat one only in theory — the two-step version of the
right answer loses to the one-step version of the wrong one, which is SSHing from
an ordinary pane. `exec` also means the remote *is* the window's process, so
ending the remote session closes the window instead of exposing a local shell that
needs a second `exit`.

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
inside a session, `Shift+F5` opens the same picker without a new window.

Closing a window never prompts for confirmation (`confirm_os_window_close 0`).
Kitty's default asks when a foreground process is running, but with Zellij
owning persistence there is nothing to lose by closing.

### Naming a session

Zellij names sessions itself, and it names them `sincere-petunia`. That is fine
for one and useless for twenty: the tab bar, `zj`, `zjclean` and
`zellij list-sessions` all end up showing a list of adjectives and animals with
no way to tell which window is which project.

The name is not only Zellij's. The terminal window title is
`{session} | {pane title}`, so it is the session name that leads the alt-tab
list — `dotfiles | ⠐ Streamline Zellij nested sessions` rather than
`sincere-petunia | …`. Naming a session names the whole window.

There are two ways to do it, and they answer different questions.

`Ctrl+; o n` names the session after the project in the focused pane — one
keystroke, nothing to type. From `~/.local/share/chezmoi` the tab bar becomes
`Zellij (chezmoi)`.

**`Ctrl+; o N` asks instead**, and that is the one to reach for. The automatic
name is always the project, and several windows open on one project is the
normal case rather than the exception — they come back as `chezmoi`,
`chezmoi-2`, `chezmoi-3`, which is no easier to tell apart than the adjectives
and animals. What actually distinguishes two windows on one repo is what you are
doing in them, and only you know that. So `Ctrl+; o N` opens an fzf prompt where
anything you type is a name, prefilled with the machine's best guesses in the
order they are likely to be right:

1. **the focused pane's title**, because an agent or an editor has usually
   written a summary of the work into it — this is the suggestion that knows
   what the window is *for*, and it is why the prompt usually costs one Enter;
2. **the Git branch**, when it is one that names work rather than the trunk;
3. **the project**, which is what `Ctrl+; o n` would have picked anyway.

Zellij's own placeholder titles are never offered: an unclaimed pane is
`Pane #1`, and `pane-1` as the suggestion sitting under the Enter key would be
worse than no suggestion at all. Free text is slugified to what a socket path
can hold and cut back to a word boundary at 24 characters, so a long title
becomes `streamline-zellij` rather than `streamline-zellij-neste`.

`zjname` does the project thing from a shell, `zjname <name>` sets one by hand,
and `zjname --prompt` is the picker.

It is a key rather than something automatic, and the reason is worth knowing:

- **A rename invalidates the session name every other pane is holding.** Panes
  capture `ZELLIJ_SESSION_NAME` when they spawn, and afterwards `zellij action`
  from a pane still holding the old one *hangs on its socket rather than
  failing* — which would disable the last-pane exit trap and stall everything
  else that shells out to zellij, `zellij-nav`'s `Ctrl+hjkl` included. A rename
  therefore records the name it replaced under `$XDG_RUNTIME_DIR/zellij-names/`,
  pointing at the name that replaced it, and a prompt hook in
  `private_dot_bash_env` follows that chain so an already-open pane repairs
  itself. The common case is a single file test, so it costs nothing to leave
  running — but it is a repair, not something to lean on, which is why renaming
  is a deliberate act and not a thing that happens on every `cd`.
- **A name already in use is never taken.** `rename-session` onto an existing
  name does not fail: it takes the name and the session that held it
  disappears, resurrectable records included. Two windows on one repo is
  ordinary, so `zjname` finds a free name first — `chezmoi`, then `chezmoi-2` —
  counting every listed session, exited ones too.

The binding passes `--focused` because the two callers see different
directories. A shell knows its own `$PWD`, but a keybinding does not run in a
shell: Zellij launches the command in a pane of its own, and that pane inherits
the *session's* default directory rather than the one you are working in. So
`zjname` asks Zellij instead — `zellij action list-panes --all` reports each
pane's `CWD`, `FOCUSED` and `FLOATING`, and tracks a live `cd` — and skips its
own pane, which by the time it runs is the focused floating one. A pane running
a command rather than a shell reports its `CWD` as `-`, which the agent panes
this is usually aimed at all do; that costs the directory but not the title, so
the pane still counts.

Both bindings pass their argument **positionally** — `Run "zjname" "--focused"`,
not an `args` child inside the braces. A layout's `command` pane spells the same
thing with `args`, and writing it that way in a keybinding parses without
complaint and is then silently dropped, so the command runs bare. It is worth
knowing because it fails in the direction of doing something plausible: `zjname`
with no arguments still renames the session, just after the wrong directory.
`Ctrl+; t w` had the same defect, and was launching a bare `zellij` — a whole
nested session — into a one-cell floating pane instead of adding a tab.

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
of byobu. No modifier is required for any action reached more than a few times a
day, and they are bound in every mode, locked included, so they behave
identically from a shell, from Neovim, and from an agent pane. The one exception
is the pass-through mode described below, which exists precisely to be the place
they are *not* bound.

Four keys are byobu's, unchanged: `F2`/`F3`/`F4` are new window, previous window,
next window, and `F6` is detach. The rest are ordered by **how often the action is
reached for**, against how easily the key is reached — `F1` and `F8`-`F11` anchor
off the ends of their groups, while `F6`/`F7` sit mid-row with nothing to find
them by and therefore hold the two least-used actions. `F5` is the exception,
and the section below it explains what bought the key.

| Key | Action | Reach |
|-----|--------|-------|
| `F1` | Lazygit in a large floating pane | easy |
| `F2` | New tab | byobu |
| `F3` | Previous tab | byobu |
| `F4` | Next tab | byobu |
| `F5` | [Open the focused pane's scrollback in an editor](#copying-text-with-the-keyboard) — the only keyboard route to selecting and copying | hard |
| `Shift+F5` | Leap between projects: jump to any session by name | shifted |
| `F6` | Detach, leaving the session running; closes the window, ends an SSH connection | byobu |
| `F7` | Quit: end this session, leaving it resurrectable | hard |
| `F8` | New pane, Zellij's best available split | easy |
| `F9` | Jump to a tab by name | easy |
| `F10` | Close the focused pane | easy |
| `F11` | Agent picker | easy |
| `F12` | Control-mode gateway | escape |

The awkward middle earns its keep at `F6`/`F7`: both ways of leaving a session
are deliberately slow to reach, and they are also where a mis-hit costs the most.

`F5` breaks that pattern deliberately, and it is the one place on the row where
frequency beat reach. Zellij has **no keyboard text selection at all** — scroll
mode moves the viewport and searches, and every way of marking a region is a
mouse drag — so opening the scrollback in an editor is the only way to select and
copy without leaving the keyboard. That is a several-times-an-hour action, and
every other bare key was either byobu's or already per-minute, so it displaced
the least frequent thing on the row rather than earning a key of its own. The
mis-hit is cheap: a floating editor over text you already have, closed with `:q`.
See [Copying text with the keyboard](#copying-text-with-the-keyboard).

`Shift+F5` is the one shifted key on the row, and it holds what `F5` displaced:
leap between projects, a few-times-a-day context switch that can afford the
modifier. The shift arrives intact — Zellij's parser accepts modified function
keys and decodes Kitty's `CSI 15;2~` — unlike the modified *special* keys that
`Ctrl+,` / `Ctrl+.` exist to work around. Naming a session, which used to live
here, moved down to `Ctrl+; o N`.

`F6` is detach rather than quit because that is what byobu's `F6` does, and byobu
is the only trained reflex these keys have. A reflex aims at a key on purpose,
which makes it a stronger claim on `F6` than fumble-distance is: quit used to sit
here on the grounds that `F6` has a cold key on either side, but the fumble it was
guarding against is rare and random, whereas every byobu-trained hand hits `F6`
intentionally. The swap has a price — quit now neighbours `F8`, a per-minute key,
so it no longer has a cold key on both sides. It is affordable only because quit
is recoverable; see
[Session operations and lock mode](#session-operations-and-lock-mode).

Two costs. `F10` closes a pane with no confirmation. And applications inside
Zellij no longer see `F1`-`F11`, which matters for htop and Midnight Commander;
both have letter equivalents, and `Ctrl+; o a` hands the whole layer back for the
rare TUI that genuinely needs function keys (`Ctrl+; o A` restores it).

#### What `F10` actually does

`F10` is one action — `CloseFocus`, close the focused pane — but it is worth
knowing that it cascades, because the result looks like three different keys:

| Focused pane is… | What you see |
|------------------|--------------|
| one of several in a tab | the pane closes |
| the last pane in its tab | the pane **and the tab** close |
| the last pane in the last tab | the session ends, and the window closes with it |

Nothing is conditional in the binding; the depth is. Two things hide which depth
you are at. Fullscreen (`Ctrl+; z`) conceals that a tab holds four panes, and `Ctrl+h` /
`Ctrl+l` are `MoveFocusOrTab`, which at a tab edge crosses silently into the next
tab — so the pane `F10` closes is not always in the tab you think you are in.

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
than what it replaces.

A centred segment needs symmetric clearance, so zjstatus draws this bar only
above `2 × len(format_left) + len(format_center)` columns — and below that it
renders **nothing at all**, not a truncated legend. That is why `format_left` is
`{mode}` alone: with `{session}` in it the threshold rode on a name Zellij picks
at random, so the bar needed 118 columns under `main`, 136 under
`chatty-weasel`, and 150 under `gregarious-jellyfish`, vanishing on some windows
and not others with nothing on screen to explain it. Narrowing far enough brought
it back, because a different truncation path takes over near 100 columns, which
made it look like anything but a width problem. Without `{session}` the
requirement is a constant ~110 columns. The session name is not lost — `zellij:tab-bar`
renders `Zellij (name)` one row above.

`format_right` is empty, and deliberately so: **no command widget belongs in this
bar.** It used to run `zjcount` as `command_sessions` with
`command_sessions_interval "300"`, and zjstatus does not honour that interval — it
re-runs the command as fast as the command can exit. Measured: 571 invocations a
second across five servers, 34,000× the configured rate, with none of them reaped,
so zombies accumulated alongside. Output is irrelevant to it; a script printing
nothing at all still span at 867/s.

That was expensive twice over, because `zjcount` originally shelled out to `zellij
list-sessions`, which connects to every server in the list — O(sessions²) when run
from inside one of those servers. Once sessions had accumulated it passed ten
seconds per call, each call wedged on a stdout pipe its `timeout 3` could not close
(timeout kills `zellij`, but `$(…)` waits for orphaned children to release the
pipe), and ~3300 stuck processes took the load average to **880 on 8 cores**.
Rewriting `zjcount` to count sessions off the filesystem, so it could not hang,
only converted the pileup into a spin that still burned a full core. The widget
is gone with its slot; until zjstatus honours its interval, no command belongs
here, and `zjclean` is what lists the accumulated sessions.

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
| Tab | `F3` / `F4` | `F9` |
| Session | — | `Shift+F5` (leap), `Ctrl+; w` (`zj`, also creates), or `Ctrl+; W` |

`Ctrl+,`/`Ctrl+.` deliberately cycle **panes** rather than tabs. Tabs have
`F3`/`F4` and a name jump, whereas nothing cycles panes otherwise.

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
| `e` | Open scrollback in the editor (also on bare `F5`) |
| `n/N` | Next/previous result after starting a search |
| `c/w/o` | Toggle case sensitivity / wrapping / whole-word search |

Leaving scroll or search mode returns to the bottom before handing input back
to the application.

#### Copying text with the keyboard

Zellij 0.45 has no keyboard text selection. Scroll mode moves the viewport and
searches, but there is no visual-select action to bind: every way of marking a
region is a mouse drag, and `copy_on_select true` puts that drag straight on the
system clipboard.

**`F5` is the keyboard route.** It runs `EditScrollback`, which opens the focused
pane's scrollback — `scrollback_lines_to_serialize`, 10 000 lines — as a buffer
in `scrollback_editor` in a new pane. From there it is ordinary Vim:
`/pattern` to find, `v` / `V` / `Ctrl+v` to select, `y` to yank, `:q` to leave.
A bare `y` reaches the system clipboard everywhere — through `xclip` where there
is a display and through OSC 52 where there is not. Getting that to hold on an
SSH host took an explicit `clipboard=unnamedplus`; see [Clipboard](#clipboard). `Ctrl+; [ e` is the same action from scroll
mode, for when the search has already found the spot.

**Which editor is Neovim wherever Neovim exists.** `scrollback_editor` is
templated on `.editor` **or** `lookPath "nvim"`, so F5 opens `nvim` on `personal`
and `container`, on any machine that has nvim from outside the pixi manifest, and
`vim` — from the toolbox — everywhere else. It was hardcoded to `"nvim"` at first,
which made F5 a *dead key* on the two profiles that never had nvim: the floating
pane opens, execs a binary that is not on PATH, and dies instantly, which is
indistinguishable from an unbound key. Gating on `.editor` alone then overcorrected:
that flag answers "does pixi install nvim here", so a `shared` box carrying nvim
from a distro package or an `/opt/nvim` tarball got sent to vim with nvim on PATH
one directory over. `lookPath` is evaluated at apply time on the machine being
applied to, and the `.editor` half stays because apply runs before `pixi global
sync` on a fresh machine, where nvim is not installed yet. Vim serves the paragraph
above unchanged; only the LazyVim clipboard defaults are Neovim's, so where F5
lands in vim use `"+y` explicitly.

The binding is in the `shared_except "tmux"` block, so it fires from Locked and
from inside Neovim too, and unlike the scroll-mode copy it does **not** switch to
Normal — reading a pane's output should not unlock the session as a side effect.

#### Clipboard

`dot_config/nvim/lua/config/options.lua` picks the provider from the **display**,
not from the binary, and the container case is why. Neovim finds `xclip` by itself
on a desktop and switches to OSC 52 by itself over SSH (`$SSH_TTY`), but a `dl`
workspace is neither: `docker exec` sets no `SSH_*` variables and nothing forwards
an X socket into it (only `kinisi_ros` containers get X11, and `kinisi_env` owns
that). LazyVim therefore set `unnamedplus` with no provider behind it, nvim
reported `clipboard: No provider`, and every yank stayed in the container.

`xclip` is installed there anyway — it rides the `toolbox`/`editor` union, and it
is the right tool the moment a display *is* forwarded — which is exactly why
testing `executable("xclip")` would pick the broken provider in the one case that
needs the fallback. The test is `$DISPLAY`/`$WAYLAND_DISPLAY` **and** a tool;
without both, `vim.g.clipboard` becomes an explicit OSC 52 provider and the yank
goes out through the terminal to whatever is hosting it. Verified end to end under
a pty: a yank in a display-less environment puts `\033]52;c;<base64>` on the wire.

Having a provider is only half of it, though, and the other half bit on every SSH
host. `clipboard` decides whether a bare `y` is routed through the provider at all,
and LazyVim blanks it whenever `$SSH_CONNECTION` is set (`opt.clipboard =
vim.env.SSH_CONNECTION and "" or "unnamedplus"`). Its reason is the paste
round-trip: with `unnamedplus`, every paste asks the terminal to read the clipboard
back, and a terminal that denies OSC 52 reads leaves nvim waiting on an answer that
never comes. That reason does not survive the paste override above — paste is served
from the unnamed register and never touches the wire — so blanking `clipboard` only
broke the copy half. On an SSH host `xclip` is unreachable *and* `y` was unrouted,
so a yank in the F5 scrollback went nowhere and `"+y` was the only way out. The file
therefore sets `vim.opt.clipboard = "unnamedplus"` back, unconditionally.

This only ever misbehaved over SSH. On the host console `$SSH_CONNECTION` is unset,
LazyVim leaves `unnamedplus` alone and `xclip` has a display, so bare `y` always
worked there — which is what made it look intermittent rather than broken.

Two things make this awkward to test. `OptionSet` does not fire while options are
loaded at startup, so a watcher sees nothing; and LazyVim deliberately stashes
`clipboard` to `""` right after loading options ("xsel and pbcopy can be slow"),
restoring it on `VeryLazy`. A headless `nvim --headless +qa` never reaches
`VeryLazy`, so it reports `clipboard=[]` no matter what the config says. Check it
under a pty, or from inside a running session, never headless.

Paste is served from the unnamed register rather than from the terminal, because
Kitty's `clipboard_control` denies OSC 52 *reads* by default — a real paste request
comes back empty, so `"+p` gives back the last yank instead.

To grab a whole pane without selecting anything, skip the editor:

```bash
zellij action dump-screen /dev/stdout | clip
```

`--full` includes the scrollback above the viewport, not just the visible screen.

`clip` rather than `xclip` because this recipe is also the one you want from
inside a `dl` workspace, and `xclip` cannot serve it there. See
[`clip`](#clip-copying-from-the-shell).

#### `clip`: copying from the shell

`~/.local/bin/clip` copies stdin or a file to the system clipboard, and exists
because **`xclip` is installed in containers and cannot work in one**:

```bash
cmd | clip          # copy stdin
clip notes.txt      # copy a file
```

Nothing forwards an X socket into a `dl` workspace, so `echo hi | xclip
-selection clipboard` there fails with `Can't open display: (null)` — verified in
a live workspace. `command -v xclip` still succeeds, so any pipeline that probes
for the binary picks the one tool guaranteed to fail, which is why the recipe
above used to be a dead end inside a container. Until this existed, the only way
to get a container's output onto the host clipboard was a yank inside Neovim,
whose OSC 52 provider [Clipboard](#clipboard) already configures.

`clip` picks its route from the **display**, not the binary — the same test, for
the same reason, as `options.lua`. With `$DISPLAY`/`$WAYLAND_DISPLAY` and a tool
it uses `wl-copy` or `xclip`; otherwise it writes OSC 52, which travels out of
the container over the devpod pty, through Zellij, to the terminal hosting it. A
display that is set but unusable falls through to OSC 52 rather than failing,
since a stale forwarded `DISPLAY` is exactly the case that would otherwise copy
nothing and say nothing.

It writes to `/dev/tty`, never stdout, so `cmd | clip > log` and `clip | tee`
still reach the terminal. Paste has no counterpart on purpose: Kitty denies OSC
52 *reads*, so a read request comes back empty — see [Clipboard](#clipboard).

Verified end to end from inside a `dl` workspace: `clip payload.txt` in the
container put the sentinel on the host clipboard, through Zellij and Kitty.

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
| **Detach** | `F6`, `Ctrl+; o d`, closing the window | keep running | listed, live | you are coming back to *this* work |
| **Quit** | `F7`, `Ctrl+; o x`, `exit` in the last pane | killed | listed, `EXITED` | done, but you may want to resurrect it |
| **Delete** | `Ctrl+; o X`, `zjclean` | killed | gone | the project is genuinely finished |

Detach is a bookmark, not a close. `on_force_close "detach"` means closing the
Kitty window is a detach too, and `session_serialization` restores the layout and
commands on the way back in. Since every window is its own session, closing
windows is a bookmark-per-window machine: this is why sessions accumulate.

Nothing reports that accumulation automatically. A count used to sit in the
status bar and no longer does, because zjstatus ignores `command_<name>_interval`:
configured at `"300"` seconds it re-ran the widget as fast as the script could
exit, measured at 571 invocations a second, and never reaped them. Run `zjclean`
when you want to see the pile and act on it — see [The status bar](#the-status-bar).

Quit still leaves a resurrectable record behind — that is the point of
serialization, and it is why `Ctrl+; o X` exists as the "actually finished"
version. `Ctrl+; o q` is *lock*, not quit, so the obvious guess deliberately does
nothing destructive.

`F6` and `F7` are deliberately neighbours, with the escalation running
left-to-right — leave for now, leave for good — and both sit in the hard-to-reach
middle of the row, where a deliberate reach is the only kind you make. Detach
takes `F6` because that is byobu's `F6`, the one place these keys have trained
muscle memory pointing at them, and a trained reach should land on the harmless
one. Quit gets a bare key at all precisely *because* it is recoverable — it costs
the running processes but not the session, which `zellij attach` brings back.
`zjkill` deletes the record as well and therefore stays three keystrokes deep, on
the same reasoning that kept Quit itself away from `q`. `exit` in the last pane is
the same level as `F7`, since the `EXIT` trap ends the session rather than
detaching.

The cost of matching byobu is that quit sits beside `F8` and so has one warm
neighbour. Recoverability is what pays for it: the worst a mis-hit does is cost
the running processes, and `zellij attach` restores the layout.

`Shift+F5` switches to another project without leaving this one, and the project
just left is one of its candidates, so it is also how you get back.

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

What it also restores is the **zjstatus block**, because the serialized layout is
a layout and the bar is configured inside one. A session that outlives a change
to the legend therefore comes back showing the old keys, permanently, and no
`chezmoi apply` can reach it — the file on disk and the bar on screen disagree
until the record is deleted. The SSH autostart in `~/.bash_env` handles this for
the one session where it matters: before attaching it compares the record's
`format_center` against the layout on disk and drops the record when they differ,
so the attach rebuilds from `default_layout`. It uses `delete-session` without
`--force`, which refuses on a live session — a dropped connection must still
reattach. Elsewhere, `Ctrl+; X` after a legend change is the manual equivalent;
plain `Quit` on `F7` is not, since it leaves the stale record behind.

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
| `dot_config/kitty/kitty.conf.tmpl` | Kitty font, UI, `shell` = `.` (plain login shell) for the herdr trial, `zjshell` before it, and new-OS-window mappings |
| `private_dot_local/private_bin/executable_zjshell` | Kitty's shell before the trial: opens straight into Zellij, falls back to bash |
| `dot_config/systemd/user/herdr-server.service` | Runs the herdr server under `systemd --user`, so no terminal's lifetime can kill it |
| `run_onchange_enable-herdr-server.sh.tmpl` | Enables that unit and imports `DISPLAY`/`XAUTHORITY` so the clipboard works inside panes |
| `private_dot_local/private_bin/executable_zjclean` | Prunes accumulated sessions with an fzf picker; `--dead` purges exited ones, `--stale N` only old ones |
| `private_dot_local/private_bin/executable_zjkill` | Ends the current session and deletes its record |
| `private_dot_local/private_bin/executable_sshz` | `Ctrl+Shift+R`'s target: picks a host and `exec`s ssh, so one un-multiplexed window is one connection |
| `private_dot_bash_env` | Attaches SSH logins to the persistent `main` session when Zellij is the multiplexer (`# === Zellij on SSH ===`, off during the herdr trial); repairs a pane's session name after a `zjname` rename (`# === Repairing a renamed session's name ===`) |
| `private_dot_local/private_bin/executable_zjname` | `Ctrl+; o N`: prompts for a session name with suggestions; `Ctrl+; o n`: names it after the project in the focused pane. Avoids names already taken |
| `dot_pixi/manifests/pixi-global.toml.tmpl` | Installs Kitty as the `kitty-bin` pixi global env |
| `run_onchange_install-kitty-desktop.sh.tmpl` | Kitty desktop-menu entry (pixi does not create one) |
| `run_onchange_after_grant-zjstatus-permissions.sh` | Pre-grants zjstatus its plugin permissions, whose consent prompt cannot render in a one-row pane |
| `dot_terminfo/x/xterm-kitty`, `dot_terminfo/78/xterm-kitty` | `xterm-kitty` terminfo for non-Kitty ncurses builds (applied on **all** profiles, not just `gui` — `$TERM` follows you over SSH) |
| `dot_config/xfce4/helpers.rc` | Makes Kitty XFCE's default terminal |
| `dot_config/zellij/config.kdl.tmpl` | Modal keymap, function-key layer, floating tools, plugin registration |
| `dot_config/zellij/layouts/workspace.kdl.tmpl` | Neovim/Codex/Claude/terms workspace |
| `dot_config/zellij/layouts/simple.kdl.tmpl` | Default layout: one bare pane plus the UI |
| `.chezmoitemplates/zellij-status-bar.kdl` | zjstatus bar shared by both layouts; **holds the hand-written F-key legend** |
| `.chezmoiexternal.toml` | Downloads the `zellij-autolock`, `zellij-attention`, `zellij-leap`, `zjstatus`, and `zj-which-key` WASM plugins (gated on `.toolbox`); also extracts 21 of Matt Pocock’s skills straight into `~/.claude/skills` (gated on `.claudecfg`) |
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

## Multiplexer trial: herdr

Trialling [herdr](https://github.com/herdrdev/herdr) in place of Zellij, on the
argument that its four-state agent visibility (working, blocked, done, idle) is
the one thing this setup cannot build itself, and that running both multiplexers
side by side is what produced the 4x2 pty crush documented in
`# === Zellij on SSH ===`.

Nothing Zellij has been deleted — config, plugins and the `zj*` scripts are all
still applied — so reverting is config rather than reconstruction, and the Zellij
half of this README stays accurate for the reverted state.

### There is no autostart, deliberately

Zellij needed autostart at both ends because a Zellij session is per-window and
per-connection: without something putting you in one, there was no session and no
persistence. herdr inverts that. One server, running as a systemd user unit
before any terminal opens, and `herdr` attaches to it.

So nothing is arranged at login. A Kitty window is a plain login shell, an SSH
login is a plain shell, and herdr is started by typing `herdr`. That deletes the
whole guard list autostart needed — the `$-`/`-t` tests for scp and rsync,
`SSH_ORIGINAL_COMMAND`, `TERM_PROGRAM`, and the `HERDR_ENV` guard that the pty
crush cost — because none of those contexts can accidentally launch a
multiplexer any more.

| Piece | Before | During the trial |
|-------|--------|------------------|
| Kitty `shell` | `zjshell`, so every window was a Zellij session | `.`, a plain login shell |
| SSH login | `# === Zellij on SSH ===`, autostart into session `main` | plain shell; run `herdr` when wanted |
| Server lifetime | Zellij's own daemon, started by the first client | `herdr-server.service`, a systemd user unit |
| Opting out | `ZELLIJ_AUTOSTART=0` | `ZELLIJ_AUTOSTART=1` restores the Zellij autostart |

### Attaching

herdr is one server per machine; a workspace cannot be bound to a remote host.
`herdr workspace create` and `herdr pane split` take `--cwd`, `--label` and
`--env` and no `--host`, and [the docs](https://herdr.dev/docs/how-to-work/) are
explicit that panes keep running in the server and workspaces do not map to
hosts. A pane can run `ssh`, but splitting it gives a local shell again. Three
machines is three servers.

| Want | Do |
|------|-----|
| Work on this machine | `herdr` |
| Work on a remote machine | `herdr --remote <host>` — local thin client, remote server; the only path that bridges this desktop's clipboard, image paste included |
| Already in an SSH shell, or on a phone | `ssh <host>` then `herdr` — herdr runs entirely on the far end and cannot read this desktop's clipboard |

Two `--remote` papercuts worth knowing:
[#1931](https://github.com/herdrdev/herdr/issues/1931) does not refresh
`SSH_AUTH_SOCK` when you detach and reconnect, and
[#3422](https://github.com/herdrdev/herdr/issues/3422) renders Kitty graphics as
a black box unless `SSH_TTY=/dev/tty`.

### Why the server is a systemd unit

herdr spawns its server as a child of the first client, so it inherits that
client's cgroup — `kitty-<pid>-<n>.scope` locally, or the sshd session scope on a
remote box. systemd tears those down when the window closes or the connection
drops, taking the server and every pane with it, which is the exact failure a
persistent server exists to prevent
([herdrdev/herdr#1762](https://github.com/herdrdev/herdr/issues/1762)). `setsid`
does not help: the server is already a session leader and still inside the doomed
cgroup.

`herdr-server.service` owns it instead, so it starts at login under `app.slice`
and no terminal's lifetime reaches it. This matters more on remote machines than
locally: a manually started `herdr` on the far end of an SSH connection dies with
that connection, which is the opposite of the reason for SSHing into a persistent
server.

```bash
systemctl --user status herdr-server.service     # verify
systemctl --user restart herdr-server.service    # after a unit change; panes do not survive
```

The unit sets `PATH` explicitly, because panes inherit the server's environment
and the systemd user environment has neither pixi nor `~/.local/bin` on it. Pane
shells are login shells and rebuild `PATH` from `.bash_env` anyway, so this is for
herdr's own agent detection, which shells out to the binaries it looks for.

### Clipboard

Two different paths, and only one of them depends on the server's environment.

**herdr's own copy** — mouse select with `ui.copy_on_select` (default on), and
copy mode's `v`/`y` — runs in the *client*, so it uses the environment of the
terminal you are attached from. Nothing about running the server under systemd
changes it. This is also why `herdr --remote` can bridge a local desktop
clipboard to a remote server while `ssh host` then `herdr` cannot: in the first
the client is local, in the second the whole thing runs on the far end.

**Programs inside panes** that talk to the display themselves — `xclip`,
`wl-copy`, an agent pasting an image — inherit the *server's* environment, which
is fixed at server start and does not follow a reattach
([herdrdev/herdr#2448](https://github.com/herdrdev/herdr/issues/2448): panes show
no `DISPLAY` after reattaching, while the terminal that attached has one).

That bug is mostly a Wayland problem and this desktop is largely immune: XFCE
imports `DISPLAY=:0` and `XAUTHORITY=$HOME/.Xauthority` into the systemd user
environment at session start, the unit inherits both, `:0` is stable on a
single-seat box, and `~/.Xauthority` is a fixed path rather than a per-session
file under `/run`. `run_onchange_enable-herdr-server.sh.tmpl` re-imports them
anyway, so the unit does not depend on the session having done it.

`clip` is immune either way. It tests the *display* rather than the binary and
falls through to OSC 52 on `/dev/tty` when there is no usable one — the same
design that makes it work inside a devcontainer, which turns out to cover this
case for free. Neovim's OSC 52 provider is in the same position. What would
break, if the display environment ever were missing, is a bare `xclip` in a pane.

There is no config option to force OSC 52 — the only clipboard settings are
`ui.copy_on_select` and the copy toast — so the server's environment is the
mechanism, not a preference.

### Known risk, not mitigated

[herdrdev/herdr#3415](https://github.com/herdrdev/herdr/issues/3415): panes are
SIGHUP'd before server shutdown on reboot, `persist.clear` fires, and the whole
session record is lost. There is no user-side workaround, and no herdr equivalent
of Zellij's `session_serialization`. The unit's `ExecStop` asks herdr to stop
itself first, which is the ordering the bug report says is missing — but that is
an educated guess at a mitigation, not a fix, and a reboot may still cost the
layout.

### Reverting

1. `ZELLIJ_AUTOSTART=1` in `~/.bash_env.local` to test the revert on one machine.
2. Everywhere: flip that default in `private_dot_bash_env`, and point `shell` back
   at `zjshell` in `dot_config/kitty/kitty.conf.tmpl` (the path is in a comment
   on the line above).
3. `systemctl --user disable --now herdr-server.service`.

If the trial is adopted instead, the removal list is `[envs.zellij]` in the pixi
manifest, the five WASM plugin externals in `.chezmoiexternal.toml` (which also
ends the 8.4MB re-fetch per container create), `~/.config/zellij/**` via
`.chezmoiremove.tmpl`, the `zj*` scripts, and the Zellij half of this README.

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
| `F2` | New tab (byobu) |
| `F3` / `F4` | Previous tab / next tab (byobu) |
| `F5` | [Open the scrollback in an editor](#copying-text-with-the-keyboard) to select and copy text with the keyboard; `:q` returns |
| `Shift+F5` | Leap between projects: jump to any session by name |
| `F6` | Detach (byobu): closes the window, ends an SSH connection, session stays |
| `F7` | Quit: end this session; resurrectable, so a mis-hit is recoverable |
| `F8` | New pane |
| `F9` | Jump to a tab by name |
| `F10` | Close the focused pane, no confirmation; cascades to the tab, then the session, when it is the last one |
| `F11` | Agent picker |
| `F12` | Control-mode gateway |
| tab shows `⏳` / `✅` | A Claude pane in that tab wants input / has finished |
| bar shows `N sessions, M dead` | The session list has grown past the threshold — run `zjclean` |

During the [herdr trial](#multiplexer-trial-herdr) the keys above are Zellij's and
do not apply; herdr uses a `Ctrl+b` prefix instead:

| Key | Purpose |
|-------|---------|
| `Ctrl+b ?` | List every active binding, `/` to filter — replaces `zj-which-key` |
| `Ctrl+b h/j/k/l` | Move focus between panes |
| `Ctrl+b g` | Goto picker: jump to a session or workspace — replaces `zellij-leap` |
| `Ctrl+b w` | Workspaces |
| `Ctrl+b [` | Copy mode: vim motions, `/` search, `v`/Space to select; does not pause the pane |
| `Ctrl+b q` | Detach; the server and panes keep running |
| pane marked working / blocked / idle | herdr's own agent state — replaces the `⏳`/`✅` tab markers and `zellij-attention` |

Applications inside Zellij do not see `F1`-`F11`; `Ctrl+; d` hands them back
(`F12` returns), and `Ctrl+; o a` does the same while also suspending autolock
for a long-lived TUI (`Ctrl+; o A` restores it). Locked mode does *not* pass
function keys through — a bare `shared` block covers every mode, Locked included.

**Leaving a session** — three levels, and only the last shrinks the list:

| | Keys | Processes | Record |
|---|------|-----------|--------|
| Detach | `F6`, `Ctrl+; o d`, closing the window | keep running | stays, live |
| Quit | `F7`, `Ctrl+; o x`, `exit` in the last pane | killed | stays, `EXITED` |
| Delete | `Ctrl+; o X`, `zjclean` | killed | gone |

The full modal layer remains available for everything else:

| Command / key | Purpose |
|-------|---------|
| `zj` / `Ctrl+; w` | Create or open a workspace from a project dir or worktree, without the noisy full zoxide history |
| `zjclean` | Prune accumulated sessions; shows pane and tab counts, Tab marks several |
| `zjclean --dead` | Delete every `EXITED` session unattended; live ones untouched. Also sweeps empty session dirs |
| `zjclean --stale [N]` | Delete `EXITED` sessions last serialized over N days ago (default 7); the one that is safe to automate |
| `Ctrl+; o n` / `zjname` | [Name this session](#naming-a-session) after the project in the focused pane — `Zellij (chezmoi)` instead of `Zellij (sincere-petunia)`. `Ctrl+; o N` prompts instead; `zjname <name>` sets one by hand |
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
| `Ctrl+; o` | Session operations; `w` manager, `n` name after the current project, `N` name by prompt, `d` detach, `x` quit, `X` quit and delete, `q` lock (F12 unlocks) |
| `Super+T` / `Ctrl+Alt+T` | Open Kitty from the desktop via XFCE's TerminalEmulator helper (`gui` profiles) |
| new Kitty window | Already a fresh single-pane Zellij session (`shell` is `zjshell`) |
| `ssh <host>` | Attaches to a persistent `main` session there, from any device; `ZELLIJ_AUTOSTART=0` opts out, `ZJ_SSH_PER_CLIENT=1` gives a session per client machine |
| `Ctrl+Shift+T` / `Ctrl+Shift+Enter` | Open another Kitty OS window at the Zellij workspace picker |
| `Ctrl+Shift+Y` | Open a Kitty window with a **plain** login shell, no Zellij — SSH from here so the remote Zellij is the only one |
| `Ctrl+Shift+R` | The same plain window, straight into `sshz`: pick a host, `exec ssh` — remote keys are then identical to local ones |
| `sshz [host]` | The picker on its own; hosts come from `~/.ssh/config` and the `ssh` lines in history |
| mouse wheel | Scroll the focused pane without entering a mode; a drag also copies, `copy_on_select` being on |
| `zellij action dump-screen /dev/stdout \| clip` | The whole pane to the clipboard without selecting; `--full` adds the scrollback |
| `cmd \| clip`, `clip file` | Copy to the clipboard from any shell, host or container — xclip where there is a display, OSC 52 where there is not |

The focused pane's frame is **magenta** in normal mode and **cyan** while the
`Ctrl+;` layer is active; every other pane keeps a plain white frame. Zellij will
not let a theme colour unfocused frames — they always use the terminal's default
foreground — so the focused pane has to win on hue, which is why the bundled
`blade-runner` theme is re-declared as `blade-runner-focus` in
`dot_config/zellij/config.kdl.tmpl` with just those two colours changed.

Use a separate Git worktree and Zellij workspace for agents that may edit in
parallel. Multiple agents inside one workspace share one working tree and are
best used for coordinated roles such as implementation plus review.

### Neovim
Stock LazyVim plus the language extras listed in
`dot_config/nvim/lazyvim.json`. That file is chezmoi-managed, so the extras
list is version-controlled and arrives on every machine — but `:LazyExtras`
writes to the *applied* copy, so toggling an extra in the UI shows up as
chezmoi drift. Edit the source file and `chezmoi apply --force` instead.
Leader is `Space`. `<leader>` then a pause pops which-key; `<leader>sk`
fuzzy-searches every live keymap, which beats this table when it drifts.

**Find and search** — the three habits that carry over from VS Code:

| Key | Purpose |
|-------|---------|
| `Ctrl+P` | Fuzzy-open a file, rooted at the project (VS Code's `Ctrl+P`; same picker as `<leader><space>`) |
| `<leader>/` | Grep the whole project (VS Code's `Ctrl+Shift+F`) |
| `<leader>sw` | Grep the word under the cursor |
| `<leader>e` | File tree, rooted at the project |
| `Ctrl+Q` *in any picker* | Send **all** matches to the quickfix list |
| `]q` / `[q` | Walk the quickfix list |
| `<leader>sR` | Reopen the last picker with its query intact |
| `<leader>sb` | Fuzzy-search lines within the current file |
| `<leader>sB` | Grep across open buffers only |

**Navigate by structure** — needs a language server, hence the extras:

| Key | Purpose |
|-------|---------|
| `gd` | Go to definition |
| `gr` | References |
| `gI` | Implementations |
| `gy` | Type definition |
| `K` | Hover docs |
| `Ctrl+O` / `Ctrl+I` | Back / forward through the jumplist |
| `]f` / `[f` | Next / previous function |
| `]c` / `[c` | Next / previous class |
| `]a` / `[a` | Next / previous argument |
| `<leader>cs` | Symbol outline for the file (Trouble) |
| `zM` / `zR` / `za` | Fold all / unfold all / toggle one fold |
| `s` | Flash: type 2 chars, then a label letter, to jump anywhere on screen |

**Read a diff** — walking what an agent just changed:

| Key | Purpose |
|-------|---------|
| `]h` / `[h` | Next / previous changed hunk |
| `<leader>ghp` | Preview the hunk inline |
| `<leader>gb` | Blame the current line |
| `<leader>gf` | History of the current file |
| `<leader>gg` | Floating Lazygit |
| `gx` | Open the URL or filepath under the cursor |

**Editing**, for when it comes up:

| Key | Purpose |
|-------|---------|
| `Ctrl+/` | Toggle comment (normal, visual, insert) |
| `cif` / `daf` | Change inside / delete around the enclosing function |
| `cia` / `daa` | Change inside / delete around an argument |
| `ci"` / `da(` | Change inside quotes / delete around parens |
| `<leader>sr` | Project-wide find-and-replace in a live buffer (grug-far) |
| `.` | Repeat the last change |

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

### Code review
Three review skills that share one body of review content. `~/.claude/review-core.md` holds the whole review — what to attack (boundaries, error paths, untested branches, interaction with unchanged code, lifetimes, concurrency, wire compatibility, resources), how to prove a finding as concrete inputs → wrong result and then try to refute it, when to run `/constructive-modeling` over changed types, comment verbosity, and the bar for what counts. Both review skills read that file, so the review is identical either way; each `SKILL.md` is only the half that differs — the **output**. Either one runs as two parallel subagents on independent axes: **Defects** (the adversarial read) and **Spec** (conformance against the ticket the PR closes). The spec is resolved deterministically and never asked for — where nothing resolves, the axis reports *no spec available* and is skipped, because a spec reconstructed from the diff grades the diff against itself and always passes. Correctness ranks first wherever a cap or a reader’s attention has to be spent.

| Command | Purpose |
|-------|---------|
| `/review-self [branch\|PR]` | Your own branch. A finding is not something to report, it is something to fix: failing test first, red then green, one commit per defect naming the failure. Then drives the PR's CI to green — a red check needs no further proof, but a job already red on base is left alone rather than buried in your diff, and green is never bought with an `xfail`, a loosened assertion, a lint ignore, or a re-run. Never comments, never amends or force-pushes, and escalates rather than redesigning when the only honest fix is a different design. |
| `/review-other [branch\|PR]` | Someone else's PR, read-only. Posts one batched review as `event: COMMENT` — never `--approve`/`--request-changes`, that is the human's call — capped at five inline comments, ranked correctness first. Nothing qualifying is a real result: post the summary alone. |
| `/respond [branch\|PR]` | Address every unresolved review thread — fix the code, push, reply inline saying what changed. |

Comment verbosity is treated as correctness, not style: a comment that narrates the next line, or that this diff just falsified, is a claim that goes stale and then lies. Scoped to the diff — neither skill sweeps the file, and neither trades a correctness finding for a comment one.

### Writing
| Command | Purpose |
|-------|---------|
| `/unslop` | Strip AI tells from prose, then add voice back. 31 numbered patterns to detect and fix: puffery, AI vocabulary ("crucial", "delve", "tapestry"), "not just X, but Y", rule of three, em dashes, inline-header lists, title-case headings, hedging, abstract metaphor nouns ("substrate", "vector", "API surface"), passive voice, adverbs propping up weak verbs. Ends with a self-audit pass: "what makes this obviously AI generated?" |

Vendored from [cursor/plugins](https://github.com/cursor/plugins/blob/main/pstack/skills/unslop/SKILL.md) (`pstack/skills/unslop`). The body is verbatim; the one local change is the `description:` line. Upstream's reads "Must always apply", which suits Cursor, where the plugin is always on. Claude Code picks skills by matching that line against the task, so it lists the prose it applies to instead. A refresh is a re-download of that one file plus that one line.

### Wayfinding
For efforts too big for one agent session and too foggy to spec. `/wf` charts the work as a map issue (`wayfinder:map`) with child **decision tickets** on GitHub Issues (sub-issues + native blocked-by; falls back to local markdown in `.wayfinder/`), then resolves them one per session until the way is clear. Planning, not doing — tickets settle questions, not work slices.

| Command | Purpose |
|-------|---------|
| `/wf <loose idea>` | Chart a map: name the destination (via `/grill-me`), create the frontier tickets, sketch the fog, fire research subagents. One session, no resolving. |
| `/wf <map # or URL>` | Work the map: claim one frontier ticket (or resume a claimed one you name — it re-enters from the ticket's breadcrumb trail), resolve it, record the answer, graduate the fog. One ticket per session. Sessions journal `**breadcrumb:**` comments at decision points and a `### handoff` comment on deliberate exit. |
| `/wf-mid <idea \| map>` | Between the two: every decision gets an honest attempt against the same **principles** first, and only the ones that survive the **escalation test** — the legwork is done, the principles genuinely don't settle it, and the call is taste, expensive to reverse, redraws the destination, or contradicts a recorded decision — reach you, as a one-question **decision brief** with a recommendation and the cost of being wrong. "Your call" is a valid answer. Planning by default like `/wf`; execution is in scope only where the map's `## Notes` or a `steer:` line grants it. |
| `/wf-auto <idea \| map>` | The same map with nobody in the loop and execution in scope: decisions settle against declared **principles** instead of a grilling, and one run drives the map — decision tickets and `wayfinder:build` slices alike — to approved work. |
| `/wf-one <task>` | Known work, no planning: a **single-ticket map** filed before the work starts, so it shows in `wf` and resumes across sessions, still built via `/wf-tdd` and reviewed in fresh context via `/wf-review`. Never gets a second ticket — if it wants one, it was never single-ticket work. |
| `/research <question>` | Background subagent reads primary sources, writes cited findings to a Markdown file in the repo. |
| `/prototype <question>` | Throwaway artifact to react to: logic/state-model questions get a tiny TUI; "what should it look like" gets 3 switchable UI variants. |

Ticket types: `research` (AFK subagent), `task` (unblocks a decision), `grilling` (default — `/grill-me` + `/constructive-modeling`), `prototype`, and `build` (an execution slice via `/wf-tdd` then `/wf-review`, whose stage is derived from its PRs).

Four ways in, split on **who decides** and **how much fog**: `/wf` when the fog needs *you* in the loop (planning only — tickets settle questions, then it hands off); `/wf-mid` when you want the obvious calls taken for you and the one or two that are genuinely yours put to you properly (the same principles, plus an escalation test that decides which is which, and close calls recorded as close calls, so re-deciding an agent-decided ticket later is normal rather than a conflict); `/wf-auto` when there's fog but you'd rather not be asked at all (principles in priority order — maintainability → simplicity → constructive modeling → test-first, extendable per map in its `## Notes` — with every resolution marked `**agent-decided:**` / *(agent)*); `/wf-one` when there's no fog at all and you just want the work tracked, resumable and gated. All four share the same tracker mechanics and the same `/wf-tdd` → gate → fresh-context `/wf-review` lifecycle, and all four park with a `### handoff` rather than guess when a call needs human hands, contradicts a recorded decision, redraws a destination you wrote, or would merge. The line between the middle two is what an unanswered question does: in `/wf-mid` an earned escalation that goes unanswered parks the ticket and the run moves to other unblocked work, where `/wf-auto` would decide it alone.

`wf` ([blooop/wayfinder](https://github.com/blooop/wayfinder)) is the way in from the shell rather than from a Claude session: one fuzzy-find picker over the tickets of *every* mapped project on the machine, so you choose the work before choosing the session. Projects accrete zoxide-style — running `wf` in a checkout registers it — and the picker opens focused on the checkout you are standing in.

| Key | What it does |
|-------|---------|
| `wf` | Open the picker. Every open map renders as its own cluster, takeable tickets first with the subtree each one unblocks; `tab` swaps to the full blocking forest, `ctrl-f`/`ctrl-g` narrow to one project or widen to all, `ctrl-r` refreshes. |
| `↑`/`↓`, `←`/`→` | Move between siblings, and in and out of subtrees. `↑` from a cluster's first row lands on the **map itself**, which is a thing you can launch. |
| `enter` | Open the **launch picker** over the list: it names the agent and shows a row per mode — `interactive` (the skill the node's type and stage resolve to: `/wf`, `/wf-tdd`, `/wf-review`), `mid` (`/wf-mid`), `auto` (`/wf-auto`), `plain` (a bare session, no skill), plus `resume` when the node has a conversation to pick back up. |
| `↑`/`↓`, `←`/`→`, *type* | On the launch picker: pick the mode, switch the agent between Claude and Codex (the route column follows, `/wf` vs `$wf`), and type to fill the `steer` field. A second `enter` execs it in the checkout, *replacing* `wf`: the picker is gone by the time the agent draws. `esc` backs out. |

Installed via pixi-global like every other tool (published to prefix.dev/blooop), so it arrives on each machine at the next `pixi global sync`.

**The wayfinder skills ship inside that package.** `wf` hardcodes all six — `/wf`, `/wf-mid`, `/wf-auto`, `/wf-one`, `/wf-tdd`, `/wf-review` — in its routing table and execs them, so those prompts are part of its interface and live in [blooop/wayfinder](https://github.com/blooop/wayfinder) under `skills/` — not in this repo. `pixi global update wf` moves the binary and its prompts together, and `run_onchange_after_link-wf-skills.sh` runs `wf skills install` to symlink them into `~/.claude/skills`. `wf skills` reports which prompt each route would actually run. To edit a skill against a released `wf`, point it at a checkout: `WF_SKILLS_DIR=$PWD/skills wf skills install`.

A map stays in the repo it maps: the target repo is resolved once from that repo's own `origin`, named to you before the first write, and passed as `--repo` on every `gh` call — never left to `gh`'s ambient resolution, which follows cwd, `gh repo set-default`, and a fork's parent.

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
| `claude-login` | Sign into Claude Code through the saved Chrome profile; after clicking Copy code, it submits the code to the terminal. `--auto-copy` uses an isolated profile to click Copy automatically. |

`.bash_env` exports `CLAUDE_CONFIG_DIR=$HOME/.claude`, which moves
`.claude.json` — the logged-in account and per-project history — from
`~/.claude.json` into the config directory itself. That directory is what
devlaunch bind-mounts into every container, so the file has to be inside it for
the host and its containers to agree on who is logged in; left at the default
they share one set of credentials while reading two different account records.
Nothing else moves, and a container that sets the variable itself keeps its own
value. The trade is that every session now writes one file, so simultaneous
exits can lose a project's history — see the comment in `private_dot_bash_env`.

**Skills come from three places.** Hand-written ones live in this repo under
`private_dot_claude/skills/`; the six wayfinder prompts ship inside the `wf` package
(above); and 21 of [Matt Pocock's](https://github.com/mattpocock/skills) 25 promoted
skills come from `.chezmoiexternal.toml`, as one `archive` external per skill
extracted straight into `~/.claude/skills`. Four upstream skills are skipped as
collisions: `wayfinder`, `to-tickets`, `to-spec` and `implement` duplicate the wf map
spine, and `code-review` collides by name with Claude Code's built-in. Gated on
`.claudecfg` — which means "chezmoi owns `~/.claude` here", not "this is not a
container". See [Who owns `~/.claude`](#who-owns-claude).

Each stanza's `include` is written against the tarball's own layout — a
`skills-<ref>/` top directory, hence the leading `*/` — and `stripComponents = 4`
discards `skills-<ref>/skills/<bucket>/<name>/`, which is what flattens upstream's
bucket directories away so `engineering/tdd` lands as `skills/tdd`. All 21 name the
same tarball — pinned to a commit sha, so it is fetched once and cached, not 21
times; a warm apply re-extracts from the cache in about 150ms.

These were briefly a single `git-repo` clone plus a script that symlinked each skill
out of it, which is worth recording because it cost more than it appeared to. The
clone was a second copy of every skill; a skill dropped from the list left a real
directory that the link script then refused to clobber, so the orphan blocked its own
replacement and printed a "needs a decision" notice on every apply; and clearing
those orphans needed `.chezmoiremove` entries individually guarded against deleting
the very symlinks the script had just created — an unguarded entry removed the stale
directory on the first apply and the replacement symlink on the second, with
`run_onchange` declining to re-run because its hash had not changed. As externals
none of that arises: every skill is an ordinary managed path, and chezmoi replaces
whatever sits there, symlink or directory, unaided.

`.chezmoiremove.tmpl` covers what is left, because a departure is still not
self-cleaning: dropping an external's entry leaves its extracted files behind exactly
as deleting a source file leaves the applied copy behind. It currently retires the
abandoned `~/.claude/mp-skills` clone and three skills that a rename and a deletion
left stranded. Entries stay guarded on *not* being a symlink even though none of them
is one today, since `run_onchange_after_link-wf-skills.sh` still links the six wf
prompts into that same directory and deleting one would be silent and permanent.

### Codex CLI
| Alias | Command |
|-------|---------|
| `cdy` | `codex --yolo` |

### Dev Containers (dl / aid)
[devlaunch](https://github.com/blooop/devlaunch) opens a repo's own devcontainer as a devpod workspace — one per branch, each with its own clone, so several agents work at once without sharing a tree. It forwards the host's `gh` token in as `GH_TOKEN`, defaults to `--ide none` so nothing opens over the terminal, and handles git-lfs. `aid` is the same thing with a coding agent already started. `toolbox` machines only — never inside a container, which is where it *sends* work.

| Command | Purpose |
|-------|---------|
| `dl <owner/repo>` | Open (creating if needed) the workspace for a repo's default branch and attach a shell |
| `dl <owner/repo>@<branch>` | Same, on a branch — its own clone and container, created locally off the default branch if the branch is new |
| `dl <path>` | Open a checkout already on disk |
| `dl <workspace> -- <cmd>` | Run one command in the workspace instead of attaching (a shell line, not an argv — quote what must stay one word) |
| `dl <workspace> up` | Start or create the workspace without attaching; `wf` uses this to warm a container while you are still choosing (needs devlaunch ≥ 0.0.24) |
| `dl --purge` | Remove devlaunch's clones and the workspaces made from them, naming anything that refused |
| `aid <workspace> [prompt]` | `dl … -- claude --dangerously-skip-permissions '<prompt>'` — the workspace with an agent in it |
| `dl-next`, `aid-next` | The working tree of a devlaunch checkout (`./dev.sh`), kept under separate names so the released `dl` stays the one that opens real workspaces |

`wf` shells out to `dl` for the same reason: a ticket whose checkout declares a `.devcontainer/devcontainer.json` launches its agent in a container instead of on the host, and says `(devlaunch)` in the launch notice when it does. No `dl`, or one older than the version that `wf` build needs, and the launch runs on the host with the reason stated.

**zellij is not installed into workspaces**, and from devlaunch 0.15.0 nothing here has to say so. The setup pass used to install zellij into every workspace it created, which these dotfiles did not want: zellij sits behind `toolbox`, off for the container profiles, and nothing in a workspace multiplexes anything — `dl` attaches a single shell, and the multiplexer that matters is the host's, outside the container. [devlaunch#425](https://github.com/blooop/devlaunch/pull/425) made that stage opt-in, so skipping is the default and `DEVLAUNCH_ZELLIJ=1` is the one thing that asks for the install. Before 0.15.0 this took a `DEVLAUNCH_NO_ZELLIJ=1` export from `.bash_env`; that variable is retired and read by nothing, and the export is gone. A machine still pinned below 0.15.0 needs it back, or its workspaces get zellij again.

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

### DevPod Workspaces (dl, dl-sandbox)
`dl` ([blooop/devlaunch](https://github.com/blooop/devlaunch)) opens a DevPod workspace for a repo, cloning it first if needed. It shares the `devpod` pixi-global env rather than getting one of its own — it depends on devpod, so a second env would install a second copy of it — which means `pixi global update` covers both.

| Command | Purpose |
|-------|---------|
| `dl <owner>/<repo>` | Clone if needed and open a workspace on the default branch |
| `dl <owner>/<repo>@<branch>` | Same for one branch — each branch is its own workspace |
| `aid <owner>/<repo>[@branch] [prompt...]` | The same workspace with a coding agent started in it — `aid` rewrites itself into `dl ... -- claude '<prompt>'`, so it is a shortcut rather than a second launcher (`--codex`/`--gemini` pick another agent) |
| `dl-next ...` | The same tool built from a working copy of the repo, installed alongside by its `dev.sh`. Never shadows `dl`. |
| `dl-sandbox ...` | Run `dl-next` against throwaway state in `~/.cache/dl-sandbox` instead of the real workspace list |
| `DL_SANDBOX_BIN=dl dl-sandbox ...` | Sandbox the released build instead |

`dl` keeps everything it knows — `metadata.json`, the bare clones, `config.toml` — behind `XDG_CACHE_HOME` and `XDG_CONFIG_HOME`, so redirecting those is the whole sandbox. It is not a container: `dl` drives devpod and docker on the host, so what gets isolated is the state, not the machine, and the workspaces a sandboxed run creates are still real ones that `devpod list` shows and that need deleting like any other.

The `dl`/`dl-next` split is the same one `wf` and `wf-next` use: the released build stays on PATH and keeps working while a checkout is mid-change, and the working copy lives beside it under a name that cannot be confused for it.

### Kinisi Dev Containers
`kinisi_ros` containers are created by `kinisi_env start` (which owns X11/NVIDIA/privileged mode) and install nobody's dotfiles. `container/bootstrap.sh` adds them on top; `install.sh` runs it automatically on the DevPod path, and otherwise you run it by hand. It is idempotent and near-instant once the shared pixi root exists, so re-running it is also how you recover after a dotfiles change breaks something. See [Development Containers](#development-containers) for what it does and does not touch.

| Command | Purpose |
|-------|---------|
| `docker exec <container> bash -c 'bash "$HOME/.local/share/chezmoi/container/bootstrap.sh"'` | Bootstrap dotfiles into a running kinisi container |

The status line does **not** need this — `~/.claude/statusline.sh` resolves the binary through the `~/.local/share` mount on its own. Everything else interactive (fzf keybindings, zoxide, broot, forgit, the prompt, `~/.bash_aliases`) does.

Personal pixi globals for containers live in `container/pixi-global.toml` (separate from the host manifest, no capability gating). `pixi global sync` is declarative — it removes envs not listed there.

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

For containers you launch yourself (rocker with user mapping), mount the host cache to skip the bootstrap entirely: `-v ~/.local/share/ags:/home/$USER/.local/share/ags`. Requires a glibc-based image.

The username and home path no longer have to match. Pixi's exposed-command trampolines record an absolute prefix, so one cache reached at two paths (say `/home/you/...` on the host and `/home/kinisi/...` in a container) used to leave every exposed command failing with ENOENT on whichever side did not bootstrap it — environments intact, launchers pointing nowhere, and `.installed` already set so nothing repaired it. `ags` now reads one trampoline on startup and, if the recorded prefix is not the current `$AGS_HOME`, re-exposes the manifest with `pixi global sync` (no network needed; the environments are already installed). Switching sides costs one re-expose; staying put costs a single file read. Note this happens **inside** the kinisi containers too, since they bind-mount `~/.local/share` — which is exactly why the container pixi root is deliberately container-only and cannot hit this.

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

- `~/.bash_env.local` — sourced from `~/.bash_env`, in its environment half, so it reaches non-interactive shells too (per-machine env vars, e.g. `WS_EXCLUDE`)
- `~/.gitconfig.local` — included from `~/.gitconfig` (per-machine git config, e.g. the `gh` credential helper)

## Troubleshooting

### The Zellij status bar is blank

**Symptom:** the bottom row is empty. No legend, no mode indicator, no error —
and `zellij.log` cheerfully reports `Loaded plugin '.../zjstatus.wasm'` for every
session, so nothing looks wrong.

There are three causes, and they are told apart by what changes the outcome.

**1. The permission prompt with nowhere to draw.** Zellij asks for consent the
first time a plugin requests a permission and renders that prompt *inside the
plugin's pane* — which here is one borderless row, so the prompt is invisible and
the plugin waits forever. Check for an entry in `~/.cache/zellij/permissions.kdl`:

```bash
grep -A4 zjstatus ~/.cache/zellij/permissions.kdl
```

No entry, or an entry missing one of `ReadApplicationState`,
`ChangeApplicationState`, `RunCommands`, is the fault.
`run_onchange_after_grant-zjstatus-permissions.sh` writes it on every apply, so
`chezmoi apply --force` fixes it; new sessions pick it up immediately, and an
existing one needs
`zellij action start-or-reload-plugin "file:$HOME/.config/zellij/plugins/zjstatus.wasm"`.

This re-arms itself whenever the bar starts asking for a permission it did not
ask for before — adding `command_sessions_command` pulled in `RunCommands` and
darkened the bar on a machine where it had worked for weeks. Widen the list in
that script alongside the change.

**2. The window is in the dead band.** The bar needs
`2 × len(format_left) + len(format_center)` columns and draws nothing below it.
Resize the window much wider — or much *narrower*, which also works and is the
tell, since a truncation path takes over near 100 columns. See
[The status bar](#the-status-bar).

**3. The session predates the current legend.** Not blank but *stale* — old keys
in the right places. A resurrected session replays its serialized layout, zjstatus
block included. `Ctrl+; X` (not `F7`) rebuilds it; see
[What "attach to resurrect" means](#what-attach-to-resurrect-means).

### Lost SSH config entries after a sync

**Symptom:** manually-added `Host` blocks disappear from `~/.ssh/config`, seemingly around the time you ran `chezmoi apply` / `/sync`.

**Cause:** not chezmoi. This repo does **not** manage `~/.ssh/config` (`chezmoi managed` lists no ssh files, and the file has never been in git history), and `chezmoi apply` never touches unmanaged files. The real culprit is **DevPod**, which rewrites `~/.ssh/config` in place every time a workspace is created, recreated, or deleted. It inserts/prunes blocks between `# DevPod Start <ws>` / `# DevPod End <ws>` markers, and when those markers get unbalanced (e.g. an orphaned `Start` with no matching `End`) a prune can delete everything down to the next marker — taking your hand-written entries with it. The chezmoi correlation is indirect: `install.sh`'s devpod configuration step and `dl`/devpod activity tend to happen right after a sync, and that's what rewrites the file.

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

### `git` stops authenticating over HTTPS after a `/sync`

**Symptom:** git operations against github.com over HTTPS start failing — `fatal: could not read Username for 'https://github.com'`, or an interactive password prompt in a place that never had one. `gh auth status` still reports `✓ Logged in`, and `gh api user` still works, so the token is fine. Only git is broken.

**Cause:** `/sync` step 3 runs `chezmoi apply --force`, and `~/.gitconfig` is chezmoi-managed (`dot_gitconfig.tmpl`). `gh auth setup-git` writes its credential helper into the **global** gitconfig — which is that exact file — so the apply rewrites it from the template and the helper section is gone. Nothing flags it: `chezmoi status` is clean afterwards, because the file now matches the source. `chezmoi diff` before the apply would have shown it, but only as an unexplained deletion.

The `container` profile is immune (`.chezmoiignore.tmpl` skips `.gitconfig` there, in favor of the XDG fallback). Every other profile is exposed.

**Fix — write the helper to the untracked include, not the managed file:**

```bash
GH=$(command -v gh)
for h in github.com gist.github.com; do
  git config --file ~/.gitconfig.local --replace-all "credential.https://$h.helper" ""
  git config --file ~/.gitconfig.local --add        "credential.https://$h.helper" "!$GH auth git-credential"
done
```

The empty first `helper` is gh's own convention — it resets any helper inherited from a wider scope before adding its own. Verify:

```bash
printf 'protocol=https\nhost=github.com\n\n' | git credential fill
```

That should print `username=` and `password=` lines. `git ls-remote https://github.com/<owner>/<repo> HEAD` is the end-to-end check.

**Hardening:** never run bare `gh auth setup-git` on a chezmoi-managed machine — it targets `~/.gitconfig`, which `chezmoi apply --force` owns, so the next `/sync` silently reverts it. `~/.gitconfig.local` is untracked on purpose (see the `[include]` at the bottom of `dot_gitconfig.tmpl`) precisely so machine-local credentials survive an apply.

Note that the helper is recorded as the **absolute path** of whichever `gh` was on `PATH` when it was written (e.g. `~/.pixi/envs/gh/bin/gh`, expanded). That path embeds the current username, which is a second reason `~/.gitconfig.local` must stay out of this repo — see the no-hardcoded-`/home/<user>` rule in `CLAUDE.md`.

### `ssh` reports a broken agent instead of no agent

**Symptom:** in a container, `ssh-add -l` answers `Error connecting to agent: No such file
or directory`, and a push to an ssh remote dies with `fatal: Could not read from remote
repository`. `echo $SSH_AUTH_SOCK` names `~/.ssh/agent.sock` — and `~/.ssh` is not there.
A `bash -lc` payload in the same container has no `SSH_AUTH_SOCK` at all, so the two shell
kinds disagree about what is wrong.

**Cause:** `.bash_env` used to export the socket path first and start the agent second,
with `ssh-agent`'s stderr sent to `/dev/null`. `ssh-agent -a` does not create its socket's
parent directory, so on an image with no `~/.ssh` it failed and said nothing, leaving every
shell naming an agent that was never started. An absent agent would have been the truth;
a *broken* one sends you looking for the wrong thing.

**What it does now:** nothing is exported until something answers on the socket. An agent
forwarded into the shell is kept rather than overwritten — the old export discarded it.
`~/.ssh` is created `0700` before an agent is started there. A failure lands in
`${XDG_STATE_HOME:-~/.local/state}/ssh-agent-bootstrap.log`, truncated per attempt so it
holds the last failure rather than a line per shell, and an interactive shell also prints
one line naming it. `ssh-add`'s exit 1 means *alive, holding no keys*, so an empty agent is
no longer killed and replaced on every new shell. Keys are added with `SSH_ASKPASS_REQUIRE=never`
and stdin closed, so a passphrase-protected key fails instead of prompting in every shell
you open.

Checking it, in a container and on the host:

```bash
ssh-add -l                                    # 0 = keys, 1 = agent but no keys, 2 = no agent
[ -n "$SSH_AUTH_SOCK" ] && ls -l "$SSH_AUTH_SOCK"   # must exist if it is set at all
diff <(bash -lc 'echo ${SSH_AUTH_SOCK:-none}') <(bash -ic 'echo ${SSH_AUTH_SOCK:-none}' </dev/null)
cat "${XDG_STATE_HOME:-$HOME/.local/state}/ssh-agent-bootstrap.log"
_ssh_agent_setup; echo $?                     # re-run the bootstrap in place
```

No key material reaches a `dl` workspace by design, so a container agent holding nothing is
the expected state there; `ssh -T git@github.com` answering `Permission denied (publickey)`
is that state reported honestly. A workspace whose devcontainer bind-mounts the host's
`~/.ssh/agent.sock` (devlaunch's own does) gets the host's keys through it instead, in
both shell kinds.

### `/sync` keeps reporting drift with no content change

**Symptom:** `chezmoi diff` lists files whose only difference is a mode — `100644` vs
`100664`, `40755` vs `40775` — and nothing you do clears it. `chezmoi re-add` reports
success and changes nothing; `chezmoi apply` clears those files and the next `/sync`
reports a *different* set.

**Cause:** chezmoi takes the mode it writes from the umask of the shell that invoked it,
and nothing pinned it. Ubuntu defaults to `0002`, so an apply from a login shell writes
`664`/`775`; the same apply from a shell at `0022` writes `644`/`755`. Neither is wrong,
git records none of it — it tracks only the executable bit — so there was nothing to
commit and nothing to converge on. `re-add` re-adds *contents*, not modes, which is why
it looked like a no-op. The files that showed it were whichever ones the *other* umask
had last written; `private_` files never did, because chezmoi forces those to `600`/`700`
regardless.

**Fix:** `.chezmoi.toml.tmpl` pins `umask = 0o022`, so the mode is a property of this repo
rather than of the terminal. Confirm with `(umask 002; chezmoi diff)` and
`(umask 022; chezmoi diff)` — they now agree.

### Uncolored `user@host` in the shell prompt

**Symptom:** the `user@host:path` prompt is plain white in Kitty, but colored in gnome-terminal or Terminator.

**Cause:** Ubuntu's stock `~/.bashrc` only enables the colored `PS1` when `TERM` matches `xterm-color` or `*-256color`. Kitty reports `TERM=xterm-kitty`, which matches neither, so the non-color branch wins. Kitty's own color support is fine — it's purely the pattern match.

**Fix:** `private_dot_bash_env` sets the colored `PS1` in a `# === Prompt ===` block, gated on `tput setaf 1` (actual color support) rather than a `TERM` pattern. The `PS1` line lives in `.bash_env`'s *interactive* half, which `modify_private_dot_bashrc` always hooks in after the stock prompt block, so it overrides cleanly and covers any terminal with an unrecognized `TERM`. That ordering is the constraint: a ROS bashrc also gets an early, environment-only hook, and moving the prompt into that half hands `PS1` straight back to the block this fix exists to beat — which is exactly how it regressed once.

**If the prompt is still uncolored after that fix:** the `tput setaf 1` guard fails when the `xterm-kitty` terminfo entry is missing, so the override never fires. Check with `ls ~/.terminfo/x/xterm-kitty` and `tput setaf 1; echo $?`. This is why `.terminfo` is *not* gated on `.gui` in `.chezmoiignore.tmpl` — Kitty runs locally, but `TERM=xterm-kitty` travels over SSH into headless `shared`/`robot`/`container` boxes that need the entry just as much.

Setting `term xterm-256color` in `kitty.conf` would also work but is not used — it costs kitty-specific escape sequences (styled underlines, graphics protocol, extended keyboard) that programs discover through terminfo.
