#!/bin/bash
# Install JetBrainsMono Nerd Font
# This script runs once per machine via chezmoi

set -e

FONT_DIR="$HOME/.local/share/fonts"
FONT_NAME="JetBrainsMono"
FONT_URL="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${FONT_NAME}.zip"

echo "Installing ${FONT_NAME} Nerd Font..."

# Ensure unzip is available - if not, run pixi global sync first
if ! command -v unzip &> /dev/null; then
    echo "unzip not found, running pixi global sync first..."
    if command -v pixi &> /dev/null; then
        pixi global sync
    else
        echo "ERROR: pixi not found, cannot install unzip"
        exit 1
    fi
fi

# Create fonts directory if it doesn't exist
mkdir -p "$FONT_DIR"

# Download and extract font
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo "Downloading ${FONT_NAME}..."
curl -fLO "$FONT_URL"

echo "Extracting fonts..."
unzip -q "${FONT_NAME}.zip" -d "$FONT_DIR"

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Refresh font cache
echo "Refreshing font cache..."
fc-cache -fv "$FONT_DIR" > /dev/null 2>&1

echo "✓ ${FONT_NAME} Nerd Font installed successfully"
echo "  Installed to: $FONT_DIR"
echo "  Configure your terminal to use: ${FONT_NAME} Nerd Font Mono"
