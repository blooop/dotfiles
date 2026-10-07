-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
--
-- Add any additional autocmds here
-- with `vim.api.nvim_create_autocmd`
--
-- Or remove existing autocmds by their group name (which is prefixed with `lazyvim_` for the defaults)
-- e.g. vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell")

-- Land at the bottom of a herdr scrollback dump.
--
-- herdr's F5 (`edit_scrollback`) writes the pane's scrollback to a temp file and
-- runs it through a hardcoded shell line:
--
--     scrollback_file=/tmp/herdr-scrollback-<pid>-<nanos>-<pane>.txt
--     eval "${EDITOR:-vi} \"$scrollback_file\""; rm -f "$scrollback_file"
--
-- No `+<line>`, so the cursor opens on line 1 -- thousands of lines above the
-- output that was on screen when F5 was pressed. This autocmd opens the dump at
-- the bottom instead.
--
-- It has to be fixed here because herdr 0.9.0 has no knob for it: the command is
-- a string constant in the binary, there is no `editor` config key, and the only
-- input is $EDITOR -- which is eval'd, so `EDITOR="nvim +\$"` would work but
-- would also open `git commit` and every other editor spawn at the last line.
--
-- The window options matter as much as the cursor. A dump is a *grid*: lines are
-- as wide as the pane was, 292 columns here. LazyVim leaves `wrap` on, adds a
-- number column and a sign column, and its `lazyvim_wrap_spell` FileType autocmd
-- turns on `spell` for filetype=text -- which a dump is. So the buffer arrives
-- five columns narrower than the grid it holds, every full-width row (a TUI's
-- box rules, a wide table) folds onto a second display line with a stub of
-- leftovers under it, and terminal output gets spell-underlined on top. That is
-- the mess; it is not a width-accounting bug between herdr and Neovim, which
-- agree on every glyph in the dump -- box drawing, ambiguous widths, VS16 emoji,
-- ZWJ sequences, combining marks and nerd-font PUA all probe identical.
--
-- BufWinEnter rather than BufReadPost because these are window options and
-- because it runs after FileType, which is where the spell setting comes from.
vim.api.nvim_create_autocmd("BufWinEnter", {
  group = vim.api.nvim_create_augroup("herdr_scrollback", { clear = true }),
  pattern = "*herdr-scrollback-*",
  callback = function()
    -- Keep each dumped row on one display line. The number column stays: the
    -- relative numbers are what make `12k` or `5jV` usable in a dump, and with
    -- `wrap` off it only hides a few columns at the right edge rather than
    -- folding every full-width row.
    vim.opt_local.wrap = false
    vim.opt_local.signcolumn = "no"
    vim.opt_local.spell = false
    vim.opt_local.list = false
    vim.cmd("normal! G")
  end,
})
