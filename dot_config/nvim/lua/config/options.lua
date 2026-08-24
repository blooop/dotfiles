-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

vim.opt.relativenumber = true
vim.opt.number = true

-- === Clipboard ===
-- xclip when there is a display for it to reach, OSC 52 through the terminal
-- otherwise.
--
-- LazyVim sets clipboard=unnamedplus unless $SSH_CONNECTION is set, so every
-- plain `y` goes to whatever provider Neovim can find. Neovim finds xclip on a
-- desktop and switches to OSC 52 on its own over SSH ($SSH_TTY) — but a
-- devcontainer is neither case: `docker exec` sets no SSH_* variables and
-- forwards no X socket, so nvim came up with unnamedplus and no provider at all
-- ("clipboard: No provider") and every yank stayed inside the container.
--
-- The test is deliberately about the display, not the binary: xclip IS installed
-- in containers (see the .editor/.toolbox union in the pixi manifest), and it
-- cannot work there, so `executable("xclip")` would pick exactly the wrong
-- provider in exactly the case this is here to fix.
local has_display = (vim.env.DISPLAY or vim.env.WAYLAND_DISPLAY) ~= nil
local has_tool = vim.fn.executable("xclip") == 1 or vim.fn.executable("wl-copy") == 1

if not (has_display and has_tool) then
  local osc52 = require("vim.ui.clipboard.osc52")
  vim.g.clipboard = {
    name = "OSC 52",
    copy = { ["+"] = osc52.copy("+"), ["*"] = osc52.copy("*") },
    -- Paste comes from the register, not from the terminal. Kitty's
    -- clipboard_control denies OSC 52 *reads* by default, so an actual paste
    -- request answers with nothing; serving it from the unnamed register makes
    -- `"+p` give back the last yank instead of silently pasting empty.
    paste = {
      ["+"] = function()
        return vim.split(vim.fn.getreg('"'), "\n")
      end,
      ["*"] = function()
        return vim.split(vim.fn.getreg('"'), "\n")
      end,
    },
  }
end

-- Having a provider is only half of it: `clipboard` decides whether a bare `y`
-- is routed through that provider at all, and LazyVim blanks it whenever
-- $SSH_CONNECTION is set (`opt.clipboard = vim.env.SSH_CONNECTION and "" or
-- "unnamedplus"`). Its reason is the paste round-trip -- with unnamedplus, every
-- paste asks the terminal to read the clipboard back, and a terminal that denies
-- OSC 52 reads leaves nvim blocking on an answer that never comes.
--
-- That reason does not survive the paste override above. Paste is served from the
-- unnamed register and never touches the wire, so there is no read to hang on and
-- nothing left to protect against. Blanking `clipboard` therefore only breaks the
-- copy half: on an SSH host, xclip is unreachable AND `y` is unrouted, so a yank
-- in the F5 scrollback buffer went nowhere and `"+y` was the only way out.
--
-- Set it back. This is what the README's Clipboard section already promises
-- ("`clipboard` stays `unnamedplus`, so a bare `y` is enough") -- that held in a
-- container, where docker exec sets no SSH_* vars and LazyVim's rule never fires,
-- and silently did not on any SSH host.
vim.opt.clipboard = "unnamedplus"
