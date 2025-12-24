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

# Check if we're in a DevPod environment
if [[ -n "$DEVPOD" ]]; then
    info "Detected DevPod environment"
else
    info "Running in standalone mode"
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
    CHEZMOI_PROFILE=devpod chezmoi apply --force
else
    # Fallback: clone from GitHub (standalone scenario)
    info "Initializing chezmoi from GitHub repository..."
    CHEZMOI_PROFILE=devpod chezmoi init --apply --force https://github.com/blooop/dotfiles
fi

# Sync pixi global packages
info "Synchronizing pixi global packages..."
pixi global sync

# Make sure shell configuration is reloaded
if [[ -f "$HOME/.bash_aliases" ]]; then
    info "Sourcing bash aliases..."
    source "$HOME/.bash_aliases" || true
fi

# Install Nerd Fonts if the script exists (only for full profile)
if [[ -f "$HOME/.local/share/chezmoi/run_once_install-nerd-fonts.sh.tmpl" ]] && [[ "${CHEZMOI_PROFILE}" != "devpod" ]]; then
    info "Installing Nerd Fonts..."
    # The template will be processed by chezmoi, so we don't need to run it manually here
    # This code path is mainly for reference - chezmoi's run_once scripts handle this automatically
fi

success "Dotfiles setup completed successfully!"

# Display helpful information
echo ""
info "Your development environment is now configured with:"
echo "  • Git configuration and aliases"
echo "  • Bash aliases and shell customizations"  
echo "  • Neovim with custom configuration"
echo "  • Essential development tools via pixi"
echo "  • Nerd Fonts for terminal icons"
echo ""
info "To use chezmoi for future updates:"
echo "  chezmoi update    # Pull and apply latest changes"
echo "  chezmoi edit      # Edit configuration files"
echo "  chezmoi apply     # Apply pending changes"
echo ""

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