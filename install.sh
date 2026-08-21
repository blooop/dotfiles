#!/bin/bash

# DevPod Dotfiles Installation Script
# This script is automatically detected and run by DevPod when using --dotfiles
# It sets up the environment using pixi and chezmoi for full compatibility

set -e

echo "Setting up dotfiles with DevPod..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
info() { echo -e "${BLUE}INFO: $1${NC}"; }
success() { echo -e "${GREEN}SUCCESS: $1${NC}"; }
warning() { echo -e "${YELLOW}WARNING: $1${NC}"; }
error() { echo -e "${RED}ERROR: $1${NC}"; exit 1; }

# Resolve machine profile (see .chezmoi.toml.tmpl for the capability matrix):
#   personal | shared | robot | container | kinisi
# Override with CHEZMOI_PROFILE=<profile>; AGS_SHELL/DEVPOD are auto-detected.
#
# The fall-through is `shared`, not `personal`. Nothing here identifies a machine
# positively as yours -- `personal` was simply what was left when the two probes
# above missed -- and `personal` is the only profile with identity, gui, heavy and
# host all on. So an unrecognised environment used to get the most invasive install
# in the matrix, which is how a kinisi container (no KINISI_INSTANCE handshake, so
# never the `kinisi` row) came to write a /home/kinisi kitty.conf onto the host
# through the compose bind-mounts. `shared` keeps identity off and leaves the GUI
# and toolchain trees alone.
#
# A personal machine must now say so: pass CHEZMOI_PROFILE=personal, or omit it and
# answer the prompt interactively. That is the intended trade -- the safe answer is
# the automatic one, and the invasive one is opt-in.
if [[ -n "$CHEZMOI_PROFILE" ]]; then
    info "Using profile from CHEZMOI_PROFILE"
    INSTALL_PROFILE="$CHEZMOI_PROFILE"
elif [[ -n "$AGS_SHELL" ]]; then
    info "Detected ags isolated shell"
    INSTALL_PROFILE="shared"
elif [[ -n "$DEVPOD" ]]; then
    info "Detected DevPod environment"
    INSTALL_PROFILE="container"
else
    info "Unrecognised machine — falling back to the 'shared' profile."
    info "For your own machine: CHEZMOI_PROFILE=personal"
    INSTALL_PROFILE="shared"
fi
info "Installing with profile: $INSTALL_PROFILE"

