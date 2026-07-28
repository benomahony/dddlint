---
icon: lucide/settings
---

# Configuration reference

dddlint reads `dddlint.yaml` from the project root. Every key is optional; an
empty file is valid and produces no findings.

## Top-level keys

| Key | Type | Default | Description |
|---|---|---|---|
| `similarity_threshold` | float | `0.85` | Ratio above which two domain/context names are flagged as duplicates |
| `enforce_canonical` | bool | `true` | Flag alias terms in addition to forbidden ones |
| `forbidden` | list[str] | `[]` | Terms that must never appear in a definition name |
| `exclude` | list[str] | `[]` | Paths to skip, see [exclude patterns](#exclude-patterns) |
| `synonyms` | list[[SynonymGroup](#synonymgroup)] | `[]` | Canonical terms and their aliases |
| `domains` | list[[Scope](#scope)] | `[]` | Path-scoped rules for high-level business domains |
| `contexts` | list[[Scope](#scope)] | `[]` | Path-scoped rules applied after domains, win on conflict |
| `embeddings` | [Embeddings](#embeddings) | see below | Model and thresholds for `dddlint map` |

## Exclude patterns

`exclude` takes gitignore syntax, matched against each file's path **relative to
the directory holding the config file**, not relative to the directory you point
the CLI at. So the same patterns hold whether you run `dddlint lint` or
`dddlint lint src/billing`.

```yaml title="dddlint.yaml"
exclude:
  - src/generated
  - "**/*_pb2.py"
  - migrations/
```

A `.gitignore` beside the config file is honoured on top of these, as are the
always-skipped directories listed in the [CLI reference](cli.md#lint).

## SynonymGroup

| Key | Type | Default | Description |
|---|---|---|---|
| `canonical` | str | required | The one true term |
| `aliases` | list[str] | `[]` | Terms that should be renamed to `canonical` |

## Scope

`domains` and `contexts` share the same shape. Both add their rules to the
global rules for any file whose path matches an `include` glob.

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | str | required | Identifier for the scope, shown in config-rule messages |
| `include` | list[str] | required | `fnmatch` globs matched against each file path |
| `forbidden` | list[str] | `[]` | Banned terms within this scope |
| `synonyms` | list[[SynonymGroup](#synonymgroup)] | `[]` | Scope-specific canonical terms |

Precedence: global → domains → contexts. Contexts are applied last, so a
context can override a domain's alias mapping. See
[how checking works](../explanation/how-checking-works.md).

## Embeddings

Read only by [`dddlint map`](cli.md#map). `lint` and `lsp` never embed anything.

| Key | Type | Default | Description |
|---|---|---|---|
| `model` | str | `sentence-transformers:all-MiniLM-L6-v2` | pydantic-ai embedding model, `provider:name` |
| `dimensions` | int \| None | `None` | Truncate vectors to this width, `None` keeps the model's native size |
| `batch_size` | int | `128` | Names embedded per request |
| `cache` | Path | `.dddlint/embeddings.json` | Vector cache, relative paths resolve against `ROOT` |
| `threshold` | float \| None | `None` | Cosine similarity above which names cluster, falls back to `similarity_threshold` |
| `outlier_margin` | float | `0.05` | How much closer a name must sit to another scope before it is called an outlier |

The cache is keyed by model and dimensions, so changing either invalidates it
rather than mixing vector spaces. Unchanged names are never re-embedded.

```yaml title="dddlint.yaml"
embeddings:
  model: openai:text-embedding-3-small
  dimensions: 512
  threshold: 0.78
```

## Full example

```yaml title="dddlint.yaml"
similarity_threshold: 0.85
enforce_canonical: true

forbidden:
  - util
  - helper
  - manager

synonyms:
  - canonical: customer
    aliases: [client, user, accountholder]
  - canonical: order
    aliases: [purchase, transaction]

domains:
  - name: commerce
    include: ["**/commerce/**"]
    synonyms:
      - canonical: order
        aliases: [purchase]

contexts:
  - name: billing
    include: ["**/billing/**"]
    forbidden: [discount]
    synonyms:
      - canonical: invoice
        aliases: [bill, statement]
```

## Loading config in Python

```python
from pathlib import Path
from tempfile import mkdtemp

from dddlint.config import load_config

path = Path(mkdtemp()) / "dddlint.yaml"
path.write_text("forbidden: [manager]\n")

config = load_config(path)

assert config.forbidden == ["manager"]
assert config.enforce_canonical is True
assert config.similarity_threshold == 0.85
```
