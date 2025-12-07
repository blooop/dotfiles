#!/bin/bash
# Install JetBrainsMono Nerd Font
# This script runs once per machine via chezmoi
#
# WHY: LazyVim and other terminal applications use Nerd Font icons for a better UI.
#      Without these fonts, you'll see boxes/missing characters instead of icons.

set -e

FONT_DIR="$HOME/.local/share/fonts"
FONT_NAME="JetBrainsMono"
FONT_URL="https://github.com/ryanoasis/nerd-fonts/releases/latest/download/${FONT_NAME}.zip"

echo "========================================="
echo "Installing ${FONT_NAME} Nerd Font"
echo "========================================="
echo ""
echo "WHY? Nerd Fonts provide icons and symbols used by:"
echo "  - LazyVim (file type icons, git status, etc.)"
echo "  - Terminal prompts (starship, powerlevel10k, etc.)"
echo "  - File managers and other CLI tools"
echo ""
echo "Without these fonts, you'll see [] boxes instead of icons."
echo ""

# Ensure unzip is available - if not, run pixi global sync first
if ! command -v unzip &> /dev/null; then
    echo "⚠ unzip not found, running pixi global sync to install it..."
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

echo "Extracting fonts to $FONT_DIR..."
unzip -q "${FONT_NAME}.zip" -d "$FONT_DIR"

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Refresh font cache (optional, may not be available in all environments)
if command -v fc-cache &> /dev/null; then
    echo "Refreshing font cache..."
    fc-cache -fv "$FONT_DIR" > /dev/null 2>&1 || true
else
    echo "⚠ fc-cache not found - font cache not refreshed (you may need to restart your terminal)"
fi

echo ""
echo "========================================="
echo "✓ ${FONT_NAME} Nerd Font installed!"
echo "========================================="
echo ""
echo "NEXT STEPS:"
echo "  1. Configure your terminal to use: ${FONT_NAME} Nerd Font Mono"
echo "  2. Font size: 11-13 recommended"
echo "  3. Restart your terminal for changes to take effect"
echo ""
echo "Fonts installed to: $FONT_DIR"
echo ""
