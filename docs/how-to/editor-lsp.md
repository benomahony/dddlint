---
icon: lucide/monitor
---

# Get editor diagnostics (LSP)

dddlint ships a Language Server that publishes diagnostics as you work and
offers a one-click rename from an alias to its canonical term.

![dddlint diagnostics inline in an editor](../assets/dddlint-lsp.png){ loading=lazy }

## How the server behaves

- It publishes diagnostics on **file open** and **file save**.
- Each run scans the **entire workspace**, so cross-file
  [drift](../reference/rules.md#drift) is always caught, not just the open file.
- [Alias findings](../reference/rules.md#alias) carry a code action that renames
  the identifier to the canonical term with case preserved
  (`ClientRepo` → `CustomerRepo`, `get_client` → `get_customer`).

The command to launch it over stdio is:

```sh
dddlint lsp
```

## Neovim

Attach the server on any buffer inside a project that has a `dddlint.yaml`. No
filetype list needed, since it is language-agnostic.

```lua title="init.lua"
vim.api.nvim_create_autocmd("BufReadPost", {
  callback = function(args)
    local root = vim.fs.root(args.buf, { "dddlint.yaml" })
    if root then
      vim.lsp.start({
        name = "dddlint",
        cmd = { "dddlint", "lsp" },
        root_dir = root,
      }, { bufnr = args.buf })
    end
  end,
})
```

## VS Code

Use a generic LSP client extension and point it at `dddlint lsp` for all
filetypes:

```json title="settings.json"
{
  "lsp.servers": {
    "dddlint": {
      "command": ["uvx", "dddlint", "lsp"],
      "filetypes": ["*"]
    }
  }
}
```

## Helix

```toml title=".helix/languages.toml"
[language-server.dddlint]
command = "dddlint"
args = ["lsp"]
```
