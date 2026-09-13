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
-- output that was on screen when F5 was pressed. Zellij's EditScrollback passed
-- the scroll position through to `scrollback_editor` and opened near the bottom,
-- which is the behaviour this restores.
--
-- It has to be fixed here because herdr 0.9.0 has no knob for it: the command is
-- a string constant in the binary, there is no `editor` config key, and the only
-- input is $EDITOR -- which is eval'd, so `EDITOR="nvim +\$"` would work but
-- would also open `git commit` and every other editor spawn at the last line.
vim.api.nvim_create_autocmd("BufReadPost", {
  group = vim.api.nvim_create_augroup("herdr_scrollback", { clear = true }),
  pattern = "*herdr-scrollback-*",
  callback = function(ev)
    vim.api.nvim_buf_call(ev.buf, function()
      vim.cmd("normal! G")
    end)
  end,
})
