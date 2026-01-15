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

# Check if we're in a DevPod environment and set appropriate profile
if [[ -n "$DEVPOD" ]]; then
    info "Detected DevPod environment"
    INSTALL_PROFILE="devpod"
else
    info "Running in standalone mode"
    INSTALL_PROFILE="full"
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

# Install pixi if not present
if ! command -v pixi &> /dev/null; then
    info "Installing pixi..."
    curl -fsSL https://pixi.sh/install.sh | bash
    export PATH="$HOME/.pixi/bin:$PATH"
    success "Pixi installed successfully"
else
    info "Pixi already available"
    export PATH="$HOME/.pixi/bin:$PATH"
fi

# Install chezmoi if not present via pixi
if ! command -v chezmoi &> /dev/null; then
    info "Installing chezmoi via pixi..."
    pixi global install chezmoi
    success "Chezmoi installed successfully"
else
    info "Chezmoi already available"
fi

# Ensure pixi is in PATH for the session
export PATH="$HOME/.pixi/bin:$PATH"

# Backup existing pixi-global.toml if it exists (to preserve pre-installed packages)
PIXI_MANIFEST="$HOME/.pixi/manifests/pixi-global.toml"
PIXI_BACKUP=""
if [[ -f "$PIXI_MANIFEST" ]]; then
    info "Backing up existing pixi global manifest..."
    PIXI_BACKUP=$(mktemp)
    cp "$PIXI_MANIFEST" "$PIXI_BACKUP"
fi

# Apply dotfiles using chezmoi
info "Applying dotfiles with chezmoi..."

# If we're running from the dotfiles directory itself (DevPod scenario)
if [[ -f "$PWD/dot_gitconfig" ]]; then
    info "Setting up chezmoi from current directory..."

    # Copy the chezmoi config to the right location first
    if [[ -f "$PWD/dot_chezmoi.toml" ]]; then
        mkdir -p "$HOME/.config/chezmoi"
        cp "$PWD/dot_chezmoi.toml" "$HOME/.config/chezmoi/chezmoi.toml"
    fi

    # Initialize chezmoi and copy source files
    chezmoi init
    mkdir -p "$HOME/.local/share/chezmoi"
    cp -r "$PWD"/* "$HOME/.local/share/chezmoi/"
    cp -r "$PWD"/.[!.]* "$HOME/.local/share/chezmoi/" 2>/dev/null || true

    # Apply the dotfiles (this will process templates)
    # Use --force to skip prompts in non-interactive DevPod environments
    CHEZMOI_PROFILE="$INSTALL_PROFILE" chezmoi apply --force
else
    # Fallback: clone from GitHub (standalone scenario)
    info "Initializing chezmoi from GitHub repository..."
    CHEZMOI_PROFILE="$INSTALL_PROFILE" chezmoi init --apply --force https://github.com/blooop/dotfiles
fi

# Merge existing pixi packages with dotfiles packages
if [[ -n "$PIXI_BACKUP" && -f "$PIXI_BACKUP" ]]; then
    info "Merging existing pixi packages with dotfiles..."
    # Extract [envs.*] sections from backup that aren't in the new manifest
    # and append them to preserve pre-installed packages
    while IFS= read -r line; do
        if [[ "$line" =~ ^\[envs\.([a-zA-Z0-9_-]+)\]$ ]]; then
            env_name="${BASH_REMATCH[1]}"
            # Check if this env exists in the new manifest
            if ! grep -q "^\[envs\.$env_name\]" "$PIXI_MANIFEST" 2>/dev/null; then
                info "Preserving existing package: $env_name"
                # Read and append this entire env section
                in_section=true
                echo "" >> "$PIXI_MANIFEST"
                echo "$line" >> "$PIXI_MANIFEST"
            else
                in_section=false
            fi
        elif [[ "$in_section" == true ]]; then
            # Continue appending lines until we hit the next section or EOF
            if [[ "$line" =~ ^\[envs\. ]]; then
                in_section=false
            elif [[ -n "$line" ]]; then
                echo "$line" >> "$PIXI_MANIFEST"
            fi
        fi
    done < "$PIXI_BACKUP"
    rm -f "$PIXI_BACKUP"
fi

# Sync pixi global packages
info "Synchronizing pixi global packages..."
pixi global sync

# Make sure shell configuration is reloaded
if [[ -f "$HOME/.bash_aliases" ]]; then
    info "Sourcing bash aliases..."
    source "$HOME/.bash_aliases" || true
fi

success "Dotfiles setup completed successfully!"

# Add pixi to PATH in common shell profiles if not already present
for profile in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [[ -f "$profile" ]] && ! grep -q "pixi/bin" "$profile"; then
        echo "" >> "$profile"
        echo "# Added by dotfiles setup" >> "$profile"
        echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> "$profile"
        info "Added pixi to PATH in $(basename "$profile")"
    fi
done

success "Setup complete! Restart your shell or run 'source ~/.bashrc' to ensure all changes take effect."