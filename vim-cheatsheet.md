# Neovim: search, navigate, read

Reader's reference for this repo's LazyVim setup. Keys verified against a live
instance, not from memory — if this drifts, `<leader>sk` is the source of truth.

Leader is `Space`. Press `<leader>` and wait to see which-key.

## Coming from VS Code

| VS Code | Here |
|---------|------|
| `Ctrl+P` fuzzy-open file | `Ctrl+P` (mapped in `lua/config/keymaps.lua`), or `<leader><space>` |
| `Ctrl+Shift+F` global search | `<leader>/` |
| Sidebar file tree | `<leader>e` |
| `F12` go to definition | `gd` |
| `Shift+F12` find references | `gr` |
| `Ctrl+Shift+O` symbol in file | `<leader>cs` |

The fuzzy-open box matches on the whole path, not just the filename, so
`nvim/plug` finds `lua/plugins/*`. That covers most of what the tree is for
when you half-remember a name.

## The loop that matters

Grep, collect everything, walk it:

```
<leader>sw     grep the word under the cursor
<C-q>          send all matches to the quickfix list
]q  [q         walk them
```

Without the `<C-q>` step a picker is a one-shot jump. With it you get a
worklist, which is what "find every use of this" actually needs.

## Finding

| Key | Action |
|-----|--------|
| `Ctrl+P` / `<leader><space>` | Find files (project root) |
| `<leader>fF` | Find files (cwd instead of root) |
| `<leader>fg` | Find files, git-tracked only |
| `<leader>/` or `<leader>sg` | Grep the project |
| `<leader>sG` | Grep from cwd |
| `<leader>sw` | Grep word under cursor (or visual selection) |
| `<leader>sb` | Fuzzy-search lines in this file |
| `<leader>sB` | Grep across open buffers |
| `<leader>sR` | Resume the last picker, query intact |
| `<leader>,` | Switch buffer |
| `<leader>e` / `<leader>E` | File tree (root / cwd) |
| `<leader>sk` | Search every live keymap |

## Navigating

| Key | Action |
|-----|--------|
| `gd` | Definition |
| `gr` | References |
| `gI` | Implementations |
| `gy` | Type definition |
| `K` | Hover docs |
| `<C-o>` / `<C-i>` | Back / forward in the jumplist |
| `<C-^>` | Last buffer |
| `H` / `L` | Previous / next buffer |
| `]f` `[f` | Next / previous function |
| `]c` `[c` | Next / previous class |
| `]a` `[a` | Next / previous argument |
| `]d` `[d` | Next / previous diagnostic |
| `]q` `[q` | Next / previous quickfix entry |
| `<leader>cs` | Symbol outline (Trouble) |
| `<leader>xx` | Diagnostics list (Trouble) |
| `s` | Flash: 2 chars + label letter, jump anywhere on screen |
| `zM` `zR` `za` | Fold all / unfold all / toggle |
| `%` | Matching bracket |
| `gx` | Open URL or filepath under cursor |

`gd` in, read, `<C-o>` out. That is the whole reading motion, and it nests.

## Reading a diff

| Key | Action |
|-----|--------|
| `]h` / `[h` | Next / previous changed hunk |
| `<leader>ghp` | Preview hunk inline |
| `<leader>gb` | Blame this line |
| `<leader>gf` | Current file's history |
| `<leader>gl` | Git log |
| `<leader>gg` | Floating Lazygit |

Walking `]h` through a working tree beats a pager diff: real highlighting, and
`gd` still works so you can jump out for context and `<C-o>` back.

## Editing, when it comes up

| Key | Action |
|-----|--------|
| `Ctrl+/` | Toggle comment |
| `cif` / `daf` | Change inside / delete around enclosing function |
| `cia` / `daa` | Change inside / delete around argument |
| `ci"` / `da(` | Change inside quotes / delete around parens |
| `<leader>sr` | Project-wide find-and-replace, live buffer (grug-far) |
| `<leader>ca` | Code action |
| `<leader>cr` | Rename symbol |
| `.` | Repeat last change |
| `u` / `<C-r>` | Undo / redo |

Note `<leader>sr` is replace and `<leader>sR` is resume — easy to transpose.

## Completion (blink.cmp, `enter` preset)

| Key | Action |
|-----|--------|
| `<C-n>` / `<C-p>` | Next / previous item (insert mode) |
| `<C-space>` | Open menu, then expand docs |
| `<CR>` or `<C-y>` | Accept |
| `<Tab>` / `<S-Tab>` | Next / previous snippet placeholder |
| `<C-e>` | Dismiss |

`<C-p>` is blink's in insert mode, which is why the file-picker mapping is
normal-mode only.

## Windows and panes

| Key | Action |
|-----|--------|
| `Ctrl+h/j/k/l` | Move between splits, then out to the neighbouring Zellij pane |
| `<leader>-` | Split below |
| `<leader>\|` | Split right |
| `<leader>qs` | Restore the last session for this directory |
