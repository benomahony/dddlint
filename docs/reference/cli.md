---
icon: lucide/terminal
---

# CLI reference

Installed as `dddlint`. Every command auto-detects each file's language and
downloads the tree-sitter grammar on first use, so there is nothing to configure.

```sh
dddlint [OPTIONS] COMMAND [ARGS]
```

## Global options

| Option | Description |
|---|---|
| `-v`, `--version` | Print the version and exit |
| `-h`, `--help` | Show help and exit |

## `lint`

Lint a codebase for ubiquitous-language violations.

```sh
dddlint lint [ROOT] [--config PATH]
```

| Argument / option | Default | Description |
|---|---|---|
| `ROOT` | current directory | Directory to scan recursively |
| `--config PATH` | `ROOT/dddlint.yaml` | Config file to load |

Config resolution: if `--config` is omitted, dddlint looks for `dddlint.yaml`
in `ROOT`, then falls back to the current working directory.

Directories skipped while scanning: `.git`, `.venv`, `node_modules`,
`__pycache__`, `target`, `dist`, `build`.

The config file itself is validated on every run (see the
[config rules](rules.md#config-rules)).

**Exit code**

| Code | Meaning |
|---|---|
| `0` | No findings |
| `1` | One or more findings (printed to stdout) |

## `html`

Open an interactive language graph in the browser.

```sh
dddlint html [ROOT] [--config PATH]
```

Renders the configured vocabulary (canonical terms, aliases, domains, and
contexts) to a temporary HTML file and opens it in your default browser. Takes
the same `ROOT` and `--config` arguments as `lint`.

## `lsp`

Start the Language Server over stdio.

```sh
dddlint lsp [ROOT]
```

Publishes diagnostics on file open and save, scanning the whole workspace each
time, and offers rename code actions for aliases. Wire it into an editor with
the [editor guide](../how-to/editor-lsp.md). Also available as the
`dddlint-lsp` entry point.
