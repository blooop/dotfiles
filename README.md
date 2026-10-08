# Dotfiles

Personal development environment configuration managed with [Chezmoi](https://www.chezmoi.io/) and [Pixi](https://pixi.sh/).

## Profiles

Every install picks a **machine profile** — the level of invasivity. The profile is
resolved once at `chezmoi init` (interactive prompt, or `CHEZMOI_PROFILE` env var, or
auto-detected from `AGS_SHELL`/`DEVPOD`), persisted in `~/.config/chezmoi/chezmoi.toml`,
and every later `chezmoi apply`/`update` uses it — no env vars needed after setup.

Profiles map to **capability flags**; templates gate on the flags, never on profile
names. The matrix lives in one place: `.chezmoi.toml.tmpl`.

| Flag | personal | shared | container | kinisi | Controls |
|------|----------|--------|-----------|--------|----------|
| `identity` | ✓ | ✗ | ✓ | ✗ | git user name/email |
| `gui` | ✓ | ✗ | ✗ | ✗ | Kitty, nerd fonts, uhk-agent |
| `heavy` | ✓ | ✗ | ✗ | ✗ | rust, nodejs, devpod, ccache, yq, lazydocker |
| `host` | ✓ | ✗ | ✗ | ✗ | git, git-lfs, openssh, curl, unzip |
| `monitor` | ✓ | ✓ | ✗ | ✗ | htop, btop |
| `agents` | ✓ | ✓ | ✗ | ✗ | codex (AI coding CLI) |
| `toolbox` | ✓ | ✓ | ✗ | ✗ | the interactive toolbox — ripgrep, fd, zoxide, broot, vim, lazygit, tuicr, xclip, prek, go, herdr, wf, devlaunch |
| `editor` | ✓ | ✗ | ✓ | ✗ | neovim + its `.config/nvim` tree; xclip (also under `toolbox`, so every profile but `kinisi` gets it) |
| `pixi` | ✓ | ✓ | ✓ | ✗ | `~/.pixi/manifests/pixi-global.toml` |
| `xdg` | ✓ | ✓ | ✓ | ✗ | `~/.config`, `~/.cache`, `~/.local/share` |
| `gitconfig` | ✓ | ✓ | ✗ | ✗ | `~/.gitconfig` |
| `claudecfg` | observed | observed | observed | observed | `~/.claude` |

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
syncing ~25 pixi envs / ~1.27GB — go, isd, vim, a second devlaunch — on every
create (a fresh container has no package cache), in order to run `claude` and `gh`. With `toolbox` off, a container installs
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
behind `editor` and lands only where it is actually driven. `shared` keeps vim: it
had no nvim before the flag existed, and a lab PC is the last place to want a
compiler.

- **personal** — your own machine: everything.
- **shared** — shared account (ags isolated shells, lab PCs): the full toolbox + system monitors + AI coding agent (codex), git identity omitted so others on the account can't impersonate you. vim, not nvim — `$EDITOR` resolves to whichever is on PATH.
- **container** — devcontainers/DevPod: the eight-env floor + nvim and its config via `editor` + the full `~/.config` tree and pixi manifest (both container-local). No toolbox — no launchers *from here*, because the only things otherwise run in a workspace are `claude` and `gh`. Identity kept, but `~/.gitconfig` is skipped in favor of the XDG fallback because DevPod overwrites it with credential injection, and `~/.claude` is skipped because `dl` bind-mounts the host's.
- **kinisi** — `kinisi_ros` dev containers: `container`, minus every path the compose files bind-mount from the host (`~/.config`, `~/.cache`, `~/.local/share`) and minus `~/.pixi`, whose manifest the image symlinks into the `kinisi_ros` checkout. Its private container manifest supplies Neovim alongside Vim without writing through those mounts. Selected only by `container/bootstrap.sh`, never prompted for.

`robot` is **retired**. It differed from `shared` in exactly one flag (`host`), which
was not worth a column; an appliance that needs git and ssh installed is a `personal`
machine without the GUI flags, and one that does not is `shared`. A machine still
carrying `profile = "robot"` is remapped to `shared` at init rather than rejected, so
it keeps applying — but it loses `host`, so re-init it as `personal` if it needs git,
openssh, curl or unzip from pixi.

Adding a new machine class = one row in the matrix in `.chezmoi.toml.tmpl`, no other
template changes.

To change an existing machine's profile, re-run init (apply alone reuses the stored one):
```bash
CHEZMOI_PROFILE=shared chezmoi init --apply
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
- every template rendered with `homeDir=/home/kinisi`, so host config that names
  `$HOME` paths points at `/home/kinisi/...` paths it cannot use.
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

# shared machine / container
curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/install.sh | CHEZMOI_PROFILE=shared bash
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

Replace `personal` with `shared` or `container` to match the machine. Omit
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
and not for fzf keybindings, zoxide or forgit. Being sourced twice is
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

A one-command *non-login* shell is a third case, and it reaches even less. `ssh host
<cmd>` gets neither `.profile` nor an interactive shell: bash reads `.bashrc` (the sshd
special case) and returns at the guard on line 8. So none of the above runs, and until
2026-09-11 every pixi tool was invisible to a remote command. Of the 93 binaries pixi
exposes on the CI host, 55 did not resolve at all and the 38 that did resolved to older
system copies. `git` was 2.43.0 over ssh and 2.55.0 in a terminal; `rg` was 14.1.0 against
15.2.0. The second group is the dangerous one, because a missing command fails loudly and
an older `git-upload-pack` serving your fetches does not.

`modify_private_dot_bashrc` therefore writes a `# One-command PATH` block *above* that
guard, on every `.bashrc` that does not already take the early `.bash_env` hook. It
prepends `~/.pixi/bin` and does nothing else. Not the environment half of `.bash_env`,
which the kinisi branch uses: that also runs `_ssh_agent_setup`, which probes with a
2-second timeout and on a miss starts an agent daemon, and every `scp`, `rsync` and
`git-upload-pack` would pay for it. Starting a daemon from inside an rsync's remote shell
is its own bug. The kinisi branch accepts the cost because that container's agent socket
is bind-mounted and already answers.

Two things resolve a binary by name over exactly this kind of shell, both correctly, and
both broke: herdr's remote bootstrap probes `command -v herdr`, and devlaunch's
`dl-herdr-shell` guards on `command -v dl` before exec'ing a pane shell, falling through
to a plain host bash when it fails. herdr closed the report as expected behavior, on the
grounds that the non-interactive `PATH` is the contract and pixi is not one of its
documented fallbacks. That is a fair reading, and it is what makes the `PATH` ours to set.

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
  - **Git** - lazygit, tuicr (code review TUI; forgit is in the floor, not here)
  - **Terminal** - herdr (multiplexer and agent workspace manager), wf (wayfinder ticket picker), devlaunch (`dl`/`aid`), vim
  - **Prompt** - [flyline](#flyline-the-prompt-line-editor), a readline replacement. The one entry here that is not a pixi package and not a program: it is a bash loadable builtin, so `.chezmoiexternal.toml` fetches a pinned `.so` and `.bash_env` `enable -f`s it
  - **Management** - prek
  - **Utilities** - go (xclip is shared with `editor`, above)
- **`host`** - git, git-lfs, openssh, curl, unzip, speedtest-go, `nvidia-upgrades` script
- **`monitor`** - htop, btop
- **`editor`** - neovim (+ full config), on personal machines and containers. 1.1GB, because nvim-treesitter compiles its parsers and so the env carries gcc/gxx; `shared` uses the toolbox's vim instead
- **`toolbox` or `editor`** - xclip, installed wherever there is an editor to yank from. It cannot work in a `dl` container — it is an X11 client and nothing forwards a display there — so nvim falls back to OSC 52 (see [Clipboard](#clipboard)) and the shell uses [`clip`](#clip-copying-from-the-shell), which makes the same choice
- **`heavy`** - nodejs, rust toolchain, devpod, lazydocker, ccache, yq (and `dl`/`aid` split their exposure with the `toolbox` devlaunch env)
- **`agents`** - codex (AI coding CLI)
- **`gui`** - Kitty, uhk-agent, JetBrainsMono nerd fonts

pixi itself is installed by `install.sh`, not by the manifest, so it is present everywhere.

## Git Configuration

The git configuration (included in DevContainers and Full installations) provides:

- **Useful aliases** - `com` (checkout main), `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push), `pushf` (push --force-with-lease)
- **Sensible defaults** - Auto-setup remotes, `push.default = simple`
- **Stacked-PR friendly** - `rebase.updateRefs` (rewrite stacked refs in one rebase) and `rerere` (remember conflict resolutions across restacks)
- **Personal credentials** - Uses Austin Gregg-Smith's git user info on profiles with the `identity` flag (`personal`, `container`); omitted on the `shared` profile so commits made by others on the account can't impersonate you
- **github.com is cloned over SSH even when the URL says HTTPS** - `[url "git@github.com:"] insteadOf = https://github.com/`, on `personal` hosts only. GitHub rejects a push touching `.github/workflows/**` when the credential is an OAuth token without the `workflow` scope, which `gh auth login` does not grant by default — so an HTTPS remote turns a workflow-file edit into a server-side rejection about scopes. SSH has no scope model. `gh repo clone` already honours `git_protocol = ssh`; this catches the hand-typed `git clone https://...` that was the only way back in

## Terminal Vibe-Coding Workflow

Kitty is only the graphical terminal frontend; [herdr](#herdr-the-multiplexer)
owns panes, tabs, workspaces and persistence. Avoid Kitty panes and tabs in this
workflow: use another Kitty **OS window** when a separate terminal is useful, and
use herdr for everything inside it.

Kitty's `shell` is `.`, a plain login shell, and an SSH login lands in a plain
shell too. Nothing autostarts a multiplexer: type `herdr` when you want one. See
[There is no autostart, deliberately](#there-is-no-autostart-deliberately).

Note that Kitty reads `shell` at startup, so after changing it an already-running
Kitty keeps handing new windows the old shell until it is restarted.

### Over SSH

**Do not nest multiplexers.** Multiplex at exactly one end, and for a remote host
that end is the remote one, because persistence across a dropped connection can
only live there. Two multiplexers one inside the other means two status bars,
doubled pane frames, and keys, mouse and clipboard that have to pass through two
emulators — and an outer multiplexer eats a key before the inner one is offered
it.

So the local terminal for such a window should not be a multiplexer session,
which is what `Ctrl+Shift+Y` is for: a Kitty window with a plain login shell. SSH
from it and the remote herdr is the only one in the stack, so every key, the
mouse, the clipboard, and the scrollback belong to it unambiguously. Since the
remote runs this same config, applied by chezmoi, the keymap is identical.
`herdr --remote <host>` is the other route, and the one that bridges this
desktop's clipboard; see [Attaching](#attaching).

`Ctrl+Shift+R` is the same window with the hostname built in: it runs `sshz`, an
fzf picker over `~/.ssh/config` and the `ssh` lines in history, which then `exec`s
the connection. Two steps beat one only in theory — the two-step version of the
right answer loses to the one-step version of the wrong one, which is SSHing from
an ordinary pane. `exec` also means the remote *is* the window's process, so
ending the remote session closes the window instead of exposing a local shell that
needs a second `exit`.

The cost is that such a window has no local splitting. Open another window
instead; `confirm_os_window_close 0` makes that cheap.

### Clipboard

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

**Inside a herdr pane the display test is not enough, and OSC 52 wins anyway.** X
has no clipboard storage: whoever owns the selection serves it on demand, and
Neovim's provider spawns `xclip -quiet -i -selection clipboard`, where `-quiet`
means *serve the selection once, then exit*. No clipboard manager runs on this
desktop to catch the handoff, so once Neovim is gone the clipboard answers exactly
one paste and is then empty — `Error: target STRING not available`. F5 sharpens it,
because `:q` also ends the pane and herdr SIGHUPs the process group behind it.
Measured, after Neovim exited:

```
read 1: [line one|line two]
read 2: [Error: target STRING not available]
xclip owners now: 0
```

So `options.lua` takes `$HERDR_ENV` as a second route into the OSC 52 branch. The
text goes to Kitty, which owns the selection and outlives every pane in the
session, and a yank then pastes as many times as wanted — verified by writing an
OSC 52 sequence to a live pane's pty and reading the clipboard back three times
for three hits. It is also the right answer under `herdr --remote`, where the
client is local and `xclip` would have reached the wrong machine's display.

### `clip`: copying from the shell

`~/.local/bin/clip` copies stdin or a file to the system clipboard, and exists
because **`xclip` is installed in containers and cannot work in one**:

```bash
cmd | clip          # copy stdin
clip notes.txt      # copy a file
```

Nothing forwards an X socket into a `dl` workspace, so `echo hi | xclip
-selection clipboard` there fails with `Can't open display: (null)` — verified in
a live workspace. `command -v xclip` still succeeds, so any pipeline that probes
for the binary picks the one tool guaranteed to fail. Until this existed, the only way
to get a container's output onto the host clipboard was a yank inside Neovim,
whose OSC 52 provider [Clipboard](#clipboard) already configures.

`clip` picks its route from the **display**, not the binary — the same test, for
the same reason, as `options.lua`. With `$DISPLAY`/`$WAYLAND_DISPLAY` and a tool
it uses `wl-copy` or `xclip`; otherwise it writes OSC 52, which travels out of
the container over the devpod pty to the terminal hosting it. A
display that is set but unusable falls through to OSC 52 rather than failing,
since a stale forwarded `DISPLAY` is exactly the case that would otherwise copy
nothing and say nothing.

It writes to `/dev/tty`, never stdout, so `cmd | clip > log` and `clip | tee`
still reach the terminal. Paste has no counterpart on purpose: Kitty denies OSC
52 *reads*, so a read request comes back empty — see [Clipboard](#clipboard).

Verified end to end from inside a `dl` workspace: `clip payload.txt` in the
container put the sentinel on the host clipboard, through Kitty.

### Copying a URL off the screen

`Ctrl+Shift+E` labels every URL on screen, and the letter you press copies that
one to the clipboard. `Ctrl+Shift+O` is the same picker but opens the URL in a
browser, which is what Kitty binds `Ctrl+Shift+E` to out of the box.

The reason it is a custom binding rather than the stock one is **wrapped links**.
Kitty's built-in URL matcher is column-aware: it stitches a URL back together
across two rows only when Kitty itself did the wrapping and marked the second row
as a continuation. A multiplexer destroys that mark — herdr, like tmux, repaints each pane row with explicit cursor positioning, so every row
reaches Kitty as its own hard line. Short links worked; long ones came back cut
off at the right-hand edge.

So `Ctrl+Shift+E` uses `--type regex` and reconstructs the mark from the padding
instead. A line ending in the text the hints kitten matches against is *zero or
more NUL bytes followed by CR or LF*: a short row is NUL-padded out to the
terminal width, and a row that wrapped ran flush to the last column with no
padding at all. A newline with **no NUL in front of it** therefore means the row
wrapped, which is why the pattern continues across `[\r\n]` and not `[\0\r\n]`.
Kitty strips the NULs and newlines from what it hands back, so the URL arrives
already joined.

Two things it does not fix:

- A URL that genuinely **ends flush at the last column** looks identical to a
  wrapped one, so the match swallows the first word of the next line.
- A URL wrapped inside a **vertical split** cannot be recovered at all: its
  continuation rows are columns apart rather than lines apart, with the border
  and the neighbouring pane's output in between. Excluding box-drawing from the
  pattern at least makes that fail cleanly — the match stops at the border rather
  than eating it. Press `prefix+z` to zoom the pane first.

If the emitting program hard-wrapped the URL itself — a pager, `fold`, a markdown
renderer — there is a real newline in the byte stream and nothing downstream can
undo it. The durable fix in that direction is an OSC 8 hyperlink at the source,
which `kitten hints --type hyperlink` picks up whole regardless of layout.

### Agents, Git, and worktrees

`F11` runs `pick-agent` in a herdr popup, an fzf picker for:

- new or resumed Codex with unrestricted permissions;
- new or resumed Claude with unrestricted permissions;
- a plain shell.

Multiple agents in one herdr workspace share one working tree. That is useful
for coordinated roles such as implementation plus review, but independent
agents should edit separate Git worktrees. `ctrl+space shift+G` opens a worktree
of the current repository as a new workspace; ordinary Git and stacked-PR
aliases remain available in the shell.

### Kitty and UHK integration

Kitty is installed on `personal`/`gui` profiles as the `kitty-bin` pixi global
env from the [blooop channel](https://prefix.dev/channels/blooop), which
repackages upstream's current Linux binary. It is named `kitty-bin` rather than
`kitty` because conda-forge ships a stale 0.23.1 source build under that name.
Its configuration uses JetBrainsMono Nerd Font Mono, disables the audio bell,
keeps remote control disabled, and sets `shell` to `.`, a plain login shell.

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
TUIs (htop, btop, broot, lazygit, lazydocker) fail with
`cannot initialize terminal type ($TERM="xterm-kitty")` when run directly in a
Kitty window. It is
installed twice on purpose: Ubuntu's ncurses looks in `x/`, while conda-forge's
uses hex-named directories (`78/` for `x`), and neither reads the other's layout.
To refresh both after a Kitty upgrade changes the entry:

```bash
KT=~/.pixi/envs/kitty-bin/lib/kitty-bin/lib/kitty/terminfo
cp "$KT/x/xterm-kitty" ~/.terminfo/x/xterm-kitty
cp "$KT/x/xterm-kitty" ~/.terminfo/78/xterm-kitty
chezmoi add ~/.terminfo/x/xterm-kitty ~/.terminfo/78/xterm-kitty
```

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

### Personal SSH hosts

`herdr --remote <host>` takes an ssh target, and it takes an alias from
`~/.ssh/config` — which is the whole reason to name a host at all. The
[herdr docs](https://herdr.dev/docs/how-to-work/#remote-work-from-your-local-terminal)
put it as `herdr --remote ssh://you@server:2222` versus `herdr --remote workbox`,
and the second one is the one you will still be typing in a month. `sshz` and plain
`ssh` get the same names for free.

Three writers share `~/.ssh/config`, and chezmoi is the least entitled of them.
DevPod rewrites it on every workspace create, recreate and delete; hand-added
entries land at the end; and an unbalanced `# DevPod Start` marker makes a prune
delete everything below it, which is the failure in
[Lost SSH config entries after a sync](#lost-ssh-config-entries-after-a-sync). So
chezmoi contributes the wiring and nothing else:

| Path | Who owns it |
|------|-------------|
| `~/.ssh/config` | DevPod, mostly. chezmoi owns one marked block at the top of it, holding a single `Include config.d/*` line |
| `~/.ssh/config.d/personal` | You, on this machine. Untracked, `0600` |

`private_dot_ssh/modify_private_config` is a `modify_` script rather than a managed
file, which is the same choice `modify_dot_profile` and `modify_private_dot_bashrc`
make and for the same reason: a managed file would delete DevPod's blocks on every
apply and DevPod would write them straight back, and the two would fight forever. A
`modify_` script is handed the file as it stands on stdin and owns only the region
between its own markers. It emits that region at the *top*, because ssh takes the
first value it obtains for each option — so a personal `Host` block wins over
anything a later writer adds — and because a prune that over-deletes runs downward.

The hosts themselves are deliberately not in this repo. It is public, and a `Host`
block for a private LAN is an internal name and an internal address. The cost is
that hosts do not travel between machines: each one gets the `Include` from an
apply and you write its `config.d/personal` once. Making them travel means
[age encryption](https://www.chezmoi.io/user-guide/encryption/age/), not plaintext.

Adding a host is therefore ordinary ssh config, in a file nothing rewrites:

```sshconfig
# ~/.ssh/config.d/personal
Host workbox
    HostName server.example.com
    User you
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

`ServerAliveInterval` earns its place here specifically because of `--remote`: that
attach is a UI streamed over the connection for hours, and without it a dropped
link leaves the client waiting on a socket nothing will ever answer. Reattaching to
a server that kept running is cheap, so failing fast is strictly better than
hanging.

Two details that cost a debugging session each:

- **ssh matches a `Host` pattern case-sensitively.** A box that calls itself
  `BOX09` needs `Host BOX09 box09` if you ever type the lowercase form —
  otherwise `ssh box09` resolves nothing and tries to connect to a literal host
  of that name. `ssh -G <alias>` is the check; it prints the options ssh would
  actually use.
- **The far end is found by two probes, and a pixi install misses both.**
  `herdr machine add <target> --label <name>` builds a candidate list in
  `src/remote/attach.rs`. First `remote_binary_on_path_any` runs
  `ssh -T <target> "command -v herdr"` — note the absence of `-l`. Then
  `known_remote_binary_candidate_script` tries a hardcoded list:
  `$HOME/.local/bin/herdr`, Homebrew (`/opt/homebrew/bin` and `/usr/local/bin` on
  macOS, `/home/linuxbrew/.linuxbrew/bin` on Linux), three mise install layouts,
  and the Nix profiles. pixi appears on neither, and that is the whole problem.

  The PATH probe misses because of *this* repo, not herdr: a bare `ssh host <cmd>`
  gets a non-login, non-interactive bash, which reads `~/.bashrc` (the sshd special
  case) and nothing else — so on Ubuntu it returns at the interactive guard on line
  8, long before the `.bash_env` hook on line 109 that puts `$PIXI_HOME/bin` on
  `PATH`. Ask for a login shell and it resolves fine: `ssh host 'bash -lc "command
  -v herdr"'` answers `~/.pixi/bin/herdr`, because `.profile` is read there. herdr
  never asks for one. The candidate list misses because pixi is deliberately not on
  it: herdr's documented install methods are Homebrew, mise and Nix, and conda-forge
  is packaged downstream of them.

  So the binary you have is invisible twice over, on a box where typing `herdr
  --version` answers the matching version. Accepting the install prompt it offers
  is **not** harmless, which is what makes this expensive rather than merely
  confusing: it writes a real 16MB copy at `~/.local/bin/herdr` that `pixi global
  update` has no idea exists, so the box is pinned to whatever herdr was current
  that afternoon, and every later `machine add` fails naming a version the box
  appears to already have. kinisi-ci sat on 0.8.0 for three weeks that way.

  `private_dot_local/private_bin/symlink_herdr.tmpl` is the fix, and it works by
  putting the pixi binary at the first candidate the list checks:
  `~/.local/bin/herdr` is a symlink onto `~/.pixi/bin/herdr`, so both names are one
  file and pixi remains the only thing that upgrades herdr. `chezmoi apply --force`
  repairs the link if a herdr install ever replaces it with a copy, and `chezmoi
  status` shows the drift in the meantime. `HERDR_REMOTE_BINARY=<local path>` pushes
  a chosen local binary for a single invocation, which is the escape hatch on a host
  this repo does not manage.

  Reported upstream as herdrdev/herdr#3950 and closed as expected behavior: the
  non-interactive `PATH` is the contract, and pixi is not one of the documented
  fallbacks. Their recommendation was to put `~/.pixi/bin` on that `PATH` before the
  guard, which is what the `# One-command PATH` block under
  [PATH hygiene](#path-hygiene) now does, and it fixes the same gap for `dl` and the
  other 54 pixi tools a remote command could not see. Do not re-file it.


### Managed files and reproduction

| Source file | Responsibility |
|-------------|----------------|
| `dot_config/kitty/kitty.conf.tmpl` | Kitty font, UI, `shell` = `.` (plain login shell), and new-OS-window mappings |
| `run_onchange_disable-herdr-server.sh.tmpl` | Retires the old `herdr-server.service` on machines that enabled it. Ungated and idempotent: it disables the unit and clears the dangling `default.target.wants` symlink, and stops nothing, so a live session survives the apply |
| `private_dot_local/private_bin/executable_prwatch` | The PR supervisor, one python file: the poll loop (classify, diff fingerprints, rank, decide), the scan for tabs you already have open on a branch, and the worker it runs in a herdr tab (devlaunch workspace or host worktree). `status`, `dispatch`. See [PRs become the queue: prwatch](#prs-become-the-queue-prwatch) |
| `run_onchange_disable-prwatch-timer.sh` | Retires the systemd timer earlier versions of prwatch installed: clears the enable symlink, `disable --now`, `daemon-reload`. A no-op on a machine that never had it |
| `private_dot_local/private_bin/executable_ags-who` | `ags-who [--all] [--no-titles]`: who holds the memory on a devlaunch host. First the systemd-oomd and kernel OOM kills in the last hour, with the top victims. Per container: memory (anon and tmpfs shmem), CPU over 1 s, Bazel server RSS, `IMAGE STALE` when its tag now names a newer image (bm then misses the remote cache; `dl <ws> recreate`), and each Claude session in it with its status (`idle` = waiting for you), idle minutes and title. Then the host Claude sessions and the largest entries in the `/tmp/claude-<uid>` tmpfs. Run it before closing sessions to free RAM. `ags-who --workspaces` joins `dl --ls --json` with each branch's PR and lists the removable workspaces (PR merged or closed, or someone else's PR, and nothing to lose), the rest with the reason, and the ones with no clone, then prints the `for i in ...; do dl rm "$i"; done` loop |
| `dot_config/herdr/config.toml.tmpl` | herdr's keymap: `ctrl+space` prefix, the bare function-key layer, the agent priority queue, and the command popups. Verify with `herdr server reload-config` |
| `run_onchange_install-herdr-integration.sh.tmpl` | Installs herdr's Claude Code hook, which records the agent session id so a restored pane comes back as `claude --resume <id>` |
| `private_dot_claude/hooks/executable_herdr-tab-title.sh` | `Stop` hook that renames the herdr tab to Claude's own session title, and never touches a tab you named yourself. See [Tabs named after what Claude is doing](#tabs-named-after-what-claude-is-doing) |
| `run_onchange_after_install-herdr-skill.sh.tmpl` | Writes `herdr --skill` to `~/.claude/shared-skills/herdr/SKILL.md`, so an agent in a pane can drive herdr's CLI. `run_onchange` keyed on a **stat of the binary**, not on the script — a herdr upgrade has to re-run it, and nothing in a script that only names the command moves when one lands. Statting `~/.pixi/bin/herdr` would not work: that is a hardlinked trampoline shared by all ~91 pixi globals, so the env path is named instead |
| `private_dot_local/private_bin/symlink_herdr.tmpl` | Points `~/.local/bin/herdr` at `~/.pixi/bin/herdr`, the one path herdr's remote bootstrap probes. Gated on `toolbox` in `.chezmoiignore.tmpl`, since that is the flag carrying herdr in the pixi manifest and the link would otherwise dangle. Stops a `machine add` install prompt from leaving a second, pixi-invisible copy that goes stale |
| `private_dot_local/private_bin/executable_sshz` | `Ctrl+Shift+R`'s target: picks a host and `exec`s ssh, so one un-multiplexed window is one connection. Follows `Include` when collecting hosts, since the real entries are one file down |
| `private_dot_ssh/modify_private_config` | Puts `Include config.d/*` at the top of `~/.ssh/config` and touches nothing else in it, so personal hosts live where DevPod cannot prune them. See [Personal SSH hosts](#personal-ssh-hosts) |
| `private_dot_codex/modify_private_config.toml` | Sets `[tui].status_line` in `~/.codex/config.toml` and passes every other byte through, leaving the model and the trust levels to Codex. See [Codex CLI](#codex-cli) |
| `dot_pixi/manifests/pixi-global.toml.tmpl` | Installs Kitty as the `kitty-bin` pixi global env |
| `run_onchange_install-kitty-desktop.sh.tmpl` | Kitty desktop-menu entry (pixi does not create one) |
| `dot_terminfo/x/xterm-kitty`, `dot_terminfo/78/xterm-kitty` | `xterm-kitty` terminfo for non-Kitty ncurses builds (applied on **all** profiles, not just `gui` — `$TERM` follows you over SSH) |
| `dot_config/xfce4/helpers.rc` | Makes Kitty XFCE's default terminal |
| `.chezmoiexternal.toml` | Downloads flyline's `libflyline.so` (gated on `.toolbox`); also extracts 15 of Matt Pocock’s skills into `~/.claude/shared-skills` and Claude-only git guardrails into `~/.claude/skills` (gated on `.claudecfg`) |
| `private_dot_local/private_bin/executable_pick-agent` | Coding-agent picker, herdr's `F11` popup |
| `dot_config/private_uhk-agent/UserConfiguration.json` | UHK layouts and Caps-as-Ctrl |

On another personal machine, the normal install or `chezmoi update` reproduces
the managed configuration. Useful verification commands are:

```bash
kitty +runpy 'import os, kitty.config; bad=[]; kitty.config.load_config(os.path.expanduser("~/.config/kitty/kitty.conf"), accumulate_bad_lines=bad); print(bad)'
jq empty ~/.config/uhk-agent/UserConfiguration.json
```

## herdr, the multiplexer

[herdr](https://github.com/herdrdev/herdr) is the terminal multiplexer. Its
four-state agent visibility (working, blocked, done, idle) is the one thing this
setup cannot build itself.

### There is no autostart, deliberately

herdr runs one server per machine, spawned by whichever client gets there first,
and every later `herdr` attaches to it.

So nothing is arranged at login. A Kitty window is a plain login shell, an SSH
login is a plain shell, and herdr is started by typing `herdr`. That avoids the
whole guard list an autostart needs — the `$-`/`-t` tests for scp and rsync,
`SSH_ORIGINAL_COMMAND`, `TERM_PROGRAM`, a `HERDR_ENV` test so a herdr pane does
not autostart a second multiplexer — because none of those contexts can
accidentally launch a multiplexer.

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

### Why the server is no longer a systemd unit

herdr spawns its server as a child of the first client, so it inherits that
client's cgroup — `kitty-<pid>-<n>.scope` locally, or the sshd session scope on a
remote box. There was a `herdr-server.service` here that owned the server
instead, on the grounds that systemd tears those scopes down when the window
closes or the connection drops, taking every pane with it
([herdrdev/herdr#1762](https://github.com/herdrdev/herdr/issues/1762)).

That reasoning is sound in general and did not hold on this fleet, for two
reasons found while a CI box was dropping sessions every ninety minutes.

**logind here does not kill anything.** `KillUserProcesses` is false, so a
disconnected session's scope is *abandoned*, not torn down — six of them were
alive on the box in question, holding between 25 and 304 tasks each. The server
a plain `herdr` spawns therefore survives a dropped connection anyway, which is
the whole thing the unit was buying.

**The unit was what made herdr an OOM target.** Ubuntu enables systemd-oomd's
pressure-kill on `user@.service` and nowhere else in the user session:

```
user.slice          ManagedOOMMemoryPressure=auto   # ignored
user-1000.slice     ManagedOOMMemoryPressure=auto   # ignored
user@1000.service   ManagedOOMMemoryPressure=kill   # 50% for >20s
```

`app.slice` is inside `user@.service`, so the unit placed the server in the one
cgroup oomd is allowed to reap — and, at 8-11GB of agents, it was always the
largest candidate there. When 46 CI containers under `system.slice` exhausted
the box, oomd could not touch them and killed herdr instead, twice in one
afternoon, 81 processes the first time. A session-scope server sits in
`user-1000.slice` and is not a candidate at all.

So the server is upstream's again: `herdr` starts it, `herdr server stop` ends
it, and nothing has to be enabled. The cost is real but narrow — on a machine
configured with `KillUserProcesses=yes`, a dropped SSH connection *would* take
the server down, and such a machine wants the unit back rather than this. Check
with `busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
org.freedesktop.login1.Manager KillUserProcesses` before assuming.

`run_onchange_disable-herdr-server.sh.tmpl` retires the unit on machines that
already enabled it. It stops nothing, so the apply that removes it leaves a live
session attached; upstream behaviour begins at the next boot.

### Clipboard

Two different paths, and only one of them depends on the server's environment.

**herdr's own copy** — mouse select with `ui.copy_on_select` (default on), and
copy mode's `v`/`y` — runs in the *client*, so it uses the environment of the
terminal you are attached from. Nothing about where the server was started
changes it. This is also why `herdr --remote` can bridge a local desktop
clipboard to a remote server while `ssh host` then `herdr` cannot: in the first
the client is local, in the second the whole thing runs on the far end.

**Programs inside panes** that talk to the display themselves — `xclip`,
`wl-copy`, an agent pasting an image — inherit the *server's* environment, which
is fixed at server start and does not follow a reattach
([herdrdev/herdr#2448](https://github.com/herdrdev/herdr/issues/2448): panes show
no `DISPLAY` after reattaching, while the terminal that attached has one).

That bug is mostly a Wayland problem and this desktop is largely immune, and
rather more so now the server is spawned by a client: it inherits that
terminal's environment directly, `DISPLAY` and `XAUTHORITY` included, with no
import step to get wrong. `:0` is stable on a single-seat box and
`~/.Xauthority` is a fixed path rather than a per-session file under `/run`, so
the values stay right for as long as the server lives.

The trap this replaces is worth remembering: under the unit the environment came
from `systemd --user`, which has neither by default, so XFCE's session-start
import — or the enabler's re-import — was load-bearing for `xclip` inside a
pane. Starting the server from a terminal that already has a display sidesteps
the whole question.

Neovim in a pane is nominally in the second category, and deliberately is not any
more: it copies through OSC 52 whenever `$HERDR_ENV` is set, so the yank goes out
through the client rather than to a selection owner that dies with the pane. The
reasoning is under the Neovim clipboard notes above.

`clip` is immune either way. It tests the *display* rather than the binary and
falls through to OSC 52 on `/dev/tty` when there is no usable one — the same
design that makes it work inside a devcontainer, which turns out to cover this
case for free. Neovim's OSC 52 provider is in the same position. What would
break, if the display environment ever were missing, is a bare `xclip` in a pane.

There is no config option to force OSC 52 — the only clipboard settings are
`ui.copy_on_select` and the copy toast — so the server's environment is the
mechanism, not a preference.

### Keys

The keymap is `dot_config/herdr/config.toml.tmpl`: bare function keys for the
hot path, in the spirit of byobu, and flat, because herdr has no sticky modes: one prefix press, one action, no Pane/Tab/
Resize layer to be inside of.

The prefix is **`ctrl+space`**, not herdr's default `ctrl+b`, which is a two-hand
stretch and the reason the prefix layer went unused at first. `ctrl+space` is a
pinky and a thumb, and it is the only easy chord free everywhere in this stack:
`alt+space` is GNOME's window menu and `super+space` is its input-source switch.
`ctrl+;` is the one to switch to if `ctrl+space` ever grates. Moving off `ctrl+b`
also hands `ctrl+b` back to copy mode as page-up. The only cost is readline's
`set-mark`.

`prefix` takes a single string. An array is rejected outright — *invalid type:
sequence, expected a string* — so there is no aliasing it.

| Key | Purpose |
|-------|---------|
| `F1` / `Shift+F1` | Go To already in **name-search** mode (kitty sends `ctrl+space g /`) / Go To status-first. See [Bare F-keys](#bare-f-keys-and-the-kitty-macros) |
| `F2` / `F3` / `F4` | New tab / previous tab / next tab — byobu's three, unchanged |
| `F5` | Dump the pane's scrollback into `$EDITOR`, landing at the *last* line — the editor config does that part, see below. Kept from muscle memory; `ctrl+space [` is the better answer now |
| `Shift+F5` | Workspace picker |
| `F6` | Rename tab |
| `F7` / `Shift+F7` | **Next / previous agent that needs you.** herdr's own `next_agent` is positional — one row down the panel from wherever you are, whatever the sort — so on its own it walked idle and working agents too. The `agent-queue` plugin below filters working agents out of the panel and sorts blocked and done ahead of idle, which the docs say also drives next/previous navigation, so F7 reaches what needs you first |
| `F8` / `F9` | Previous / next workspace, **across machines** (kitty drives the workspace picker one step) |
| `F11` | `pick-agent`, the agent picker, in a popup |
| `ctrl+.` / `ctrl+,` | Next / previous agent in the queue: "next thing that needs me" |
| `ctrl+space a` | Flip the Agents panel between **needs me** (blocked, done, then idle — never working; what F7 walks) and **all**. herdr has one Agents panel and one projection on it, so this is the nearest thing to a second sidebar; the Spaces panel is the everything-view at workspace granularity, and F9 the picker over all of them |
| `ctrl+space [` | Copy mode: vim motions, `/` and `?` search, `v` to select, `y` to yank |
| `ctrl+space` `.` / `,` | The same agent queue, on the prefix |
| `ctrl+space alt+1..9` | Jump to agent N by queue position, so `alt+1` is whatever is most blocked. The one agent key that was always absolute rather than relative |
| `ctrl+space o` | Jump to whatever the last notification was about |
| `ctrl+space t` | Scratch terminal, in a popup |
| `ctrl+space shift+B` | Break this pane out into its own tab |
| `ctrl+space ?` | The live keymap — the thing to trust over this table |

Two of those key strings are worth knowing are legal, because the docs do not say
so: `ctrl+period` and `shift+f7` both validate. Check any new one with
`herdr server reload-config`, not `herdr config check` — the former returns a
`diagnostics` array and reports `partial` with *kept current keybinds* rather
than applying a bad value, and the latter can only ever read the real config path
because it ignores `HOME` and `XDG_CONFIG_HOME`.

Copy mode (`ctrl+space [`) is the keyboard path to copying a line. F5, the
scrollback dump into `$EDITOR`, is the other one.

What F5 still gets wrong on its own is *where* it opens. herdr writes the
scrollback to `/tmp/herdr-scrollback-*.txt` and runs a hardcoded shell line —
`eval "${EDITOR:-vi} \"$scrollback_file\""` — with no `+<line>`, so the cursor
starts on line 1, thousands of lines above the output that was on screen when
the key was pressed. herdr 0.9.0 has nowhere to put
that preference: the command is a string constant in the binary, there is no
`editor` config key, and the only input is `$EDITOR`. Since that string is
`eval`ed, `EDITOR="nvim +\$"` would work — and would also open `git commit` and
every other editor spawn at the last line.

The same autocmd fixes what the buffer *looks* like, which was the other half of
the complaint. A dump is a grid: its lines are as wide as the pane was, 292
columns here. LazyVim leaves `wrap` on, adds a number column and a sign column,
and its `lazyvim_wrap_spell` FileType autocmd turns `spell` on for `filetype=text`
— which a dump is. Five columns narrower than the grid it holds, so every
full-width row (a TUI's box rules, a wide table) folds onto a second display line
with a stub of leftovers under it, and terminal output gets spell-underlined on
top. `nowrap`, no number column, no sign column, no spell, and a dumped row
occupies exactly the row it occupied in the terminal.

It is *not* a width-accounting disagreement between herdr and Neovim, which was
the first suspicion and is worth writing down as ruled out. Probing herdr's actual
cursor advance (`ESC[6n` after each glyph) against `strdisplaywidth` in Neovim
gives identical answers for every glyph in a dump: box drawing, ambiguous-width
symbols, VS16 emoji, ZWJ sequences, combining marks and nerd-font PUA.

So the fix lives in the editor, keyed on the filename, in both configs that can
be `$EDITOR` here:

- `dot_config/nvim/lua/config/autocmds.lua` — `BufWinEnter *herdr-scrollback-*`,
  which runs after FileType (where the spell setting comes from) and on the window
  that shows the buffer
- `private_dot_vimrc` — the same autocmd, for the profiles with no `.editor` flag
  and therefore no nvim. Spelled as two `autocmd` lines rather than one with `\`
  continuations: this file has no `set nocompatible`, so a continuation is an `E10`
  the moment anything sources it with `-u`

### The agent panel is a queue only if the key walks it

`ui.agent_panel_sort = "priority"` sorts the Agents panel with blocked agents
first, and the config comment used to say `next_agent` "walks it". It does not.
The docs define `next_agent` as *focus the next agent shown in the agent panel*
— positional, one row from wherever you are — so F7 from row 5 went to row 6
while the agent with the tick sat at row 1. And `done` means "idle and not yet
seen": landing on it marks it seen, it becomes `idle`, and the panel re-sorts
underneath you, so the next F7 went somewhere unrelated again.

The fix is `agent.view.set`, a socket-only method (no CLI) that installs a
filtered projection of the Agents panel. Per the docs it "controls the expanded
and collapsed sidebar, mobile Agents list, mouse targets, indexed focus, and
next/previous Agent navigation" — that last clause is the one that matters. With
the panel filtered to `blocked` + `done`, F7 has nothing else to land on. Idle
agents are in the filter too, sorted last: blocked+done alone made the panel an
inbox, and an agent that finished while its tab was focused went straight to
`idle` ("seen") and could never be found by F7 again. Sorted by attention first,
blocked and done still head the list, and F7 continues into idle agents —
most recently changed first — instead of wrapping.

That lives in `dot_config/herdr/plugins/agent-queue/`, a local herdr plugin:
`view.sh set|clear|toggle` posts the JSON to the socket (raw, via `socat`, since
there is no CLI), a `[[startup]]` hook runs `set` after every server start or
handoff because the projection dies with the server, and three `[[actions]]`
expose it so `prefix+a` can bind `local.agent-queue.toggle` as a
`type = "plugin_action"` key. `run_onchange_after_link-herdr-plugins.sh` does the
`herdr plugin link` — chezmoi puts the files in place, but herdr only runs a
plugin it has been told about — and reruns when the manifest hash changes.

The cost: `working` agents leave the Agents panel while they work and come back
when they finish or block. There is no second panel to show them in — one Agents
panel, one projection — so the everything-view is the Spaces panel (rolled up
per workspace), Shift+F1, or `prefix+a` for a moment. The docs' own worked example is
the middle ground, current workspace plus anything needing attention elsewhere;
it is left in `view.sh` as a comment for anyone who wants working agents back at
the cost of F7 walking their current workspace's idle ones again.

### PRs become the queue: prwatch

The agent-queue plugin fixes which agent F7 lands on. The other half of the
problem was that there were ~100 open PRs across ~40 repos being babysat by
hand, one Claude tab each, until RAM ran out — and on the pilot repo 11 of 18
needed nothing at all. So the supervisor's first job is *not* launching agents,
and it must not be a long-running Claude session, which burns context every tick
and compacts away what it was watching. `prwatch OWNER/NAME` is a python + `gh`
loop you run in a terminal window: four API calls per poll, every ten minutes,
state under `~/.local/state/prwatch/OWNER/NAME/`. A Claude worker is started
only on a *transition*, in a herdr tab of its own, and told exactly one thing to
do. The tab opens itself, and the notification is the cue that the PR is ready
to be looked at. The tab is then yours: read it, carry on in it, or `/exit`.
Exiting is the cleanup, and a later transition on the same PR is prompted into
the same open tab rather than a new one.

The first version was a systemd user timer with a config file. That shape hid
what was running: the timer ticked whether or not you remembered it, the repo
and the live/dry-run switch lived in `~/.config/prwatch/config`, and `--repo` on
a hand run changed the poll but not the dispatcher, which re-read the config and
went to the default repo. Now the window is the process. The command line names
the repo and the mode, there is no config file, Ctrl-C stops the polls and tears
down the workers, and closing the window is the off switch. One window per repo;
a lock in the repo's state dir refuses a second.

Design and the measured reasons behind each predicate are in
[#38 — prwatch: a PR supervisor that dispatches herdr workers on transitions](https://github.com/blooop/dotfiles/issues/38);
the short version:


| Stage | Trigger | Action |
|---|---|---|
| `unassigned` | neither yours by authorship nor assigned to you. A guard rather than a stage you will see: the poll lists exactly the union of those two sets, so nothing it fetches lands here | drop |
| `stale` | a `stale` label, or last **human** activity > 7 d with no `keep-alive` label. Not `updatedAt`: the repo's own stale bot bumps that by weeks | drop |
| `draft` | `isDraft` and CI not red | drop |
| `ci_red` | a **required** check failed. `CANCELLED` is pending, not red — 23 % of runs there end cancelled from `cancel-in-progress` | worker: fix CI |
| `conflicting` | `mergeable == CONFLICTING`. An `UNKNOWN` within five minutes of the head commit carries the last known value forward; past that it stands as `UNKNOWN` and this rung falls through, because a computation GitHub is stuck on is not a conflict | worker: merge base |
| `comments_open` | an unresolved thread whose **last comment is not the author's and not a bot's**, a live `CHANGES_REQUESTED`, or a non-empty non-author review body newer than the head commit. `unresolved > 0` alone was 100 % false positives — nobody clicks Resolve | worker: `/respond`, replies through `/unslop` |
| `ready` | approved **after** the head commit, CI green, mergeable | notify only, never merge |
| `waiting_review` | otherwise | nothing |

A transition is a change in `(stage, head_sha, actionable_threads,
red_required_checks, mergeable)`, not a stage change: stage-only misses a new
review round inside an existing stage. Workers are woken for `ci_red`,
`conflicting` and `comments_open`; `ready` notifies through
`herdr notification show`.

Where the worker runs is a per-repo choice, made on the command line:

- **Default: a throwaway devlaunch workspace.** The tab runs
  `exec dl OWNER/NAME@branch --rm -- claude`, so the repo's own devcontainer is
  the toolchain. `dl` forwards the gh and Claude logins, installs herdr inside
  the container and reports the agent to the pane, which is what lets
  `herdr agent prompt` reach Claude in there. When you exit Claude, `--rm`
  deletes the workspace and the exec'd shell ends, so the pane and its tab
  close on their own. `dl` refuses the delete, and says so, if the clone holds
  work nobody pushed; `dl --ls` finds it.
- **`--clone PATH`: a host-side `git worktree`** cut from that clone, with
  `herdr agent start <name> --kind claude --pane <id>` running Claude in the
  pane's own shell. For repos whose devcontainer cannot be built here:
  kinisi_ros delegates its image to `kinisi_env build`, which refuses without
  live `gcloud` credentials, needs a ~20 GB sim image, and is a per-clone
  GPU-claiming singleton that does not fan out. Passing the clone as the repo
  argument (`prwatch ~/kinisi/kinisi_ros`) names the repo from its remote and
  selects this backend in one go. Exiting Claude leaves the pane at its shell,
  so the next poll closes that tab and removes the worktree if it is clean; one
  with uncommitted or unpushed work is kept and named.

Safety rails, because the worker runs `/respond` unattended and that was the
explicit choice:

- **`--dry-run`** classifies, notifies, and prints the prompt it would have
  sent, and opens no tab. The mode is on the command line, where the window
  shows it.
- Per-PR round budget, 8 per UTC day (`--round-budget`). Every push is
  legitimately a new fingerprint, so a fix → red → fix loop fires correctly
  every cycle and the budget is what breaks it.
- Worker cap (`--max-workers`, default 5 turns in flight; open idle tabs do not count); the rest stay pending and go out as
  slots free up, ranked `conflicting` first. A worker finishing wakes the next
  poll early, so a freed slot is not idle until the tick.
- Stacked PRs are worked parent-first. A PR whose base is another open PR's
  head branch is held while that parent is conflicting, or is red on a check
  they share — the child's branch contains the parent's commits, so it inherits
  the failure and the fix belongs upstream. A parent with only open review
  threads blocks nothing. When the child's turn comes its prompt names the
  parent, merges the parent's branch rather than the repo's base, and is told
  to change nothing and say so if the problem reproduces on the parent.
- A red required check is re-run once per head before it costs anything. A
  failing check is not always the PR's fault, and retrying the failed jobs is
  what a human tries first — no round, no worker, no devcontainer. Only a check
  that fails again earns a turn. The cap is the head sha: one retry per run per
  push, so a genuinely broken test cannot become a retry loop. `gh run rerun`
  refuses a run still in progress, so the retry waits for the rest of the run —
  but only for 25 minutes. A required check that has already failed will not
  un-fail, and a single job can sit in progress for hours, so past that the
  retry is abandoned and the PR gets its worker. `--no-rerun` hands every red
  CI straight to a worker instead.
- A turn that ends cleanly but leaves the PR exactly as it found it owes one
  more, and exactly one. The marker records the PR's fingerprint at dispatch; if the next poll
  computes the same fingerprint, the turn changed nothing observable and the PR
  stays pending. Without this a worker that read its failing check, judged it a
  flake and pushed nothing left the PR unreachable for good — `ci_red` with an
  unchanged head produces an identical fingerprint however long it waits, so no
  transition ever returns. It is capped at one retry because the prompt
  sanctions that answer — a failure reproducing on the base branch is not this
  PR's to fix, and saying so beats patching over it — so a second identical
  verdict is a result, not a miss. After it, the PR is left for a human with a
  notification rather than spending the day's budget re-deciding.
- A conflict outranks red CI, because a red run on a conflicting head can never
  come back green — the fix is a merge commit, which discards that run's
  results with the sha they belong to. Red-CI-first meant a PR that was both
  spent round after round on checks against a base it could not merge into,
  and the conflict blocking the merge was never named until every check went
  green.
- In a stack, a PR is held behind a `conflicting` ancestor at **any** depth,
  and behind nothing else. A conflict below is the one thing a descendant
  cannot work around: its own merge resolves against a branch that has to
  change first. The walk used to be a single hop, which let a conflicting PR
  through whenever its immediate parent happened to be red on some unrelated
  check while the grandparent's conflict was still unresolved. Red and
  comment-bearing ancestors deliberately hold nothing, and that is a measured
  choice: a thirteen-deep stack ran for four hours with every level worked
  concurrently and converged — workers re-merge their parent branch on the next
  turn, so a stale base costs a turn, not the result — while its root spent all
  eight rounds flapping between `comments_open` and `conflicting` as `main`
  moved and never resolved. Holding on any unwell ancestor would have parked
  all twelve descendants behind exactly that PR for the whole run.
- One process per repo, by a lock in the repo's state dir. A second window on
  the same repo would spawn duplicate workers off the same transitions.
- The prompt forbids merge, close, force-push, amend, `gh auth token`, and
  resolving a human's thread; a PR whose head branch belongs to somebody else is
  refused before a prompt is built. The poller itself never logs a token.
- Authorship **or** assignment is the gate, either one sufficient. The poll
  lists the PRs assigned to you unioned with the ones you wrote, and works both:
  a PR you opened and never assigned to yourself, and a PR somebody else wrote
  and assigned to you — where the worker pushes to their branch. Unassigning
  therefore takes back only somebody else's PR; your own authorship is a claim
  you cannot drop, so a `stale` label is how you park one of yours, since
  `stale` outranks every worker stage. The author login is read strictly, with
  no fall back to you when the API omits it: a guessed author would be a worker
  on a PR you have no claim on.
- An agent that herdr knows about but has no status for yet — a Claude for the
  minute `dl` takes to bring it up — counts as busy. That is what stops a worker
  landing on a branch somebody just launched their own agent on: the tab is
  recognised as theirs, adopted rather than duplicated, and never prompted
  mid-startup.
- A PR whose tab is mid-turn is held until it settles, never prompted twice at
  once — and it makes no difference whether the turn is a worker's or yours.
- A branch you already have open is not opened a second time. Before a poll
  opens anything it asks what is open: `dl --ls --json` for the devlaunch
  workspaces and each pane's cwd for host worktrees. A tab already on the PR's
  branch is adopted and prompted rather than duplicated. The match is on the
  branch, never on the tab's name: `dl` titles the terminal `repo@branch` and
  the tab-title hook copies that to the label, but the slug is lossy and
  one-way (`rerun_drop` and `rerun-drop` both render as `rerun-drop`, and a long
  branch is cut), so the title is only ever checked against a workspace id and
  never parsed back into a branch.
- A turn that did not work the PR is owed another, recorded on the tab's
  marker and retried on the next poll within the round budget. `pending` cannot
  carry that: it is cleared at dispatch, so a failed worker used to leave the PR
  in neither the fired set nor the pending one — top of the queue, never picked
  up, waiting for a transition that was never coming.
- An `UNKNOWN` mergeable freezes the fingerprint, but only for five minutes
  after the head commit. The freeze is there because `UNKNOWN` is usually
  GitHub recomputing straight after a push, which is exactly when a worker has
  just pushed a merge commit: firing then would read the last known
  `CONFLICTING` and send a second merge worker at a PR about to come back
  clean. Unbounded, though, it was a latch. `prev_fingerprint` is read from the
  same frozen value, so the two were equal by construction and the PR was
  skipped on every poll — in none of the three candidate sets, still at the top
  of the queue. A stacked PR on a moving base branch can sit `UNKNOWN` for
  hours that way, and one did: red on a required check, invisible for 2 h 45.
  Past the window the stale `mergeable` is dropped too, so the PR is ranked on
  the signals that are real rather than earning a merge worker for a merge that
  already landed. `ready` still needs a live `MERGEABLE`, so an unevaluable PR
  is never reported mergeable
  ([#39 — a stuck UNKNOWN latches the fingerprint](https://github.com/blooop/dotfiles/issues/39)).
- A new devcontainer tab is handed its task at launch — `dl OWNER/NAME@branch
  -- claude <prompt>`, which is exactly what `aid` is a shortcut for — so Claude
  submits it by reading its own argument. No input box, no Enter to lose, no
  race to retry around. Two cases still type it in: an adopted tab, where Claude
  is already running, and the worktree backend, where `herdr agent start`
  refuses an argument containing a newline and every prompt has one.
- That input box is cleared before every submit. `herdr agent prompt`
  appends to whatever is already typed there and submits the lot, so an unsent
  draft on an adopted tab — or the previous prompt on a retry — would silently
  become part of a worker's instructions. Anything you left unsent in an adopted
  tab is discarded, and the log says so.
- The prompt is re-sent when herdr answers `agent_prompt_stalled`. A Claude that
  has only just come up takes the text and loses the Enter; that is a failed
  delivery, not a turn, and it used to return in eight seconds and be reported
  as a thirty-minute timeout. A branch checked out somewhere else with no tab on
  it is named in the log, because the worker pushes from its own clone.
- An adopted tab is yours in a way an opened one is not: prwatch never closes
  it and never removes the checkout under it. A tab that outlived its Claude is
  dropped instead of prompted — `herdr agent prompt` answers `agent_not_found`,
  which would cost a round every poll. `--rm` is dropped too when a
  devlaunch workspace for the branch is already running, with or without a tab
  — `dl` attaches to the one that is there rather than making a second, so
  `--rm` would arm the delete on yours and take it when the worker's Claude
  exits.
- Ctrl-C stops the polls and stops waiting on turns in flight. The tabs stay:
  they are yours, and the turns inside them carry on.

Each prompted turn is a thread of the prwatch process; the tab it runs in is
not, and outlives both the turn and the process. Each tab gets `$pr` / `$stage` metadata tokens
(`herdr pane report-metadata --source prwatch`), and `ui.sidebar.agents.rows`
renders them, so the Agents sidebar reads `claude · #10761 · ci_red`. Gotchas
the spawn probe paid for: bare `--wait` (the turn settles as `done`, and
`--until idle` times out against a finished turn); Claude comes up in manual
mode, so the permission posture is passed explicitly; ctrl+c does not quit
Claude Code, `/exit` does.

### Two clients on one session are synced

Attach two herdr clients to the same session and they mirror: change tabs in one
window and the other window changes too. So "every window runs `herdr`" is three
windows showing one screen.

The answer is not one session per window. Under herdr the cheap unit
of independent work is a **workspace** inside the one session, so extra
workspaces — not extra windows — are how several projects are held at once.

For the genuinely separate case — another monitor, a demo, work that must not
share a sidebar — name a session yourself with `herdr --session <name>`. There
was an `hnew` here that derived the name from the project in the cwd and
guaranteed it was free; it went unused, and on a box reached over SSH its kitty
bindings could never fire at all. If you name sessions by hand, remember
`--session` uses-or-creates, so a collision silently re-creates the mirroring
you were avoiding — check `herdr session list` first.

| Want | Do |
|------|-----|
| Another project, same window | `ctrl+space shift+N` — a workspace. Nearly always this |
| A worktree of this repo as a workspace | `ctrl+space shift+G` |
| A window that is genuinely independent | `herdr --session <name>` |
| See what has accumulated | `herdr session list`, then `herdr session stop\|delete <name>` |

### Selecting a tab

`ctrl+space g` / `Shift+F1` is herdr's own picker, and the only one. Typing in
it filters by agent **status** first; a name search needs `/` as an extra
keystroke — and name search is the frequent case. herdr has no action that
opens Go To in search mode, so bare `F1` is a kitty macro that sends
`ctrl+space g /`.

An fzf popup (`herdr-goto`) did the same job on `ctrl+g` once and went unused.
The macro is better: it opens herdr's own Go To, which lists every pane on every
connected machine, so a name search also hops machines.

#### Bare F-keys and the kitty macros

The F-keys sit behind a layer key on a split keyboard, so a frequent action
cannot also need a modifier. Bare `F<n>` is the common action; `Shift+F<n>` is
only ever the rare variant of the same thing (`F1`/`Shift+F1`, `F7`/`Shift+F7`).
`F10` no longer closes a pane — `prefix+x` does — and `F1`/`F6`/`F8`/`F9` lost
lazygit, detach, split and goto, none of which were pressed.

Three keys are macros in `kitty.conf`, because herdr reaches their action only
through the prefix:

| Key | kitty sends | Does |
|-----|-------------|------|
| `F1` | `\x00g/` | Go To, typing mode |
| `F8` | `\x00w` Up Enter | previous workspace |
| `F9` | `\x00w` Down Enter | next workspace |

`\x00` is `ctrl+space`, the prefix — change the macros if the prefix changes.
The workspace picker is the one route between machines: herdr has no
next-machine action, and `herdr workspace focus` cannot change which machine a
client shows. It wraps, and with one workspace per machine one step is one
machine.

The macros fire only when the kitty window title ends in ` · herdr`, which
herdr's `window_title` writes; in any other window these are plain F-keys, so a
shell never receives `ctrl+space w` Up Enter (which would rerun the last
command). Two traps:

- The `--when-focus-on` value is a match *expression*, where a space separates
  terms. `title:· herdr$` does not parse — *No location specified before
  herdr$* — and the mapping silently never fires. It is spelled `title:·\sherdr$`.
- The title comes from the herdr **server you are looking at**. A remote server
  still on its old config writes the title without the suffix, and F8/F9 go dead
  while you look at it. `herdr server reload-config` on that machine fixes it.

### Claude session resume, and the apply that deleted it

`herdr integration install claude` writes `~/.claude/hooks/herdr-agent-state.sh`
and a `SessionStart` entry into `~/.claude/settings.json`. It is narrower than it
sounds: on herdr 0.8.2 that hook reports the agent's **session id** and nothing
else. Lifecycle state stays screen-manifest detection either way. What it buys is
resume — with the id on record, `session.resume_agents_on_restore` brings a pane
back as `claude --resume <id>` after a server restart instead of a bare shell in
the right directory. Given [#3415](https://github.com/herdrdev/herdr/issues/3415)
above, that is the closest thing here to a persistent session record, and
the reason the hook is worth having.

The trap: `modify_settings.json` enforces the whole `hooks` object on every
apply, so the installer wrote that entry and the next `chezmoi apply --force`
deleted it again — silently, taking resume with it. The entry now lives in
`modify_settings.json` so it survives. The hook *script* is deliberately not
managed — herdr owns it, says so in its own header, and overwrites it on
reinstall — so the settings entry is guarded on the file existing, and
`run_onchange_install-herdr-integration.sh.tmpl` is what puts it there.

### Tabs named after what Claude is doing

An unnamed herdr tab is labelled with its position in the row, so a screen of
agents reads `1 2 3 4` and says nothing about which is which. Claude Code already
writes a one-line summary of the session to the terminal title, and herdr records
it per pane as `terminal_title_stripped` with the spinner glyph removed — so the
name worth putting on the tab is already sitting in the pane record.
`private_dot_claude/hooks/executable_herdr-tab-title.sh` is a `Stop` hook that
copies one to the other. It is a copy, not a generation step: no model call, no
token cost, one `herdr tab rename` per turn.

Everything interesting about it is what it declines to overwrite. The auto label
is either `""` or a bare integer and nothing else ever is, which makes the
integer test enough to claim a tab nobody has named — no bookkeeping, no marker
file, no guessing. That the number is positional rather than fixed at creation is
worth knowing and easy to get wrong: with three auto-named tabs, closing the
middle one renumbered the last from `6` to `5` in the same breath. Either way the
test holds, since a stored generated number is still an integer.

Keeping a name after the first write is the part that needs state. The hook
records what it last wrote per tab id under
`~/.local/state/herdr-claude-tab-title/`, and only overwrites a label it still
recognises as its own. Rename a tab by hand and the hook goes quiet on it
permanently; clear the name in the UI and the label reads as auto again, which
hands it back. Tab ids are never reused, so those files only accumulate — hence
the 30-day prune on the way out.

devlaunch is the one other writer. Since 0.59, `dl` renames the tab
`<repo>@<branch>` when it opens a workspace, and prwatch finds worker tabs by
that label, so a live `dl` tab must keep it. It does without any effort: inside
the devcontainer there is no herdr on `PATH` and no `HERDR_ENV`, and `dl` sets
`CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`, so the hook never runs there. (A
`/.dockerenv` test covers the day `dl` lends herdr to the container.) The case
that needed code is the tab `dl` leaves behind. Exit the workspace, start a host
Claude in the same tab, and the label still reads `kinisi-ros@feat/esdf-map-source`.
That is not an integer and not the hook's own last write, so the hook used to
read it as a name you typed and went quiet on the tab for good. Now a label of
the `<repo>@<branch>` form — one word, one `@` — counts as unnamed on the host.
A name you type with a space in it, or with no `@`, is still left alone.

A tab holding more than one pane is skipped too: two Claudes in a split would
each write their own title every turn and the label would flicker between them.

### Known risk, not mitigated

[herdrdev/herdr#3415](https://github.com/herdrdev/herdr/issues/3415): panes are
SIGHUP'd before server shutdown on reboot, `persist.clear` fires, and the whole
session record is lost. There is no user-side workaround, and no herdr option
that keeps the record across it.

This got worse when the unit went. Its `ExecStop` ran `herdr server stop`, which
is the ordering the bug report says is missing — an educated guess at a
mitigation rather than a fix, but better than nothing, and nothing is what a
client-spawned server has on a reboot. Run `herdr server stop` by hand before
rebooting if the layout is worth keeping.

## Cheatsheet

### Navigation
| Alias | Command |
|-------|---------|
| `..` | `cd ..` |
| `...` | `cd ../..` |
| `....` | `cd ../../..` |
| `br` | broot: browse with type-to-filter; `→`/Enter goes into a dir, `←` goes up. Press `alt-t` (or type `:t`) to cd the terminal to the selected dir and quit. Default search is token-based: type comma-separated fragments in any order, e.g. `kin,ros` matches `kinisi_ros`. Prefix `f/` for fuzzy, `\|`/`&`/`!` for or/and/not |
| `z <name>` | zoxide: jump to most-used dir matching name |
| `Alt+C` | fzf: fuzzy-pick a subdirectory and cd into it (re-bound through [flyline](#flyline-the-prompt-line-editor) where that is loaded) |
| `Ctrl+T` | fzf: fuzzy-pick a file and paste its path at the prompt (likewise) |


### Flyline (the prompt line editor)
Gated on `toolbox`. Flyline is a readline replacement — a bash loadable builtin
(`enable -f`), not a program on `PATH` — so on a machine that has it, *every*
key at the prompt is handled by flyline rather than by bash. It brings syntax
highlighting, inline suggestions from history, a fuzzy `Ctrl+R`, mouse-free text
selection, and tab completions synthesised from a command's `--help` when it
ships no completion script.

It is fetched as a pinned `.so` by `.chezmoiexternal.toml` and enabled in the
interactive half of `.bash_env`, which also makes the two adjustments below.
Where the flag is off (the container profiles) the prompt is plain readline and
the fzf keys work the ordinary way.

| Key | Action |
|-----|--------|
| `Ctrl+R` | flyline's fuzzy history search (not fzf's — see below) |
| `Alt+R` | commands you `Ctrl+C`'d out of earlier in this session |
| `Tab` / `→` / `End` | accept the inline suggestion under the cursor (`Tab` is ours — see below) |
| `Up` | walk history entries that prefix-match what is already typed |
| `Tab` | completion. Accepts the selected entry (ours — see below); `Up`/`Down` and `←`/`→` move through the list. Offers to synthesise a spec via flycomp if the command ships none |
| `flyline run-tutorial` | the interactive tour — worth the five minutes once |
| `flyline key list` | every binding, defaults and ours |
| `flyline settings` | active settings, and how they differ from the defaults |

**Five deliberate departures from upstream's defaults**, all in `.bash_env`:

- **Mouse capture is off** (`flyline mouse --mode disabled`). It is on by
  default, and it is the one default that fights the rest of this setup: Kitty
  runs `copy_on_select true` and herdr runs `ui.copy_on_select`, so
  drag-to-select *is* the clipboard here (see [Clipboard](#clipboard)). A prompt
  that grabs the mouse takes that away for the one line you are most likely to
  want to copy. `flyline mouse --mode smart` in a shell to try it.
- **`Ctrl+T` and `Alt+C` are re-bound to fzf; `Ctrl+R` is not.** Replacing
  readline kills the `bind` calls `key-bindings.bash` made, so those two keys are
  re-pointed at fzf's surviving widget functions through flyline's own table.
  `Ctrl+R` stays with flyline, whose fuzzy history search does the same job
  in-process. Hand it back with
  `flyline key bind Ctrl+r 'always=runBashCommand(__fzf_history__)'`.
- **`Tab` completes; the arrows select.** Upstream's `Tab` is a three-way — open
  the list, walk it, and accept only when one match is left — so on an ambiguous
  completion the key that everywhere else inserts something moves a cursor
  instead, and `Enter` is what inserts. Here one `Tab` takes the top entry, and
  `Up`/`Down` pick a different one first. It is two bindings because
  auto-suggest opens the list with *nothing* selected — the popup footer reads
  ` /3`, not `1/3` — so accepting alone is a no-op there and the first press has
  to select and accept as one chain:

  ```bash
  flyline key bind Tab 'tabCompletionEntrySelected=tabCompletionAcceptEntry'
  flyline key bind Tab 'tabCompletionAvailable+!tabCompletionEntrySelected=tabCompletionNextSuggestion+tabCompletionAcceptEntry'
  ```
- **`Tab` also accepts the inline suggestion.** Upstream gives the grey,
  history-sourced suggestion to `→`/`End`/`Ctrl+E` only, so `Tab` — the key
  every other shell uses to accept what it offers — opened the list instead. A
  third binding, bound last so it outranks the two above, takes the inline
  suggestion when the cursor is at the end and no list entry is selected:

  ```bash
  flyline key bind Tab 'inlineSuggestionAvailable+cursorAtEnd+!tabCompletionEntrySelected=inlineSuggestionAccept'
  ```
- **The cursor jumps instead of gliding** (`flyline set-cursor --interpolate
  none`). The glide moves one step per frame, and a herdr pane's first prompt
  runs at 1 fps (see `.bash_env`), so after a `Tab` completion the cursor sat at
  the start of the inserted text for a second.

  `Shift+Tab` still walks backwards and `Enter` still accepts, both unchanged,
  so upstream's flow is intact for anyone who prefers it. Drop the two lines to
  get it back.

Turn it off for one shell with `enable -d flyline`; for the machine, drop the
external and re-apply.
### Terminal Workspaces
Quick reference for the full [terminal vibe-coding workflow](#terminal-vibe-coding-workflow).

The multiplexer is herdr, and the prefix is `ctrl+space`. Full keymap and
reasoning under [Keys](#keys); `ctrl+space ?` shows the live one.

| Key / command | Purpose |
|-------|---------|
| `herdr` | Attach. Nothing autostarts it — a window and an SSH login are both plain shells |
| `herdr --remote <host>` | Attach to *that* machine's server over ssh, as a local thin client — the only route that bridges this desktop's clipboard. `<host>` is any alias from [`~/.ssh/config.d/personal`](#personal-ssh-hosts); add `--session <name>` for a named session there |
| `F2` / `F3` / `F4` | New tab / previous tab / next tab — byobu's three |
| `F7` / `Shift+F7` | Next / previous agent in the priority queue (blocked first) |
| `ctrl+.` / `ctrl+,` | The same queue, without a prefix |
| `F1` | Jump to a tab by name — Go To opens already in search mode |
| `Shift+F1` / `ctrl+space g` | Go To status-first |
| `F6` | Rename tab |
| `F8` / `F9` | Previous / next workspace, across machines |
| `F11` | `pick-agent`: pick Codex, Claude or a shell, in a popup |
| `ctrl+space [` | Copy mode — vim motions, `/` search, `v` select, `y` yank |
| `F5` | The scrollback-into-an-editor dump. Opens at the *last* line — herdr opens it at line 1, the editor configs jump to the end |
| `ctrl+space shift+N` / `shift+G` | New workspace / new workspace from a git worktree |
| `ctrl+space o` | Jump to whatever the last notification was about |
| `ctrl+space t` | Scratch terminal, in a popup |
| `ctrl+space q` | Detach; the server and panes keep running |
| `ctrl+space ?` | List every active binding |
| `herdr session list` | What has accumulated; `herdr session stop\|delete <name>` to clear it |

Kitty and the shell:

| Key / command | Purpose |
|-------|---------|
| `Super+T` / `Ctrl+Alt+T` | Open Kitty from the desktop via XFCE's TerminalEmulator helper (`gui` profiles) |
| new Kitty window | A plain login shell; type `herdr` to attach |
| `ssh <host>` | A plain shell on the far end; run `herdr` there when wanted |
| `Ctrl+Shift+Y` | Open a Kitty window with a **plain** login shell — SSH from here so the remote multiplexer is the only one |
| `Ctrl+Shift+R` | The same plain window, straight into `sshz`: pick a host, `exec ssh` — remote keys are then identical to local ones |
| `Ctrl+Shift+E` | Hint-pick a URL on screen and **copy** it, rejoining one that wrapped onto the next row (see [Copying a URL off the screen](#copying-a-url-off-the-screen)) |
| `Ctrl+Shift+O` | The same picker, but **opens** the URL — Kitty's stock `Ctrl+Shift+E` behaviour, moved aside |
| `sshz [host]` | The picker on its own; hosts come from `~/.ssh/config`, the files it `Include`s, and the `ssh` lines in history |
| `cmd \| clip`, `clip file` | Copy to the clipboard from any shell, host or container — xclip where there is a display, OSC 52 where there is not |

Use a separate Git worktree and herdr workspace for agents that may edit in
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

### PR supervisor (prwatch)
A foreground loop you run in a terminal window, one per repo: it polls the open PRs you wrote or are assigned to every ten minutes (sooner when a worker frees a slot another PR is waiting for), classifies each into a stage, and on a transition notifies through herdr or opens a Claude worker in a herdr tab. The tab stays open for you; exiting Claude in it is the cleanup. Needs `gh`, `herdr` and `dl` (toolbox). No config file, every setting is a flag. Details in [PRs become the queue: prwatch](#prs-become-the-queue-prwatch).

| Command | Purpose |
|-------|---------|
| `prwatch OWNER/NAME` | Watch and dispatch: poll every ten minutes, print the state table and transitions, and give each woken PR a herdr tab running `dl OWNER/NAME@branch --rm -- claude --model opus` — or, if you already have a tab open on that branch, a prompt in that tab instead of a second one. A worker's tab is named the way `dl` names one, `repo@branch`, so it is not distinguishable from one you opened yourself; the PR number is on the pane's metadata, which is what the agents sidebar shows. A notification says when the PR is ready to look at; the tab stays open until you `/exit` it, which deletes the workspace and closes the tab. Ctrl-C stops the polls and leaves the tabs |
| `prwatch OWNER/NAME --dry-run` | The same poll, printing the prompts it would have sent instead of opening tabs |
| `prwatch ~/path/to/clone` | The same, with workers in host `git worktree`s cut from that clone instead of a devlaunch workspace (`--clone PATH` does the same for an `OWNER/NAME`). For repos whose devcontainer will not build here |
| `prwatch OWNER/NAME --once` | One poll, then exit |
| `prwatch OWNER/NAME status` | The last poll's table and queue, no fetch; marks PRs with a busy worker, a worker's open tab, a tab of your own already on the branch, a checkout elsewhere, or a retry owed |
| `prwatch OWNER/NAME dispatch <PR> [--dry-run]` | Push one PR through the worker at its current stage |
| `--interval 10m` `--max-workers 5` `--round-budget 8` `--model opus` `--no-rerun` `--stale-days 7` `--worker-timeout 30m` `--startup-timeout 15m` `--base main` `--workspace ID` | The knobs, with their defaults. `--interval` is the *idle* cadence: when a PR is queued behind `--max-workers`, a worker finishing wakes the next poll early instead of leaving its slot idle until the tick. `--model` is the model every worker runs on — a worker inherits nothing from the terminal that started it, so without this each one takes whatever the CLI default happens to be; `--no-rerun` disables the once-per-head retry of a failed check; `--startup-timeout` bounds the devcontainer build; `--workspace` picks the herdr workspace for worker tabs |

State per repo under `~/.local/state/prwatch/OWNER/NAME/`: `state.json`, `queue.json`, `transitions.json`, `raw/` (the API responses), `logs/` (worker transcripts), `workers/` (one marker per open tab), `worktrees/`.

### Stacked PRs
A stack is a chain of branches/PRs from `main` up to your top branch. The agent commits each change onto the branch it belongs to; `/stack sync` does the bookkeeping. GitHub PRs are the source of truth for topology. Two commands:

| Command | Purpose |
|-------|---------|
| `/stack create <N>` | Slice the current branch into an N-PR stack (N−1 interior branches + the original kept as top). Shows the proposed split first. |
| `/stack sync` | Idempotent bookkeeping from any state: restack each branch onto its parent (bottom→top, onto latest `main`), reconcile/create/retarget PRs, prune merged branches, `push --force-with-lease`. |

Commit each change onto whichever branch it belongs to, then run `/stack sync`; descendants restack and every PR updates. `gh pr checkout <n>` jumps to any PR's branch natively.

### Code review
Three review skills that share one body of review content. `~/.claude/shared-skills/review-self/references/review-core.md` holds the whole review — what to attack (boundaries, error paths, untested branches, interaction with unchanged code, lifetimes, concurrency, wire compatibility, resources), how to prove a finding as concrete inputs → wrong result and then try to refute it, when to run `/constructive-modeling` over changed types, comment verbosity, and the bar for what counts. Both review skills read that file, so the review is identical either way; each `SKILL.md` is only the half that differs — the **output**. Either one runs as two parallel subagents on independent axes: **Defects** (the adversarial read) and **Spec** (conformance against the ticket the PR closes). The spec is resolved deterministically and never asked for — where nothing resolves, the axis reports *no spec available* and is skipped, because a spec reconstructed from the diff grades the diff against itself and always passes. Correctness ranks first wherever a cap or a reader’s attention has to be spent.

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

### Desktop (Xfce)
Gated on `gui`. Applied by `run_onchange_after_apply-xfconf.sh.tmpl` through
`xfconf-query`, not as managed XML: xfconfd owns
`~/.config/xfce4/xfconf/xfce-perchannel-xml/*.xml` and rewrites them from its
in-memory cache when the session exits, so a chezmoi-managed copy is silently
reverted at logout and reported as drift on every apply after that.

| Key | Action |
|-----|--------|
| `Super+←/→/↑/↓` | tile window to that half (Xfce default) |
| `Super+KP7/KP9/KP1/KP3` | tile window to that corner (Xfce default) |
| `Super+\` | terminator |
| `Super+E` | mousepad |
| `Super+R` | xfce4-appfinder — overrides the stock `xfrun4` |
| `Super+1` | parole |
| `Super+3` / `Super+4` | LibreOffice Writer / Calc |
| `Ctrl+Alt+Del` | lock (`xflock4`) — the stock binding is the logout dialog, one stray keystroke from shut down |
| `Ctrl+F1`–`Ctrl+F12` | switch to workspace N |
| `Ctrl+Alt+←/→` | previous / next workspace |
| `Super` (tap) / `Ctrl+Escape` | Whisker Menu — but see the Super conflict below |
| Play / Pause / Next / Prev media keys | Spotify (or any non-browser MPRIS player) — see the media-key note below |

**Xubuntu 25.04 broke tap-Super-for-the-menu and `Super`+key window shortcuts
into an either/or, and this restores both.** From the
`xubuntu-default-settings` changelog:

```
xubuntu-default-settings (25.04.0) plucky
  * etc/xdg/xdg-xubuntu/autostart/xcape-super-binding.desktop,
    etc/xdg/xdg-xubuntu/xfce4/xfconf/.../xfce4-keyboard-shortcuts.xml,
    debian/xubuntu-default-settings.maintscript:
    - Replace xcape Super key binding with native support (LP: #2084326)
```

Through 24.04 an autostart ran `xcape`, which synthesises the menu key only when
Super is tapped *alone*. Super was never bound in xfconf, so there was no grab and
it stayed a real modifier. 25.04 deleted that autostart and bound `Super_L` /
`Super_R` directly instead — and a native binding on a bare modifier is a passive
X grab with `modifiers=0` that consumes the Super *press*, so every `Super`
combination dies with it, keypad spellings included.

Confirmed with `xev`: with the native binding in place, `Super+Left` produced no
`Super_L` event at all and the `Left` arrived as `state 0x0` with no Mod4 bit, and
`Super+Left`, `Super+KP_Left` and `Super+KP_7` were all no-ops. Remove it and
`Super_L` fires as keycode 133 while the `Left` is correctly grabbed by the WM.
`Alt+Shift+Left`, as a control, worked throughout. Upstream Xfce never had this
problem — it ships only the keypad spellings and binds nothing to bare Super.

So the script drops the native bindings and `dot_config/autostart` brings the
xcape autostart back, mapping a Super tap to `Ctrl+Escape` — which the same
Xubuntu defaults already bind to the menu. Net effect: 24.04's behaviour.

**`xcape` is apt-only and is the one manual step in this setup:**

```bash
sudo apt install xcape
```

The `xcape` on conda-forge is an unrelated atmospheric-science Python package, so
the pixi manifest cannot supply it. Until the binary exists the script leaves the
native bindings alone — taking the menu away without xcape to give it back would
be strictly worse — and prints the command. It is also X11-only: under the
`xfce-wayland` session neither half works and it needs solving in the compositor.

It also sets four workspaces, edge-drag tiling, and snapping to both screen edges
and other windows' edges. The workspace count is the one that bites: a fresh
Xubuntu 26.04 install comes up with a *single* workspace, which leaves every
workspace shortcut above bound and completely inert — about thirty keys that look
correctly configured in the settings dialog and do nothing.

**Media keys go to the wrong player unless the browsers are ignored.** Nothing
delivers Play/Pause/Next/Prev to Spotify directly: the pulseaudio panel plugin
grabs them and forwards each press as one MPRIS call to the *one* player whose
playback status changed most recently. Chrome registers an MPRIS player as soon
as any tab has had media in it and touches it whenever such a tab changes state,
so a YouTube tab paused hours ago is routinely the "most recent" player — Play
goes there, nothing audible happens, and Spotify's shortcuts look dead. Seen with
`dbus-monitor`: one `XF86AudioPlay` arrived at
`org.mpris.MediaPlayer2.chromium.instance4817` and Spotify got nothing. The script
sets the plugin's `ignored-players` to `Chrome;Tor Browser`, so the keys only ever
reach a music player. Media keys therefore do not control video in a browser tab;
that is the trade. `multimedia-keys-to-all` was the other option and was rejected
because it resumes the paused video too.

Do not toggle the plugin's *Enable multimedia keys* box to "fix" this. Every write
to that property makes the plugin bind the keys again without unbinding, and N
bindings mean N PlayPause calls per press — an even N is a key that visibly does
nothing. `xfce4-panel --restart` is the reset if it ever gets into that state.

### Utilities
| Alias | Command |
|-------|---------|
| `grep` | `grep --color=auto` |
| `mkdir` | `mkdir -pv` |
| `df` / `du` / `free` | `-h` (human-readable sizes) |
| `rm` / `cp` / `mv` | `-i` (prompt before overwrite) |
| `ags-who` | What holds the RAM on a devlaunch host: OOM kills in the last hour, per-container memory, CPU and `IMAGE STALE`, Claude sessions, `/tmp/claude-<uid>` |
| `ags-who --workspaces` | The dl workspaces you can remove (PR merged/closed or not yours, nothing to lose), the rest with the reason, and the `dl rm "$i"` loop |

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
| `ck` | Use the kinisi Claude login (`~/.claude`) in this shell: host `claude` and `dl`/`aid` all follow it |
| `cb` | Use the bear Claude login (`~/.claude-profiles/bear`) in this shell. The first run makes the profile; sign in once with `claude`, then `/login` |
| `claude-login` | Sign into Claude Code through the saved Chrome profile; after clicking Copy code, it submits the code to the terminal. `--auto-copy` uses an isolated profile to click Copy automatically. |
| `usage-digest` | Print yesterday's usage numbers and the running usage-review experiments. The first interactive shell of the day prints it by itself (host only). |
| `usage-db` | Open DuckDB with the usage logs loaded as tables (Claude hooks, herdr, devlaunch/aid, transcript turns and prompts) for ad-hoc SQL. `.read <file>.sql` runs a saved query. |

`.bash_env` exports `CLAUDE_CONFIG_DIR=$HOME/.claude`, which moves
`.claude.json` — the logged-in account and per-project history — from
`~/.claude.json` into the config directory itself. For workspaces whose
devcontainer mounts `~/.claude`, the file has to be inside it for the host and
container to agree on who is logged in; left at the default
they share one set of credentials while reading two different account records.
Nothing else moves, and a container that sets the variable itself keeps its own
value. The trade is that every session now writes one file, so simultaneous
exits can lose a project's history — see the comment in `private_dot_bash_env`.

`ck` and `cb` only set `CLAUDE_CONFIG_DIR` (and `CLAUDE_PROFILE`, for display).
`dl` and `aid` forward the token in `$CLAUDE_CONFIG_DIR/.credentials.json`, so a
workspace started from a `cb` shell runs as bear without `--claude-profile`. The
bear profile holds its own `.credentials.json` and `.claude.json` and symlinks
everything else to `~/.claude`, so settings, skills, hooks and memory are shared.
`dl` forwards only the short-lived access token, so the `dl`/`aid` wrappers
refresh it with one small `haiku` request when under five minutes are left. Inside a
container that mounts `~/.claude`, `claude` still shows the kinisi account in its
UI and Remote Control, but its requests use the forwarded bear token.

`.bash_env` also exports `CLAUDE_CODE_TMPDIR=~/.cache/claude-tmp`, so Claude's
scratchpad and task output go to disk, not to the tmpfs `/tmp` (which is RAM).
`~/.config/user-tmpfiles.d/claude-tmp.conf` deletes files there after 7 days
unused, and `run_onchange_enable-tmpfiles-clean.sh` enables the user timer that
runs it.

**Shared skills have one copy** in `~/.claude/shared-skills/<name>/`.
Chezmoi manages relative links from `~/.claude/skills/<name>` and
`~/.agents/skills/<name>`. Invoke them as `/name` in Claude or `$name` in Codex.
For example, `/sync` and `$sync` run the same dotfiles workflow. Sync reads the
current machine's identity/profile policy at runtime, including in containers.

The local skills, sync, `pr` and `stack` live in `private_dot_claude/shared-skills/`.
Fifteen pinned Matt Pocock skills are archive externals extracted into the same
shared tree; `git-guardrails-claude-code` stays Claude-only. Herdr's installer
writes its skill into the shared tree too. The six wf skills retain their
package-owned Claude/Codex installation, so upgrades still move prompts with wf.
The old unmanaged `wayfinder` folder is left alone.

The review core is stored in `review-self/references/review-core.md`; both review
skills link to it. The old `~/.claude/review-core.md` path is a compatibility link.
The old `commands/sync.md`, `commands/pr.md` and `commands/stack.md` are retired to
avoid duplicate Claude `/sync`, `/pr` and `/stack` commands.

**Devlaunch compatibility:** the shared payload stays inside `~/.claude`, so a
workspace mounting that directory carries both Claude's skill links and their
targets, even with a different container username. Codex's `~/.agents/skills`
links are installed by this dotfiles repo in the container. Workspaces with local
Claude configuration receive the payload through chezmoi instead. Existing
workspaces need the updated dotfiles applied to discover these skills in Codex;
no additional host mount is required. If a container also mounts `~/.agents/skills`,
`install.sh` detects that mount and disables the `skillscfg` ownership flag, so
chezmoi leaves those host-owned links alone. `$sync` preserves both ownership
flags across configuration regeneration. A workspace mounting only `.claude/skills`
without the rest of `.claude` must also expose `.claude/shared-skills`.

### Codex CLI
| Alias | Command |
|-------|---------|
| `cdy` | `codex --yolo` |
| `cdyr` | `codex --yolo resume` |
| `$sync` | Sync dotfiles and tools using the shared sync skill (`/sync` in Claude) |

Codex's status line — the bar under the composer — is the one thing in
`~/.codex/config.toml` this repo owns:

```
gpt-5.6-terra xhigh · Context 100% left · devlaunch · ~/projects/devlaunch
```

[`private_dot_codex/modify_private_config.toml`](private_dot_codex/modify_private_config.toml)
sets `[tui].status_line` and passes the rest of the file through untouched,
because Codex is the other writer: `/model` rewrites the model, trusting a
directory adds a `[projects."…"]` block, approving a hook adds a hash under
`[hooks.state]`. A managed file would revert all of that on every apply. Only
the status line is enforced, so a change here reaches every `agents` machine —
and `/statusline`, which writes the same key, is reverted by the next apply.

The value is a list of Codex's own item ids, not a command; there is no hook for
a script of your own the way `~/.claude/statusline.sh` is one. Unknown ids are
dropped silently, and the vocabulary is narrower than `[tui].terminal_title`'s —
`git-branch` is a valid *title* item that the status line renders as nothing.
Verified as working on 0.154.0: `model-with-reasoning`, `context-remaining`,
`context-used`, `total-input-tokens`, `total-output-tokens`, `weekly-limit`,
`codex-version`, `fast-mode`, `project-name`, `current-dir`. Preview a different
set with `/statusline`, then copy it into the script to keep it.

### Dev Containers (dl / aid)
[devlaunch](https://github.com/blooop/devlaunch) opens a repo's own devcontainer as a devpod workspace — one per branch, each with its own clone, so several agents work at once without sharing a tree. It forwards the host's `gh` token in as `GH_TOKEN`, defaults to `--ide none` so nothing opens over the terminal, and handles git-lfs. `aid` is the same thing with a coding agent already started. `toolbox` machines only — never inside a container, which is where it *sends* work.

| Command | Purpose |
|-------|---------|
| `dl <owner/repo>` | Open (creating if needed) the workspace for a repo's default branch and attach a shell |
| `dl <owner/repo>@<branch>` | Same, on a branch — its own clone and container, created locally off the default branch if the branch is new |
| `dl <path>` | Open a checkout already on disk |
| `dl <workspace> -- <cmd>` | Run one command in the workspace instead of attaching (a shell line, not an argv — quote what must stay one word) |
| `dl <workspace> up` | Start or create the workspace without attaching; `wf` uses this to warm a container while you are still choosing (needs devlaunch ≥ 0.0.24) |
| `dl --install` | Refresh completions and `~/.local/bin/dl-herdr-shell`; chezmoi also manages an identical pane-shell bridge |
| `dl --purge` | Remove devlaunch's clones and the workspaces made from them, naming anything that refused |
| `aid <workspace> [prompt]` | `dl … -- claude --dangerously-skip-permissions '<prompt>'` — the workspace with an agent in it |
| `dl-next`, `aid-next` | The working tree of a devlaunch checkout (`./dev.sh`), kept under separate names so the released `dl` stays the one that opens real workspaces |

`wf` shells out to `dl` for the same reason: a ticket whose checkout declares a `.devcontainer/devcontainer.json` launches its agent in a container instead of on the host, and says `(devlaunch)` in the launch notice when it does. No `dl`, or one older than the version that `wf` build needs, and the launch runs on the host with the reason stated.

HerdR's `terminal.default_shell` points at `dl-herdr-shell`. Splitting a pane in a
tab that currently holds `dl` or `aid` opens the new shell in the same DevPod
workspace; a tab with no live Devlaunch transport opens the ordinary host shell.

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
| `vst [token]` | terminal sibling of `vs`: pick one local/remote container and open a login shell in its workspace through ags |
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

The status line does **not** need this — `~/.claude/statusline.sh` resolves the binary through the `~/.local/share` mount on its own. Everything else interactive (Neovim, fzf keybindings, zoxide, broot, forgit, the prompt, `~/.bash_aliases`) does.

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

### Lost SSH config entries after a sync

**Symptom:** manually-added `Host` blocks disappear from `~/.ssh/config`, seemingly around the time you ran `chezmoi apply` / `/sync`.

**Cause:** not chezmoi. It manages exactly one block in `~/.ssh/config` — the `Include` described in [Personal SSH hosts](#personal-ssh-hosts) — and `private_dot_ssh/modify_private_config` is a `modify_` script, so everything outside that block reaches it on stdin and is written back untouched. The real culprit is **DevPod**, which rewrites `~/.ssh/config` in place every time a workspace is created, recreated, or deleted. It inserts/prunes blocks between `# DevPod Start <ws>` / `# DevPod End <ws>` markers, and when those markers get unbalanced (e.g. an orphaned `Start` with no matching `End`) a prune can delete everything down to the next marker — taking your hand-written entries with it. The chezmoi correlation is indirect: `install.sh`'s devpod configuration step and `dl`/devpod activity tend to happen right after a sync, and that's what rewrites the file.

**Fix — move your personal entries out of DevPod's blast radius.** DevPod only edits `~/.ssh/config` itself, never files it `Include`s, and chezmoi now ships that `Include` on every machine:

```sshconfig
# ~/.ssh/config — written at the top of the file by chezmoi
Include config.d/*
```

So the fix is just to put your own `Host` entries in `~/.ssh/config.d/personal`. DevPod keeps churning `config`; your entries live in a file it never opens. Above the first `# DevPod Start` is deliberate — an over-deleting prune runs *downward* from an orphaned marker, so the top of the file is the one place nothing can reach.

**Hardening:**

- Delete any orphaned `# DevPod Start …` line that has no matching `# DevPod End` — those are what make a prune over-delete.
- `config.d/personal` is deliberately **not** tracked, because this repo is public and the file is a list of internal hostnames and addresses. The cost is that hosts do not travel between machines. To make them travel, manage the file with [age encryption](https://www.chezmoi.io/user-guide/encryption/age/) (`encrypted_` prefix) — never in plaintext.

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

On a `personal` host this can no longer bite git traffic to **github.com itself**: `dot_gitconfig.tmpl` rewrites `https://github.com/` to `git@github.com:`, so those operations never reach the HTTPS credential path. It still applies to `gist.github.com`, which the rewrite does not match, and to every profile that does not get the rewrite — `shared`, which lacks the `identity` flag. Keep the helper configured regardless: the rewrite is not a substitute for it, and `gh` itself authenticates over the API rather than through git.

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

**If the prompt is still uncolored after that fix:** the `tput setaf 1` guard fails when the `xterm-kitty` terminfo entry is missing, so the override never fires. Check with `ls ~/.terminfo/x/xterm-kitty` and `tput setaf 1; echo $?`. This is why `.terminfo` is *not* gated on `.gui` in `.chezmoiignore.tmpl` — Kitty runs locally, but `TERM=xterm-kitty` travels over SSH into headless `shared`/`container` boxes that need the entry just as much.

Setting `term xterm-256color` in `kitty.conf` would also work but is not used — it costs kitty-specific escape sequences (styled underlines, graphics protocol, extended keyboard) that programs discover through terminfo.