# Refuse to run at all where $HOME is not this machine's $HOME.
#
# The kinisi compose files bind-mount the host's ~/.config, ~/.local/share,
# ~/.gitconfig and ~/.claude into the container, and the container runs as uid
# 1000 -- the same uid as the host user -- so "the container's $HOME" and "the
# host's $HOME" are one set of directories with full write access. DevPod sets
# DOTFILES_URL globally, so this script then runs inside every such container
# and, from the host's point of view, reaches into its home and:
#
#   - writes `profile = "shared"` into the host's ~/.config/chezmoi/chezmoi.toml
#     (nothing in here identifies a kinisi container: CHEZMOI_PROFILE, AGS_SHELL
#     and DEVPOD are all unset in one, and the `kinisi` row is reachable only via
#     kbash's bootstrap). The host loses identity, gui, heavy and host; the next
#     `pixi global sync` uninstalls kitty-bin, and XFCE's Super+T dies pointing at
#     a binary that is no longer there.
#   - renders every template with homeDir=/home/kinisi, so the host's zellij
#     config ends up naming file:/home/kinisi/... plugins it cannot load.
#   - `rm -rf`s the host's chezmoi source dir, .git and all, in the clone branch
#     below -- which is how an uncommitted shell function was once lost.
#
# The profile fall-through (`shared`, not `personal`) closed the capability half
# of this. It could not close the ownership half, because pixi/xdg stay true for
# `shared`, and .chezmoi.toml.tmpl says as much: "Fixing that needs the ownership
# flags gated on an observed fact rather than on a profile name." This is that
# observed fact, and it is checked here rather than in the template because
# ~/.config/chezmoi/chezmoi.toml is written by `chezmoi init` itself -- no flag
# the template sets can protect the file the template's own config lives in.
#
# The fact: a config tree on a different filesystem from $HOME was mounted in
# from outside, and the mount names a subpath under some *other* home. Both
# halves are required. The first alone would trip on a legitimately separate
# /home partition; the second alone cannot see a bind mount whose subpath
# happens to sit under $HOME, which is a mount of our own and fine.
#
#   host                 $HOME and ~/.config both dev 64513          -> ours
#   devpod workspace     both dev 179 (overlay)                      -> ours
#   kinisi container     $HOME dev 85 (overlay), ~/.config dev 64513,
#                        SOURCE ...[/home/ags/.config]               -> foreign
#
# Skipping is the whole fix, not a degradation: the mounts we just detected are
# the host's *already applied* dotfiles, so a container that skips this script
# still has every file it would have installed. Exit 0 rather than error -- a
# container start must not fail over this.
is_foreign_tree() {
    local dir="$1" home_dev tree_dev sub
    [[ -d "$dir" ]] || return 1
    home_dev=$(stat -c %d "$HOME" 2>/dev/null) || return 1
    tree_dev=$(stat -c %d "$dir" 2>/dev/null) || return 1
    # Same filesystem as $HOME: ours, whatever the mount table says.
    [[ "$home_dev" == "$tree_dev" ]] && return 1
    # A separate filesystem, so something mounted it here. Only positive
    # evidence convicts: findmnt naming a source subpath that is not under
    # $HOME, i.e. some other home. A separate filesystem with no such subpath
    # is a volume or a tmpfs -- legitimate in a devcontainer that caches
    # ~/.config, and not this bug -- so it is left alone.
    if ! command -v findmnt >/dev/null 2>&1; then
        warning "findmnt is unavailable — cannot verify who owns $dir"
        return 1
    fi
    sub=$(findmnt -n -o SOURCE --target "$dir" 2>/dev/null |
        sed -n 's/.*\[\(.*\)\]$/\1/p')
    [[ -n "$sub" && "$sub" != "$HOME"/* ]]
}

FOREIGN_TREES=()
for tree in "$HOME/.config" "$HOME/.local/share"; do
    is_foreign_tree "$tree" && FOREIGN_TREES+=("$tree")
done

if (( ${#FOREIGN_TREES[@]} > 0 )); then
    if [[ -n "${DOTFILES_ALLOW_FOREIGN_HOME:-}" ]]; then
        warning "Foreign home trees detected (${FOREIGN_TREES[*]})"
        warning "DOTFILES_ALLOW_FOREIGN_HOME is set — continuing anyway."
    else
        warning "Refusing to install: \$HOME is not this machine's \$HOME."
        for tree in "${FOREIGN_TREES[@]}"; do
            warning "  $tree is mounted from $(findmnt -n -o SOURCE --target "$tree" 2>/dev/null)"
        done
        info "These trees belong to the host, which has already applied them."
        info "Installing over them would rewrite the host's chezmoi profile and"
        info "delete its source dir. Set DOTFILES_ALLOW_FOREIGN_HOME=1 to override."
        exit 0
    fi
fi

# Fix .cache permissions if owned by root (common in container environments)
CACHE_FIXED=false
if [[ -d "$HOME/.cache" && "$(stat -c '%U' "$HOME/.cache" 2>/dev/null)" == "root" ]]; then
    warning "~/.cache is owned by root, fixing permissions..."
    if sudo chown -R "$USER:$USER" "$HOME/.cache" 2>/dev/null; then
        CACHE_FIXED=true
    fi
fi

# Test if we can write to .cache, use alternative if not
if ! mkdir -p "$HOME/.cache/rattler-test" 2>/dev/null; then
    warning "Cannot write to ~/.cache, using alternative cache location..."
    export RATTLER_CACHE_DIR="$HOME/.pixi/cache"
    mkdir -p "$RATTLER_CACHE_DIR"
    info "Using RATTLER_CACHE_DIR=$RATTLER_CACHE_DIR"
else
    rm -rf "$HOME/.cache/rattler-test"
fi

# Fix .config permissions if owned by root (common in container environments)
# Need full write access since chezmoi creates dirs like ~/.config/lazygit
if [[ -d "$HOME/.config" ]]; then
    # Check if we can write to .config
    if ! touch "$HOME/.config/.write-test" 2>/dev/null; then
        warning "~/.config is not writable, attempting to fix with sudo..."
        if sudo -n chown -R "$USER:$USER" "$HOME/.config" 2>/dev/null; then
            # Verify it actually worked
            if touch "$HOME/.config/.write-test" 2>/dev/null; then
                rm -f "$HOME/.config/.write-test"
                success "Fixed ~/.config permissions"
            else
                warning "sudo chown completed but ~/.config still not writable"
            fi
        else
            warning "Could not fix ~/.config permissions (sudo requires password or unavailable)"
        fi
    else
        rm -f "$HOME/.config/.write-test"
    fi
fi

# Ensure chezmoi config directory is writable
mkdir -p "$HOME/.config/chezmoi" 2>/dev/null || true
if ! touch "$HOME/.config/chezmoi/.write-test" 2>/dev/null; then
    warning "Cannot write to ~/.config/chezmoi, using alternative config location..."
    export XDG_CONFIG_HOME="$HOME/.local/config"
    mkdir -p "$XDG_CONFIG_HOME/chezmoi"
    info "Using XDG_CONFIG_HOME=$XDG_CONFIG_HOME"
else
    rm -f "$HOME/.config/chezmoi/.write-test"
fi

# Where pixi installs. ~/.pixi is not always ours to write: kinisi_ros's
# devcontainer symlinks ~/.pixi/manifests/pixi-global.toml onto a *tracked file
# inside the checkout* (.devcontainer/on_create.sh), so `pixi global install`
# appended through the link and left the workspace's `git status` dirty — the
# chezmoi bootstrap below was one of the two writers that did it.
#
# The test asks about the claim itself, not about who made it: a manifest that
# is a symlink was put there by something that is not us. That is the same test
# private_dot_bash_env makes, and this path must match the one it selects, or
# the shells this script sets up would resolve a different root than it
# installed into. KINISI_INSTANCE is no use here — the compose files set it, a
# devpod launch of the same repo does not.
PIXI_HOME="${PIXI_HOME:-$HOME/.pixi}"
if [[ -L "$PIXI_HOME/manifests/pixi-global.toml" ]]; then
    PIXI_HOME="$HOME/.local/share/pixi-container-$(uname -m)"
    warning "$HOME/.pixi is claimed by the image; installing globals into $PIXI_HOME"
fi
export PIXI_HOME
mkdir -p "$PIXI_HOME/manifests"

# Install pixi if not present
if ! command -v pixi &> /dev/null; then
    info "Installing pixi..."
    # Honours PIXI_HOME, so the binary lands in the root its installs will use.
    curl -fsSL https://pixi.sh/install.sh | bash
    export PATH="$PIXI_HOME/bin:$PATH"
    success "Pixi installed successfully"
else
    info "Pixi already available"
    export PATH="$PIXI_HOME/bin:$PATH"
fi

# Install chezmoi via pixi
if ! command -v chezmoi &> /dev/null; then
    info "Installing chezmoi via pixi..."
    pixi global install chezmoi
    success "Chezmoi installed successfully"
else
    info "Chezmoi already available"
fi

# Ensure pixi is in PATH for the session
export PATH="$PIXI_HOME/bin:$PATH"

# Backup existing pixi-global.toml if it exists (to preserve pre-installed packages)
# Only install yq (for tomlq) when we actually need to merge manifests
#
# Always ~/.pixi's manifest and not $PIXI_HOME's: chezmoi renders
# dot_pixi/manifests/pixi-global.toml.tmpl to one fixed target and knows nothing
# about PIXI_HOME. So this is the file the backup, the apply, the merge and the
# fzf check below all talk about — and where PIXI_HOME points elsewhere, the
# merged result is carried across to it just before the sync. (Writing it costs
# the image nothing: chezmoi replaces the symlink with a regular file rather
# than writing through it, so the checkout is untouched, and the entrypoint's
# `ln -sf` restores the link on the next container start.)
PIXI_MANIFEST="$HOME/.pixi/manifests/pixi-global.toml"
PIXI_BACKUP=""
if [[ -f "$PIXI_MANIFEST" ]]; then
    info "Backing up existing pixi global manifest..."
    PIXI_BACKUP=$(mktemp)
    cp "$PIXI_MANIFEST" "$PIXI_BACKUP"
fi

# Apply dotfiles using chezmoi
info "Applying dotfiles with chezmoi..."

# Final permission fix right before chezmoi runs (in case anything created dirs as root)
if ! touch "$HOME/.config/.write-test" 2>/dev/null; then
    info "Fixing ~/.config and ~/.cache permissions with sudo..."
    sudo chown -R "$USER:$USER" "$HOME/.config" "$HOME/.cache" 2>&1 || warning "chown failed, continuing anyway..."
fi
rm -f "$HOME/.config/.write-test" 2>/dev/null

# If we're running from the dotfiles directory itself (DevPod scenario)
if [[ -f "$PWD/dot_gitconfig.tmpl" ]]; then
    info "Setting up chezmoi from current directory..."

    # Copy source files, then init (init generates ~/.config/chezmoi/chezmoi.toml
    # from .chezmoi.toml.tmpl, pinning the profile for future applies) and apply.
    # Use --force to skip prompts in non-interactive DevPod environments.
    mkdir -p "$HOME/.local/share/chezmoi"
    cp -r "$PWD"/* "$HOME/.local/share/chezmoi/"
    cp -r "$PWD"/.[!.]* "$HOME/.local/share/chezmoi/" 2>/dev/null || true
    CHEZMOI_PROFILE="$INSTALL_PROFILE" chezmoi init --apply --force
else
    # Fallback: clone from GitHub (standalone scenario)
    info "Initializing chezmoi from GitHub repository..."
    # A fast-forward pull, not `rm -rf` and re-clone. The point of the old
    # `rm -rf` was to pick up the latest .chezmoiignore; a pull does that too,
    # and does not throw away work that only exists in this directory. It is the
    # source dir -- uncommitted edits waiting to be committed are its normal
    # state, and the foreign-home guard above is not the only way this line runs
    # somewhere it should not.
    #
    # Anything a fast-forward cannot resolve (dirty tree, diverged, detached) is
    # left exactly as it is and applied from as-is. Being one commit behind is a
    # far cheaper failure than a deleted .git.
    SOURCE_DIR="$HOME/.local/share/chezmoi"
    if [[ -d "$SOURCE_DIR/.git" ]]; then
        info "Updating existing chezmoi source dir..."
        git -C "$SOURCE_DIR" pull --ff-only --quiet ||
            warning "Could not fast-forward $SOURCE_DIR — applying it as-is."
        CHEZMOI_PROFILE="$INSTALL_PROFILE" chezmoi init --apply --force
    else
        if [[ -e "$SOURCE_DIR" ]]; then
            warning "$SOURCE_DIR exists but is not a git repo — replacing it."
            rm -rf "$SOURCE_DIR"
        fi
        CHEZMOI_PROFILE="$INSTALL_PROFILE" chezmoi init --apply --force https://github.com/blooop/dotfiles
    fi
fi

# Merge image-provided pixi envs into the manifest chezmoi just wrote.
#
# `pixi global sync` is declarative: it removes every env the manifest does not
# list, so an env the image installed and this repo does not declare would be
# uninstalled. Only those envs need merging — comparing whole files instead
# (an earlier version diffed the manifest against its own backup) reports
# "matches, skipping" whenever chezmoi did not write the manifest at all, which
# reads like success while silently syncing the image's package list.
if [[ -n "$PIXI_BACKUP" && -f "$PIXI_BACKUP" && -f "$PIXI_MANIFEST" ]]; then
    image_only=()
    while read -r env_name; do
        [[ -n "$env_name" ]] || continue
        grep -q "^\[envs\.${env_name}\]" "$PIXI_MANIFEST" || image_only+=("$env_name")
    done < <(sed -n 's/^\[envs\.\([^]]*\)\].*/\1/p' "$PIXI_BACKUP")

    if (( ${#image_only[@]} > 0 )); then
        info "Preserving image-provided pixi envs: ${image_only[*]}"
        # Only install yq when there is actually something to merge
        pixi global install yq --channel conda-forge
        # Merge: dotfiles config as base, image envs overlaid (preserves what the image shipped)
        # tomlq uses jq syntax: -s slurps files into array, .[0] * .[1] merges, -t outputs TOML
        tomlq -s '.[0] * .[1]' "$PIXI_MANIFEST" "$PIXI_BACKUP" -t > "${PIXI_MANIFEST}.tmp"
        mv "${PIXI_MANIFEST}.tmp" "$PIXI_MANIFEST"
    else
        info "Dotfiles manifest already declares every image-provided env, no merge needed"
    fi
    rm -f "$PIXI_BACKUP"
fi

# The manifest is a managed file (dot_pixi/manifests/pixi-global.toml.tmpl), so
# chezmoi should have written it above. If it is missing or still the image's
# copy, the shell will come up without fzf/zoxide/fd/rg and only say so by not
# having them — worth a loud warning instead.
if ! grep -q '^\[envs\.fzf\]' "$PIXI_MANIFEST" 2>/dev/null; then
    warning "pixi manifest has no fzf env — chezmoi may not be managing $PIXI_MANIFEST"
    warning "(check the .pixi ownership flag in .chezmoi.toml.tmpl for profile $INSTALL_PROFILE)"
fi

# Sync pixi global packages
#
# `pixi global sync` reads $PIXI_HOME/manifests/pixi-global.toml, which is the
# file chezmoi manages only while PIXI_HOME is ~/.pixi. Where the image claimed
# that path, the merged manifest has to be carried across to the root pixi will
# actually sync; without this the container would come up with none of these
# tools, which is the failure the private root exists to avoid, not to cause.
PIXI_SYNC_MANIFEST="$PIXI_HOME/manifests/pixi-global.toml"
if [[ "$PIXI_SYNC_MANIFEST" != "$PIXI_MANIFEST" && -f "$PIXI_MANIFEST" ]]; then
    info "Copying manifest into $PIXI_HOME"
    cp "$PIXI_MANIFEST" "$PIXI_SYNC_MANIFEST"
fi
info "Synchronizing pixi global packages..."
pixi global sync

# Make sure shell configuration is reloaded
if [[ -f "$HOME/.bash_aliases" ]]; then
    info "Sourcing bash aliases..."
    source "$HOME/.bash_aliases" || true
fi

success "Dotfiles setup completed successfully!"

# Add pixi to PATH in common shell profiles if not already present.
#
# The *resolved* root, not a hardcoded ~/.pixi: where the image claimed that
# path, PIXI_HOME is the private root chosen at the top of this script, and a
# profile line naming ~/.pixi/bin would put the wrong directory on PATH. Written
# expanded, because a login shell has no PIXI_HOME of its own to resolve.
#
# Guarded on a marker line rather than on the "pixi/bin" fragment, which the two
# roots cannot both satisfy — `pixi-container-x86_64/bin` does not contain
# `pixi/bin`, so the fragment guard would have appended the private line on
# every single run. A profile already carrying the old fragment gets one extra
# PATH entry, once: harmless, self-limiting, and the price of a guard that
# cannot lie.
#
# Belt and braces either way: private_dot_bash_env re-derives the same root on
# every shell it is sourced into. This is for the shells that never source it.
PIXI_PROFILE_MARK="# Added by dotfiles setup (pixi)"
for profile in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [[ -f "$profile" ]] && ! grep -qxF "$PIXI_PROFILE_MARK" "$profile"; then
        {
            echo ""
            echo "$PIXI_PROFILE_MARK"
            echo "export PATH=\"$PIXI_HOME/bin:\$PATH\""
        } >> "$profile"
        info "Added $PIXI_HOME/bin to PATH in $(basename "$profile")"
    fi
done

success "Setup complete! Restart your shell or run 'source ~/.bashrc' to ensure all changes take effect."