# dddlint

Polyglot ubiquitous language linter. Reads class, function, method, and type names across **306 languages** and enforces them against a domain vocabulary: banned terms, non-canonical synonyms, and one concept spelled multiple ways.

Works with any language tree-sitter recognises, without per-language queries. Slots into pre-commit hooks, CI pipelines, and coding agent loops via a non-zero exit code on findings. Ships with an LSP server for inline editor diagnostics and rename code actions.

![dddlint LSP diagnostics inline in an editor](docs/assets/dddlint-lsp.png)

📖 **[Full documentation](https://benomahony.github.io/dddlint/)**

## Install

```sh
uv add dddlint

# dddlint map needs an embedding backend; this one runs locally and offline
uv add 'dddlint[embed-local]'

# or, for a hosted model such as openai:text-embedding-3-small
uv add 'dddlint[embed]'
```

`lint`, `html`, and `lsp` need none of these: only `map` embeds anything.

## Quick start

```sh
# lint current directory (looks for dddlint.yaml)
dddlint lint

# lint a specific path
dddlint lint src/

# report vocabulary insights from name embeddings
dddlint map

# same, plus an interactive scatter plot of the vocabulary
dddlint map --html map.html

# open an interactive language graph in the browser
dddlint html

# start the LSP server (stdio)
dddlint lsp
```

## Config

Place `dddlint.yaml` at the project root. When a path is passed to `lint` or `html`, the config is looked up in that directory first, then falls back to the current working directory.

```yaml
similarity_threshold: 0.85   # how alike two domain or context names may be
enforce_canonical: true       # flag alias terms in addition to forbidden ones

# terms that must never appear in a definition name
forbidden:
  - util
  - helper
  - manager

# paths to skip, gitignore syntax, relative to this file's directory
exclude:
  - src/generated
  - "**/*_pb2.py"

# canonical terms and their aliases
synonyms:
  - canonical: customer
    aliases: [client, user, accountholder]
  - canonical: order
    aliases: [purchase, transaction]

# high-level business domains
domains:
  - name: commerce
    include: ["**/commerce/**"]
    synonyms:
      - canonical: order
        aliases: [purchase]

# bounded contexts, same structure as domains, applied after (context wins on conflict)
contexts:
  - name: billing
    include: ["**/billing/**"]
    forbidden: [discount]
    synonyms:
      - canonical: invoice
        aliases: [bill, statement]
```

Global rules apply everywhere. Domain rules apply to matching paths. Context rules apply after domains, so a context can override a domain synonym.

## Rules

| Rule | Severity | Description |
|---|---|---|
| `forbidden` | error | A definition name contains a banned term |
| `alias` | warning | A definition uses a non-canonical synonym, with a rename suggestion |
| `drift` | info | The same concept is spelled multiple ways across the codebase |
| `config:forbidden-canonical-clash` | error | A term is both forbidden and a canonical synonym |
| `config:alias-conflict` | warning | The same alias maps to different canonicals in different scopes |
| `config:duplicate-name` | info | Two domains or contexts have suspiciously similar names |

Config rules are checked against `dddlint.yaml` itself on every run.

## Insights

`dddlint map` embeds every definition name and compares meaning rather than tokens, catching what `drift` cannot. It always exits `0`, so it informs rather than gates.

| Rule | Description |
|---|---|
| `near-synonym` | Names that mean the same thing while sharing no token |
| `context-outlier` | A name whose vocabulary belongs to a different domain or context |

Vectors are cached in `.dddlint/embeddings.json`, keyed by model and dimensions, so only new names are ever embedded. Configure the model under `embeddings` in `dddlint.yaml`.

## LSP

The LSP server publishes diagnostics on file open and save, scanning the entire workspace each time so cross-file drift is always caught. Alias findings include a code action to rename the identifier to the canonical term with case preserved (`ClientRepo` → `CustomerRepo`, `get_client` → `get_customer`).

**Neovim**, add to `init.lua`:

```lua
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

The autocmd fires on every buffer, attaches only when `dddlint.yaml` is found, and is language-agnostic, so no filetype list is required.

**VS Code**, via a generic LSP client extension:

```json
{
  "lsp.servers": {
    "dddlint": {
      "command": ["uvx", "dddlint", "lsp"],
      "filetypes": ["*"]
    }
  }
}
```

**Helix**, `.helix/languages.toml`:

```toml
[language-server.dddlint]
command = "dddlint"
args = ["lsp"]
```

## Language support

Extraction is powered by [`tree-sitter-language-pack`](https://github.com/Goldziher/tree-sitter-language-pack), which covers 306 languages including:

Ada · Agda · Arduino · Bash · C · C++ · C# · Clojure · COBOL · Crystal · CSS · D · Dart · Dockerfile · Elixir · Elm · Erlang · F# · Fortran · GDScript · GLSL · Go · GraphQL · Groovy · Hack · Haskell · HCL · HTML · Java · JavaScript · Julia · Kotlin · Lean · Lua · MATLAB · Mojo · Nix · OCaml · Odin · Pascal · Perl · PHP · PowerShell · Prolog · Python · R · Racket · Ruby · Rust · Scala · Scheme · Solidity · SQL · Svelte · Swift · Terraform · TLA+ · TOML · TypeScript · V · VHDL · Vim · Vue · WebAssembly · XML · YAML · Zig, and [243 more](https://github.com/Goldziher/tree-sitter-language-pack).

## CI

```yaml
# .github/workflows/dddlint.yml
- run: uvx dddlint lint
```

Exit code is `0` when clean, `1` when findings exist.

## Pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: dddlint
        name: dddlint
        entry: dddlint lint
        language: python
        pass_filenames: false
```

## Offline use

The language pack downloads parsers on first use. For CI or air-gapped runs, warm the cache in the image:

```sh
python -c "import tree_sitter_language_pack as t; t.download_all()"
```
