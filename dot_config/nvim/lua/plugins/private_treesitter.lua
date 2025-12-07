-- Treesitter configuration
-- Configure which language parsers to install automatically

return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      -- Only install these languages on first launch
      -- Add more as needed, or use "all" to install everything (slower)
      ensure_installed = {
        -- Essential
        "bash",
        -- "lua",
        -- "vim",
        -- "vimdoc",
        -- "markdown",
        -- "markdown_inline",

        -- Programming languages (add only what you use)
        "python",
        -- "c",
        "cpp",
        -- "rust",
        -- "go",
        -- "java",
        -- "javascript",
        -- "typescript",

        -- Config files
        "json",
        "yaml",
        "toml",
        -- "dockerfile",
        -- "cmake",

        -- Other
        -- "regex",
        -- "query",  -- for treesitter query files
      },

      -- Install parsers synchronously (only applied to `ensure_installed`)
      sync_install = false,

      -- Automatically install missing parsers when entering buffer
      auto_install = true,
    },
  },
}
