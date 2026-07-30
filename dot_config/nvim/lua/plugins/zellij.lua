-- Neovim half of the Ctrl+hjkl navigation layer.
--
-- zellij-autolock puts Zellij into Locked mode whenever Neovim owns the focused
-- pane, so Ctrl+hjkl arrives here rather than at Zellij. This plugin moves
-- between Neovim windows first and only crosses into the neighbouring Zellij
-- pane once the cursor is already against that edge of the editor.
--
-- Loaded eagerly: the keymaps are set in lua/config/keymaps.lua so they land
-- after LazyVim's own Ctrl+hjkl window bindings and win.
return {
  {
    "swaits/zellij-nav.nvim",
    lazy = false,
    opts = {},
  },
}
