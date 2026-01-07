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

Choose the installation level based on your use case:

**Minimal** (shared/untrusted machines - tools only, no git config):
```bash
sudo apt update && sudo apt install -y curl && \
curl -fsSL https://pixi.sh/install.sh | bash && \
export PATH="$HOME/.pixi/bin:$PATH" && \
pixi global install chezmoi && \
chezmoi init --apply --exclude .gitconfig git@github.com:blooop/dotfiles.git && \
pixi global sync
```

**DevPod** (development containers - tools + git config):
```bash
sudo apt update && sudo apt install -y curl && \
curl -fsSL https://pixi.sh/install.sh | bash && \
export PATH="$HOME/.pixi/bin:$PATH" && \
pixi global install chezmoi && \
DEVPOD=1 chezmoi init --apply git@github.com:blooop/dotfiles.git && \
pixi global sync
```

**Full** (personal laptop - complete setup):
```bash
sudo apt update && sudo apt install -y curl && \
curl -fsSL https://pixi.sh/install.sh | bash && \
export PATH="$HOME/.pixi/bin:$PATH" && \
pixi global install chezmoi && \
chezmoi init --apply git@github.com:blooop/dotfiles.git && \
pixi global sync
```

> **Note:** Always inspect scripts before running. You can review files at [github.com/blooop/dotfiles](https://github.com/blooop/dotfiles)

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

The git configuration (included in DevPod and Full installations) provides:

- **Useful aliases** - `pom` (pull origin main), `cam` (commit -am), `pomp` (pull and push)
- **Sensible defaults** - Auto-setup remotes, consistent behavior across environments
- **Personal credentials** - Uses Austin Gregg-Smith's git user info (use Minimal installation to avoid this)

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