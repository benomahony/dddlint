---
icon: lucide/code
---

# Python API reference

dddlint is a library as well as a CLI. The pipeline is three steps you can call
directly: **extract** definitions from source, **check** them against a config,
and read back **findings**.

## Pipeline at a glance

```python
from pathlib import Path
from tempfile import mkdtemp

from dddlint.check import check
from dddlint.config import Config, SynonymGroup
from dddlint.extract import definitions, language_for

source = Path(mkdtemp()) / "repo.py"
source.write_text("class ClientRepository:\n    pass\n")

language = language_for(source)
defs = definitions(source, language)

config = Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])
findings = check(defs, config)

assert language == "python"
assert defs[0].name == "ClientRepository"
assert findings[0].rule == "alias"
```

## `dddlint.extract`

### `language_for(path)`

Return the tree-sitter language name auto-detected from `path`, or `None` if it
cannot be detected.

```python
from pathlib import Path

from dddlint.extract import language_for

assert language_for(Path("main.rs")) == "rust"
assert language_for(Path("data.unknownext")) is None
```

### `definitions(path, language)`

Parse `path` with the given `language` and return a list of `Definition`. Reads
classes, functions, methods, structs, interfaces, enums, traits, variables, and
constants.

### `Definition`

Frozen dataclass describing one extracted name.

| Field | Type | Description |
|---|---|---|
| `name` | str | The identifier as written in source |
| `kind` | str | `"Class"`, `"Function"`, `"Method"`, ... |
| `path` | Path | File the definition came from |
| `line` | int | 0-based line of the definition |
| `col` | int | 0-based column of the name (default `0`) |
| `doc` | str \| None | Doc comment, if any (default `None`) |

## `dddlint.check`

### `check(definitions, config)`

Run every code rule over `definitions` and return a flat list of `Finding`.

### `tokenise(name)`

Split an identifier into lowercase tokens on case and separator boundaries.
This is the unit both rule matching and drift detection work on.

```python
from dddlint.check import tokenise

assert tokenise("getUserById") == ("get", "user", "by", "id")
assert tokenise("get_user_by_id") == ("get", "user", "by", "id")
assert tokenise("HTTPServer") == ("http", "server")
```

### `Finding`

Frozen dataclass describing one violation.

| Field | Type | Description |
|---|---|---|
| `path` | Path | File the finding is in |
| `line` | int | Line of the offending definition |
| `name` | str | The definition name |
| `rule` | str | Rule name, see the [rules reference](rules.md) |
| `message` | str | Human-readable explanation |
| `col` | int | Column of the name (default `0`) |
| `fix` | str \| None | Suggested rename, for `alias` findings (default `None`) |

## `dddlint.config`

### `load_config(path)`

Read and validate a `dddlint.yaml` into a `Config`. See the
[configuration reference](config.md) for the schema and the `Config`,
`SynonymGroup`, and `Context` models.

## `dddlint.config_check`

### `check_config(config, path)`

Validate a `Config` for internal contradictions and return a list of `Finding`
with `config:` rule names. Run automatically by `dddlint lint`.

## `dddlint.discover`

### `source_files(root, exclude, base=None)`

Yield every file under `root`, skipping the built-in directories, the `exclude`
gitwildmatch patterns, and any `.gitignore`. Patterns are matched against paths
relative to `base`, defaulting to `root`. Pass the config file's directory as
`base` so patterns keep working when `root` is a subdirectory.

```python
from pathlib import Path
from tempfile import mkdtemp

from dddlint.discover import source_files

root = Path(mkdtemp())
(root / "src").mkdir()
(root / "src" / "keep.py").write_text("x = 1\n")
(root / "src" / "gen.py").write_text("y = 2\n")

found = {p.name for p in source_files(root / "src", ["src/gen.py"], root)}

assert found == {"keep.py"}
```

## `dddlint.embed`

### `await embed_names(names, config, model=None)`

Embed `names` with the pydantic-ai model from an `Embeddings` config and return
`{name: vector}`. Only names missing from `config.cache` are sent, in batches of
`config.batch_size`; the cache is keyed by model and dimensions. Pass `model` to
inject an `EmbeddingModel` directly instead of resolving `config.model`.

## `dddlint.cluster`

Vector helpers over plain `list[float]`, backed by numpy.

| Function | Returns | Description |
|---|---|---|
| `similarities(vectors)` | ndarray | Square cosine similarity matrix |
| `clusters(vectors, threshold)` | list[list[int]] | Single-link groups of indices joined above `threshold` |
| `centroid(vectors)` | list[float] | Unit-normalised mean vector |
| `nearest(vector, centroids)` | tuple[str, float] | Best-matching label and its score |
| `project(vectors)` | list[tuple[float, float]] | PCA projection to 2-D |

## `dddlint.insights`

Meaning-level analysis for `dddlint map`. Each takes the definitions, a
`{name: vector}` mapping, and a `Config`.

| Function | Returns | Description |
|---|---|---|
| `near_synonyms(definitions, vectors, config)` | list[`Insight`] | Clusters sharing meaning but no token |
| `context_outliers(definitions, vectors, config)` | list[`Insight`] | Names closer to another scope's centroid |
| `map_points(definitions, vectors, config)` | list[`Point`] | 2-D layout with role, scope, and cluster |
| `threshold_for(config)` | float | `embeddings.threshold`, falling back to `similarity_threshold` |

### `Insight`

Frozen dataclass describing one observation.

| Field | Type | Description |
|---|---|---|
| `rule` | str | `"near-synonym"` or `"context-outlier"` |
| `message` | str | Human-readable explanation |
| `names` | tuple[str, ...] | The names involved |
| `score` | float | Strength, see the [rules reference](rules.md#insights) |
| `path` | Path \| None | File of the first name (default `None`) |
| `line` | int | Line of the first name (default `0`) |

### `Point`

Frozen dataclass placing one name on the map: `name`, `x`, `y`, `role`
(`"verb"` for functions and methods, else `"noun"`), `scope`, and `cluster`.
