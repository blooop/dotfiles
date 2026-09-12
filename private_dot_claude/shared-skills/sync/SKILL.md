---
name: sync
description: Sync this machine's chezmoi dotfiles with remote main, apply configuration, reconcile and update pixi tools, and push local changes when the machine has a git identity. Use when the user asks to sync their dotfiles or invokes the sync skill.
---

# Sync dotfiles

Run these steps in order. Stop and report failures that cannot be resolved safely.
Read the current machine's configuration at runtime: this skill can be shared
through a container bind mount and must not inherit the host's identity policy.

## 1. Inspect and capture local changes

Run:

```bash
chezmoi source-path
chezmoi status
chezmoi git -- status --short
chezmoi git -- branch --show-current
chezmoi execute-template '{{ .identity }} {{ .profile }} {{ .claudecfg }} {{ .skillscfg }}'
chezmoi diff
```

Always resolve the source directory with chezmoi; never hardcode a home path.
Run source-repository git commands with `chezmoi git -- <args>`.
If the current branch is not `main`, stop before committing or pulling: do not
mix an active development branch into the sync. If a merge/rebase is already
in progress, report it and resolve its intent before starting another.

When `identity` is true, capture edits made in the home directory with
`chezmoi re-add`, report the paths, then stage with `chezmoi git -- add -A`.
Commit staged changes with a concise message; skip an empty commit.
When `identity` is false, do not re-add, commit, or push. Report local drift;
if apply would overwrite edits the user may want, stop and ask first.

If the diff removes a credential helper from `.gitconfig`, preserve that helper
in the untracked `~/.gitconfig.local` before apply and report the move. Preserve
existing local configuration there.

## 2. Pull

```bash
chezmoi git -- pull --rebase --autostash origin main
```

Resolve conflicts from both versions' intent, preserving local work. If the
intent is ambiguous, stop with the affected paths. Stage resolved files and
continue the rebase; report each resolution. Autostash restoration can itself
conflict: inspect status and the retained stash rather than assuming local work
was restored or lost. Do not apply with unresolved conflicts.

## 3. Regenerate configuration on EVERY sync

Preserve the profile and directory ownership read in step 1. Set
`DOTFILES_CLAUDE_MOUNT` from `claudecfg` and `DOTFILES_SKILLS_MOUNT` from
`skillscfg`: `local` for true, `foreign` for false. Run `chezmoi init` with both
variables and `CHEZMOI_PROFILE` set to the recorded profile. These are
command-scoped environment variables.

Run this even when the pull changed no template. `chezmoi apply` does not
regenerate its config; newly referenced capability keys otherwise abort apply,
and repeating sync cannot fix it. Preserving ownership also prevents a container
from writing through a host bind mount after init.

Read back the profile and ownership. If either unexpectedly changed, stop before
applying and ask the user to resolve the mismatch.

## 4. Apply

```bash
chezmoi apply --force
```

Report any overwritten drift and the credential-helper preservation, if needed.

## 5. Reconcile and update tools

```bash
pixi self-update
pixi global sync
pixi global update
```

Run in order. A self-update failure is nonfatal (for example a package-managed
pixi); report it and continue. A sync/update failure needs resolution before
claiming success. Report tools installed, removed, or updated. Always run global
sync: an environment can exist while its exposed binaries are missing.

## 6. Configure the tools pixi just installed

```bash
bash "$(chezmoi source-path)/post-sync.sh"
```

Run this on EVERY sync, after step 5 and never before it. Some configuration can
only be written once the tool that owns it is on PATH — devpod's `DOTFILES_URL`,
wf's skill links — so it cannot live in a chezmoi run script, whose scripts run
during the apply in step 4. `install.sh` runs this same file for the same
reason. Skipping it is not harmless and not self-correcting: a machine synced
without it opens devpod workspaces with no dotfiles at all, and nothing later in
the sync notices or repairs it.

The script guards each step on the capability flags read in step 1 and is a
no-op where they are off, so it is safe in a container and on a shared machine.
Report what it configured. Its warnings are nonfatal — report them and continue.

## 7. Push when identity is enabled

```bash
chezmoi git -- push origin main
```

Skip this entirely when `identity` is false. If new remote commits reject the
push, pull/rebase again and retry once. If the second pull changes files, repeat
configuration regeneration, apply, tool reconciliation and post-sync
configuration before reporting sync. A second rejection ends the run with
action needed.

## Report

Summarize captured files, commits made/pulled, conflict resolutions, pixi and
package changes, what post-sync configured, and final status: **in sync** or
**action needed** with details.
On machines without identity, explicitly report any uncommitted edits left over.
