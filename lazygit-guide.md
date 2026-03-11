# Lazygit Guide

Open: `<leader>gg` in neovim, or `lazygit` in terminal

## Layout

```
┌──────────┬──────────────────────────┐
│ Status   │                          │
├──────────┤                          │
│ Files    │   Diff / Preview pane    │
├──────────┤                          │
│ Branches │                          │
├──────────┤                          │
│ Commits  │                          │
├──────────┤                          │
│ Stash    │                          │
└──────────┴──────────────────────────┘
```

Switch panels: `1`-`5` or `h`/`l` (left/right)
Navigate within panel: `j`/`k` (up/down)

## Your Workflow: Review Diffs -> Commit

### 1. View file diffs

| Key | Action |
|-----|--------|
| `2` | Jump to Files panel |
| `j`/`k` | Move between changed files (diff updates in preview) |
| `enter` | Open file's diff in staging view (full screen diff) |
| `escape` | Back to files list |

### 2. Navigate inside a diff (staging view)

After pressing `enter` on a file:

| Key | Action |
|-----|--------|
| `j`/`k` | Move line by line through the diff |
| `{`/`}` | Jump between hunks |
| `ctrl-d`/`ctrl-u` | Half-page scroll down/up |
| `escape` | Back to files list |

### 3. Navigate across files while in staging view

| Key | Action |
|-----|--------|
| `tab` | Switch between staged/unstaged changes panels |
| `escape` then `j`/`k` | Back to file list, move to next file, `enter` again |

### 4. Stage and commit

From the Files panel:

| Key | Action |
|-----|--------|
| `space` | Stage/unstage selected file |
| `a` | Stage/unstage ALL files |
| `enter` then `space` | Stage individual lines inside a diff |
| `enter` then `a` | Stage entire hunk |
| `enter` then `v` | Visual select multiple lines, then `space` to stage |
| `c` | Commit (opens message editor, type message, `enter` to confirm) |
| `A` | Amend last commit with staged changes |

### Quick commit-all flow

1. `a` (stage all) -> `c` (commit) -> type message -> `enter`

## Side-by-Side Diffs with Delta

Install delta for rendered side-by-side diffs:

```bash
# Ubuntu/Debian: download .deb from https://github.com/dandavison/delta/releases
# Arch
pacman -S git-delta
# Homebrew
brew install git-delta
```

Then update lazygit config (`~/.config/lazygit/config.yml`):

```yaml
git:
  paging:
    colorArg: always
    pager: delta --paging=never --side-by-side --line-numbers --dark
```

This renders diffs as:

```
│ old file (left)          │ new file (right)         │
│ line 10: foo = 1         │ line 10: foo = 2         │
│ line 11: bar = 2         │ line 11: bar = 3         │
```

Note: side-by-side works in the preview pane. The staging view
(after pressing `enter`) always uses inline diff for line staging.

## Other Useful Keys

| Key | Action |
|-----|--------|
| `?` | Show all keybindings for current panel |
| `d` | Discard changes in selected file (from files panel) |
| `enter` then `d` | Discard selected lines/hunk |
| `space` | Stage/unstage (context-dependent) |
| `/` | Filter/search within current panel |
| `W` | Open diff menu (mark commits to compare) |
| `[`/`]` | Cycle through diff context size (+/- lines) |
| `q` | Quit lazygit |

## Comparing Commits

1. Navigate to Commits panel (`4`)
2. Press `W` on first commit to mark it
3. Move to second commit -- diff shows automatically
4. Press `enter` to see per-file breakdown
5. Press `escape` or `W` again to exit diff mode

## Tips

- `?` on any panel shows its keybindings -- use this when stuck
- `[` and `]` expand/shrink diff context (show more surrounding lines)
- `x` opens a menu of actions for the current panel
