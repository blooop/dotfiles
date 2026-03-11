# LazyVim Minimal Cheatsheet

Leader = Space

## Files

| Key | Action |
|-----|--------|
| `<leader><space>` | Find files |
| `<leader>/` | Grep across project |
| `<leader>,` | Switch buffer |
| `<leader>e` | Toggle file tree |
| `<leader>E` | File tree (cwd) |

In neo-tree: `a` add, `d` delete, `r` rename, `c` copy, `m` move

## LSP

| Key | Action |
|-----|--------|
| `gd` | Go to definition |
| `gr` | References |
| `K` | Hover docs |
| `<leader>ca` | Code action |
| `<leader>cr` | Rename symbol |
| `<leader>cd` | Line diagnostics |
| `]d` / `[d` | Next/prev diagnostic |

## Autocomplete (nvim-cmp)

| Key | Action |
|-----|--------|
| `<C-n>` / `<C-p>` | Next/prev item |
| `<CR>` | Confirm |
| `<C-Space>` | Trigger completion |
| `<C-e>` | Dismiss |

## Git

| Key | Action |
|-----|--------|
| `<leader>gg` | Open lazygit |
| `]h` / `[h` | Next/prev hunk |
| `<leader>ghs` | Stage hunk |
| `<leader>ghr` | Reset hunk |
| `<leader>ghp` | Preview hunk |
| `<leader>ghb` | Toggle inline blame |

## Flash (fancy motions)

| Key | Action |
|-----|--------|
| `s` | Jump to (forward + back) |
| `S` | Select treesitter node |
| `f` / `F` / `t` / `T` | Enhanced f/t with labels |
| `;` / `,` | Repeat flash jump |

Type `s` + 2 chars, then press the label letter to jump.

## Core Vim

| Key | Action |
|-----|--------|
| `w` / `b` | Next/prev word |
| `}` / `{` | Next/prev paragraph |
| `gg` / `G` | Top/bottom of file |
| `<C-d>` / `<C-u>` | Half-page down/up |
| `<C-^>` | Last buffer |
| `%` | Matching bracket |
| `*` / `#` | Search word under cursor |
| `.` | Repeat last change |
| `ci"` | Change inside quotes |
| `da(` | Delete around parens |
| `:w` | Save |
| `:q` | Quit |
| `u` / `<C-r>` | Undo/redo |

## Windows

| Key | Action |
|-----|--------|
| `<C-h/j/k/l>` | Move between splits |
| `<leader>-` | Split horizontal |
| `<leader>\|` | Split vertical |
