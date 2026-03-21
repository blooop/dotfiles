---
allowed-tools: Bash(git:*), Bash(chezmoi:*), Read, Glob, Grep
description: Sync chezmoi dotfiles — pull, merge, apply, push. One command to stay in sync everywhere.
---

## Context

- Chezmoi source dir: `/home/ags/.local/share/chezmoi`
- Current machine state: !`chezmoi status 2>&1 | head -20`
- Source repo status: !`git -C /home/ags/.local/share/chezmoi status --short`
- Current branch: !`git -C /home/ags/.local/share/chezmoi branch --show-current`

## Goal

Fully synchronise this machine's dotfiles with the remote repo — in both directions. After this skill runs, local changes are pushed and remote changes are applied.

## Steps

Execute these steps **in order**. Stop and report if any step fails in a way that can't be auto-resolved.

### 1. Capture local drift

Detect files that have been modified outside chezmoi (edited directly in `~` but not in the source dir):

```
chezmoi diff
```

If there are diffs, run `chezmoi re-add` to pull those changes back into the source directory. Report what was re-added.

### 2. Stage & commit local source changes

In the chezmoi source dir (`/home/ags/.local/share/chezmoi`):

- `git add -A`
- If there are staged changes, commit them with a concise message describing what changed (e.g. "Update bash aliases and claude settings").
- If nothing to commit, skip.

### 3. Pull remote changes

```
git -C /home/ags/.local/share/chezmoi pull --rebase origin main
```

- **If rebase succeeds cleanly:** continue.
- **If there are merge conflicts:**
  1. List the conflicting files.
  2. For each conflict, read the file and resolve it sensibly — prefer the version that adds more content; if ambiguous, keep both sides and flag it to the user.
  3. `git add` resolved files and `git rebase --continue`.
  4. Report every resolution made so the user can verify.

### 4. Apply to home directory

```
chezmoi apply --force
```

This updates `~` from the (now up-to-date) source dir.

### 5. Push

```
git -C /home/ags/.local/share/chezmoi push origin main
```

If push is rejected (remote has new commits since our pull), pull-rebase again and retry once.

### 6. Report

Print a short summary:
- Files re-added from local drift (if any)
- Commits made locally
- Commits pulled from remote
- Conflicts resolved (if any)
- Final status: **in sync** or **action needed** (with details)
