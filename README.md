# Dotfiles

Personal development environment configuration managed with [Chezmoi](https://www.chezmoi.io/) and [Pixi](https://pixi.sh/).

## Usage

### With DevPod

Use the `--dotfiles` argument to automatically set up your development environment:

```bash
devpod up <project-repo> --dotfiles https://github.com/blooop/dotfiles
```

DevPod will automatically detect and run the `install.sh` script to configure your environment.

### Manual Installation

For traditional setup on host machines:

```bash
curl -fsSL https://pixi.sh/install.sh | bash && \
export PATH="$HOME/.pixi/bin:$PATH" && \
pixi global install chezmoi && \
chezmoi init --apply https://github.com/blooop/dotfiles && \
pixi global sync
```

## What's Included

- **Git configuration and aliases** - Smart configuration that won't overwrite existing git user settings
- **Bash aliases and shell customizations** - Productivity shortcuts and improved command line experience
- **Neovim configuration** - Full IDE-like setup with plugins and keymaps
- **Development tools via Pixi** - Essential CLI tools (fzf, ripgrep, fd, lazygit, etc.)
- **Nerd Fonts** - JetBrainsMono Nerd Font for terminal icons

## Git Configuration

The git configuration is designed to be safe for any repository:

- **Existing git user settings are preserved** - Won't overwrite your work or other git credentials
- **Adds useful aliases** - `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push)
- **Sensible defaults** - Auto-setup remotes, consistent behavior across environments

## Tools Managed by Pixi

Core tools installed globally via Pixi:

- `fzf` - Fuzzy file finder
- `fd` - Fast file search
- `ripgrep` - Fast text search
- `nvim` - Neovim editor
- `lazygit` - Terminal git UI
- `chezmoi` - Dotfiles management
- `htop`, `nvtop` - System monitoring
- And more...

## Compatibility

This dotfiles repository is compatible with both:

- **DevPod** - Automated setup with `--dotfiles` argument
- **Traditional Chezmoi workflow** - Manual installation and management
- **Any Unix-like system** - Linux, macOS, WSL

## Managing Changes

After initial setup, use Chezmoi commands to manage your configuration:

```bash
chezmoi update    # Pull and apply latest changes
chezmoi edit      # Edit configuration files
chezmoi apply     # Apply pending changes
```