#!/bin/bash
# Install JetBrainsMono Nerd Font for Neovim icons

set -e

FONT_DIR="$HOME/.local/share/fonts"
FONT_NAME="JetBrainsMono"
FONT_URL="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${FONT_NAME}.zip"

echo "Installing Nerd Fonts for Neovim..."

# Ensure unzip is available
if ! command -v unzip &> /dev/null; then
    pixi global sync > /dev/null 2>&1
fi

# Download and extract font
mkdir -p "$FONT_DIR"
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
curl -fLO "$FONT_URL" 2>&1 | grep -v "^  " || true
unzip -q "${FONT_NAME}.zip" -d "$FONT_DIR"
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Refresh font cache if available
command -v fc-cache &> /dev/null && fc-cache -fv "$FONT_DIR" > /dev/null 2>&1 || true

echo "✓ Nerd Fonts installed"
