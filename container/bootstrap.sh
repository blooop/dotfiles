#!/usr/bin/env bash
# Install personal dotfiles + pixi globals inside a kinisi dev container.
#
# Runs INSIDE the container. install.sh invokes it on the DevPod path; otherwise
# run it by hand with docker exec (see the refusal message below). Reaches
# the container through the ~/.local/share bind-mount that kinisi's compose
# already provides, so nothing in kinisi_ros is modified and teammates are
# unaffected. Re-run any time to repair a broken environment — it is idempotent
# and is the recovery path, not just first-time setup.
#
# Deliberately touches nothing shared:
#   - chezmoi config goes to ~/.local/state (container-local), NOT ~/.config,
#     which is bind-mounted from the host and holds the host's `personal` profile.
#   - pixi installs into a private PIXI_HOME, NOT ~/.pixi, whose manifest the
#     kinisi entrypoint symlinks into the kinisi_ros checkout.
#   - the `kinisi` profile (not `container`) drives .chezmoiignore.tmpl's ownership
#     flags, keeping the apply off every host-mounted tree and off ~/.pixi. A
#     plain DevPod workspace uses `container`, which DOES own those paths.

set -euo pipefail

# The kinisi compose files are the only thing that sets KINISI_INSTANCE, and they
# set it to the empty string for the main clone — hence `+x` set-ness rather than
# a non-empty test. Refusing to run anywhere else is a safety interlock: on the
# host this script would rewrite the real ~/.config/chezmoi profile.
if [ -z "${KINISI_INSTANCE+x}" ]; then
    echo "bootstrap: not inside a kinisi dev container — refusing to run." >&2
    echo "bootstrap: run it from the host with:" >&2
    echo "  docker exec <container> bash -c 'bash \"\$HOME/.local/share/chezmoi/container/bootstrap.sh\"'" >&2
    exit 1
fi

# Source dir is this script's parent's parent. Derived from $0 rather than
# assumed, because the repo is used under several usernames and chezmoi is not
# on PATH yet (so `chezmoi source-path` is not available at this point).
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$(dirname "$script_dir")"

# Must match the PIXI_HOME selection in private_dot_bash_env — the shell resolves
# this independently on every login, so a divergence here silently produces an
# environment that installs to one root and reads from another.
export PIXI_HOME="$HOME/.local/share/pixi-container-$(uname -m)"

echo "bootstrap: source=$source_dir"
echo "bootstrap: PIXI_HOME=$PIXI_HOME"

# --- 1. Personal pixi globals -------------------------------------------------
# The image ships pixi at /usr/local/bin/pixi; PIXI_HOME redirects it away from
# the repo-owned ~/.pixi. `sync` is declarative: it installs what the manifest
# lists and removes what it does not.
mkdir -p "$PIXI_HOME/manifests"
cp "$source_dir/container/pixi-global.toml" "$PIXI_HOME/manifests/pixi-global.toml"

echo "bootstrap: syncing pixi globals..."
pixi global sync

# --- 2. Dotfiles --------------------------------------------------------------
# chezmoi comes from the sync above. Prefer the direct env bin over the exposed
# trampoline in $PIXI_HOME/bin: trampolines embed an absolute prefix, so the env
# binary is the one that keeps working if this tree is ever seen at another path.
chezmoi_bin="$PIXI_HOME/envs/chezmoi/bin/chezmoi"
if [ ! -x "$chezmoi_bin" ]; then
    echo "bootstrap: chezmoi missing after sync — check container/pixi-global.toml" >&2
    exit 1
fi

# ~/.local/state is container-local (only ~/.local/share is bind-mounted), so
# this config never reaches the host.
config_dir="$HOME/.local/state/chezmoi"
config="$config_dir/chezmoi.toml"
mkdir -p "$config_dir"

# Containers bootstrapped before the kinisi profile existed hold profile="container",
# which now owns ~/.config and ~/.pixi — exactly the paths this container must not
# touch. Regenerate any config that is not already on the kinisi profile.
if [ -f "$config" ] && ! grep -q '^[[:space:]]*profile[[:space:]]*=[[:space:]]*"kinisi"' "$config"; then
    echo "bootstrap: stored profile is not 'kinisi' — regenerating config..."
    rm -f "$config"
fi

if [ ! -f "$config" ]; then
    echo "bootstrap: generating kinisi-profile config..."
    CHEZMOI_PROFILE=kinisi "$chezmoi_bin" init \
        --config "$config" --source "$source_dir"
fi

echo "bootstrap: applying dotfiles..."
"$chezmoi_bin" apply --force --config "$config" --source "$source_dir"

echo "bootstrap: done — open a new shell to pick up the environment."
