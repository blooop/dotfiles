# CLAUDE.md

## Project

Chezmoi-managed dotfiles repo. All dotfiles live under `/home/ags/.local/share/chezmoi/` and are applied with `chezmoi apply --force`.

Tools are installed via pixi global (`dot_pixi/manifests/pixi-global.toml.tmpl`).

## Key files

- `private_dot_bash_aliases` — shell aliases and functions
- `private_dot_bash_env` — shell environment, fzf/zoxide/forgit sourcing
- `dot_gitconfig` — git aliases and config
- `dot_pixi/manifests/pixi-global.toml.tmpl` — pixi global packages (templated by profile)

## Rules

- When adding, removing, or changing any alias, keybinding, or shell command, **always update the Cheatsheet section in README.md** to match. The cheatsheet must stay in sync with the actual configuration.
