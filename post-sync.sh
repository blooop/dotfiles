#!/bin/bash

# Configuration that can only run AFTER `pixi global sync`.
#
# Both steps below configure a tool that pixi installs, so neither can live in a
# chezmoi run script: chezmoi's script phase runs during the apply, and the apply
# runs before the sync that puts the tool on PATH. A `run_once_` script gated on
# the command skipped with "not found" on every fresh machine and then never ran
# again, run_once having recorded its success. A `run_onchange_` one is no better
# — it re-runs when its content changes, not when a tool appears.
#
# So they ran from install.sh instead, which was correct and still left a hole:
# install.sh is not what a routine sync runs. The sync skill does its own
# init/apply/pixi sequence and stopped after the sync, so on a machine that had
# not re-run install.sh since these blocks landed, neither had ever happened —
# which is how DOTFILES_URL came to be unset on a fully synced machine. This file
# is the one copy both callers run, so a third step added here reaches both.
#
# Idempotent by construction: safe to run on every sync, and a no-op on a machine
# already configured. Failures warn rather than exit — neither step is worth
# failing a container start or a sync over.

set -uo pipefail

BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'
info() { echo -e "${BLUE}INFO: $1${NC}"; }
warning() { echo -e "${YELLOW}WARNING: $1${NC}"; }

DOTFILES_REPO="https://github.com/blooop/dotfiles"

# Read a chezmoi capability flag, defaulting to "false" when chezmoi cannot
# answer. A missing or unreadable flag must not be treated as permission.
flag() {
    local value
    value=$(chezmoi execute-template "{{ .$1 }}" 2>/dev/null) || return 1
    [[ "$value" == "true" ]]
}

if ! command -v chezmoi >/dev/null 2>&1; then
    warning "chezmoi is not on PATH — skipping post-sync configuration."
    exit 0
fi

# --- devpod's DOTFILES_URL -------------------------------------------------
#
# Guarded on the .heavy flag AND on the command, not on the command alone:
# inside a devpod-opened workspace an injected agent CLI sits at
# /usr/local/bin/devpod, so "devpod exists" is true in exactly the containers
# this must not touch.
#
# Note the -o. `devpod context set-options` takes its KEY=VALUE through the
# --option flag; the bare form is a silent no-op that reports success.
if flag heavy && command -v devpod >/dev/null 2>&1; then
    info "Pointing devpod's DOTFILES_URL at this repo..."
    devpod context set-options -o "DOTFILES_URL=$DOTFILES_REPO" ||
        warning "Could not set devpod DOTFILES_URL — run 'devpod context set-options -o DOTFILES_URL=$DOTFILES_REPO' by hand."
fi

# --- wf's skills into ~/.claude/skills --------------------------------------
#
# Gated on the claudecfg flag: where chezmoi does not own ~/.claude, writing
# symlinks through somebody else's bind mount is exactly what that flag exists
# to prevent.
if command -v wf >/dev/null 2>&1 && flag claudecfg; then
    info "Linking wf's skills into ~/.claude/skills..."
    wf skills install ||
        warning "Some wf skills could not be linked — see the output above, then re-run 'wf skills install'."
fi
