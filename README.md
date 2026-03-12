# Dotfiles

Personal development environment configuration managed with [Chezmoi](https://www.chezmoi.io/) and [Pixi](https://pixi.sh/).

## Usage

### Quick Install

One-liner that handles cache permissions and installs everything:

**DevContainers/DevPod:**
```bash
curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/install.sh | DEVPOD=1 bash
```

**Full (personal machines):**
```bash
curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/install.sh | bash
```

### ags - Isolated Shell (shared/untrusted machines)

`ags` (Austin Gregg-Shell) gives you a full dotfiles environment in an isolated `$HOME` that doesn't affect the host. Nothing is written outside `~/.local/share/ags/` and `~/.local/bin/ags`.

```bash
mkdir -p ~/.local/bin && curl -fsSL https://raw.githubusercontent.com/blooop/dotfiles/main/private_dot_local/private_bin/executable_ags -o ~/.local/bin/ags && chmod +x ~/.local/bin/ags
```

```bash
ags              # enter isolated shell
ags update       # reinstall dotfiles
ags uninstall    # remove ags and cached environment
```

On machines with the full dotfiles already installed, `ags` is also available directly via chezmoi.

### Manual Installation

For more control, choose the installation level based on your use case:

**Minimal** (shared/untrusted machines - tools only, no git config):
```bash
sudo apt update && sudo apt install -y curl && \
curl -fsSL https://pixi.sh/install.sh | bash && \
export PATH="$HOME/.pixi/bin:$PATH" && \
pixi global install chezmoi && \
chezmoi init --apply --exclude .gitconfig git@github.com:blooop/dotfiles.git && \
pixi global sync
```

**DevContainers** (development containers - tools + git config):
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

### Development Containers

For development containers, you have two options:

**DevPod (automated):**

First-time setup - add the Docker provider and configure automatic dotfiles:
```bash
devpod provider add docker
devpod context set-options -o DOTFILES_URL=https://github.com/blooop/dotfiles
```

This configures devpod to automatically install dotfiles for all new workspaces.

Alternatively, use the `--dotfiles` argument for individual workspaces:
```bash
devpod up <project-repo> --dotfiles https://github.com/blooop/dotfiles
```
DevPod will automatically detect and run the `install.sh` script to configure your environment.

**Manual (any devcontainer):**

Use the DevContainers installation command above, or add to your devcontainer configuration.

## What's Included

### Core Tools (All Profiles)
- **Essential CLI tools** - fzf, fd, ripgrep, htop, btop, nvtop
- **Development tools** - chezmoi, lazygit, ccache
- **Editors** - Neovim with full configuration, vim
- **Utilities** - curl, unzip

### Profile-Specific Tools

#### DevContainers Profile (Default for `--dotfiles` and DevContainers installation)
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

The git configuration (included in DevContainers and Full installations) provides:

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
- `htop`, `btop`, `nvtop` - System monitoring
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

This dotfiles repository is compatible with:

- **DevPod & DevContainers** - Automated or manual setup in development containers
- **Traditional Chezmoi workflow** - Manual installation and management
- **Any Unix-like system** - Linux, macOS, WSL

## Cheatsheet

### FZF Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+R` | Fuzzy search command history |
| `Ctrl+T` | Fuzzy find files, insert path |
| `Alt+C` | Fuzzy find directories, cd into it |
| `**<TAB>` | Trigger fzf completion (e.g. `cd **<TAB>`, `ssh **<TAB>`) |

### Navigation

| Command | Action |
|---------|--------|
| `z <query>` | Jump to best-matching directory (zoxide) |
| `zi <query>` | Jump with fzf picker (zoxide) |
| `..` / `...` / `....` | Go up 1/2/3 directories |

### Git — Forgit (fzf-powered)

| Alias | Action |
|-------|--------|
| `ga` | Interactive stage files |
| `gc` | Checkout branch |
| `gcf` | Checkout file |
| `gco` | Checkout commit |
| `gct` | Checkout tag |
| `gd` | Interactive diff |
| `glo` | Interactive log |
| `gbl` | Interactive blame |
| `grb` | Interactive rebase |
| `grh` | Reset head |
| `gss` | Stash show |
| `gsp` | Stash push |
| `gbd` | Branch delete |
| `gclean` | Interactive clean |
| `gfu` | Fixup |
| `gsq` | Squash |
| `gcp` | Cherry pick |
| `grc` | Revert commit |
| `grl` | Reflog |
| `grw` | Reword |

### Git — Plain Aliases

| Alias | Action |
|-------|--------|
| `gs` | `git status` |
| `gp` | `git push` |
| `lg` | `lazygit` |
| `git com` | Checkout main |
| `git pom` | Pull origin main |
| `git cam` | Commit -am |
| `git pomp` | Pull origin main + push |

### Utilities

| Alias | Action |
|-------|--------|
| `ll` | `ls -alF` |
| `la` | `ls -A` |
| `l` | `ls -CF` |
| `cld` | Claude CLI (skip permissions) |
| `cldr` | Claude CLI (resume, skip permissions) |
| `ralph <chain> "prompt"` | Run a hat chain (Claude Code orchestrator) |
| `ralph --list` | List available chains and hats |
| `ralph pr "prompt"` | PR feedback loop (gather/fix/self-review/push until clean) |

## Managing Changes

After initial setup, use Chezmoi commands to manage your configuration:

```bash
chezmoi update    # Pull and apply latest changes
chezmoi edit      # Edit configuration files
chezmoi apply     # Apply pending changes
```
