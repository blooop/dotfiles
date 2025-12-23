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

### Core Tools (All Profiles)
- **Essential CLI tools** - fzf, fd, ripgrep, htop, nvtop
- **Development tools** - chezmoi, lazygit, ccache
- **Editors** - Neovim with full configuration, vim
- **Utilities** - curl, unzip

### Profile-Specific Tools

#### DevPod Profile (Default for `--dotfiles`)
Minimal setup optimized for development containers:
- Excludes git, git-lfs, openssh (provided by container)
- Focuses on productivity tools and editors

#### Full Profile (Default for Manual Install)
Complete setup for host machines:
- **Git tools** - git, git-lfs for full version control
- **SSH tools** - openssh suite for secure connections
- **All core tools** - Everything from DevPod profile plus host-specific tools

### Optional Tools
- **Rust development** - Can be enabled during interactive setup

## Git Configuration

The git configuration is designed to be safe for any repository:

- **Existing git user settings are preserved** - Won't overwrite your work or other git credentials
- **Adds useful aliases** - `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push)
- **Sensible defaults** - Auto-setup remotes, consistent behavior across environments

## Tools Managed by Pixi

### Core Tools (All Profiles)
- `fzf` - Fuzzy file finder
- `fd` - Fast file search
- `ripgrep` - Fast text search
- `nvim` - Neovim editor
- `lazygit` - Terminal git UI
- `chezmoi` - Dotfiles management
- `htop`, `nvtop` - System monitoring
- `ccache` - Compiler caching
- `curl`, `unzip` - Essential utilities

### Full Profile Additional Tools
- `git` - Git version control
- `git-lfs` - Git Large File Storage
- `openssh` - SSH client and server tools

### Configuration
You can customize which profile is used by editing `dot_chezmoi.toml`:

```toml
[data]
    profile = "devpod"  # or "full"
    tools = { rust = false }  # or true to include Rust tools
```

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