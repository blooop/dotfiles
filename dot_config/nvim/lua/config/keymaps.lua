-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- VSCode-style comment toggle with Ctrl+/
-- Note: In most terminals, Ctrl+/ is sent as Ctrl+_
vim.keymap.set("n", "<C-_>", "gcc", { remap = true, desc = "Toggle comment" })
vim.keymap.set("v", "<C-_>", "gc", { remap = true, desc = "Toggle comment" })
vim.keymap.set("i", "<C-_>", "<Esc>gcca", { remap = true, desc = "Toggle comment" })

-- Ctrl+hjkl leaves the editor for the neighbouring Zellij pane once there is no
-- Neovim window left in that direction. Set here rather than in the plugin spec
-- so these override LazyVim's plain <C-w>h/j/k/l bindings, which are applied on
-- the same VeryLazy event.
vim.keymap.set("n", "<C-h>", "<cmd>ZellijNavigateLeftTab<cr>", { silent = true, desc = "Window/Zellij pane left" })
vim.keymap.set("n", "<C-j>", "<cmd>ZellijNavigateDown<cr>", { silent = true, desc = "Window/Zellij pane down" })
vim.keymap.set("n", "<C-k>", "<cmd>ZellijNavigateUp<cr>", { silent = true, desc = "Window/Zellij pane up" })
vim.keymap.set("n", "<C-l>", "<cmd>ZellijNavigateRightTab<cr>", { silent = true, desc = "Window/Zellij pane right" })

-- VSCode-style Ctrl+P to fuzzy-open a file. LazyVim already has this on
-- <leader><space>; this is the same picker under the key the muscle memory
-- reaches for. Normal mode only -- <C-p> in insert mode belongs to Blink's
-- completion menu, and inside the picker itself snacks' buffer-local maps win.
--
-- LazyVim.pick("files") rather than Snacks.picker.files() directly, so the
-- search is rooted the way every other LazyVim picker is (LSP root, then git
-- root, then cwd) instead of at whatever cwd the pane happens to have.
vim.keymap.set("n", "<C-p>", LazyVim.pick("files"), { desc = "Find Files (Root Dir)" })
