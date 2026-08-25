# CLAUDE.md

## Project

Chezmoi-managed dotfiles repo. The source dir is `~/.local/share/chezmoi` under
whatever user is applying it — resolve it with `chezmoi source-path`, never assume it.
This repo is used under several usernames, so a `/home/<user>` path must never be
hardcoded anywhere in it. Dotfiles are applied with `chezmoi apply --force`, and git
runs against the source dir via `chezmoi git -- <args>`.

Tools are installed via pixi global (`dot_pixi/manifests/pixi-global.toml.tmpl`).

## Profiles

Machine profiles (`personal`/`shared`/`robot`/`container`) are resolved once at
`chezmoi init` and persisted in `~/.config/chezmoi/chezmoi.toml`. Profiles map to
capability flags (`identity`, `gui`, `heavy`, `host`, `toolbox`) in `.chezmoi.toml.tmpl` — the
ONLY place profile names may be interpreted. Templates must gate on the flags
(e.g. `{{ if .gui }}`), never on profile names or env vars.

## Key files

- `.chezmoi.toml.tmpl` — profile → capability-flag matrix (config template, run at `chezmoi init`)
- `private_dot_bash_aliases` — shell aliases and functions
- `private_dot_bash_env` — shell environment, fzf/zoxide/forgit sourcing
- `dot_gitconfig.tmpl` — git aliases and config (identity gated on `.identity`)
- `dot_pixi/manifests/pixi-global.toml.tmpl` — pixi global packages (gated on capability flags)
- `.chezmoiignore.tmpl` — repo docs excluded from $HOME; config trees gated by flags
- `.chezmoiremove.tmpl` — deletes skills chezmoi no longer manages; every entry guarded on not-a-symlink (gated on `.claudecfg`)

## Rules

- When adding, removing, or changing any alias, keybinding, or shell command, **always update the Cheatsheet section in README.md** to match. The cheatsheet must stay in sync with the actual configuration.
- When adding a pixi package or profile-gated file, gate it on a capability flag, not a profile name. New machine classes are added as one row in `.chezmoi.toml.tmpl`.
- After changing `.chezmoi.toml.tmpl`, run `chezmoi init` (not just `apply`) to regenerate the local config.
- Never hardcode a `/home/<user>` path in repo content or in generated skills. Resolve the source dir dynamically with `chezmoi source-path`, and run git against it as `chezmoi git -- <args>` so it works under any username.
- Wayfinder maps and tickets for this config belong on **`blooop/dotfiles`**. `$HOME` is not
  a git repo, so wayfinder cannot pin the repo from the cwd the way it normally does;
  resolve it from the source dir's own remote instead, and pass `--repo` on every `gh` call:

  ```bash
  REPO=$(chezmoi git -- remote get-url origin |
      sed -E 's#^(ssh://)?(git@github\.com[:/]|https://github\.com/)##; s#\.git$##')
  ```
