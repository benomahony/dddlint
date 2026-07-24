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

language = language_for(source, {})
defs = definitions(source, language)

config = Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])
findings = check(defs, config)

assert language == "python"
assert defs[0].name == "ClientRepository"
assert findings[0].rule == "alias"
```

## `dddlint.extract`

### `language_for(path, extra)`

Return the tree-sitter language name for `path`, or `None` if it cannot be
detected. `extra` is a `dict[str, str]` mapping a file suffix to a language
name — pass `{}` to rely purely on auto-detection.

```python
from pathlib import Path

from dddlint.extract import language_for

assert language_for(Path("main.rs"), {}) == "rust"
assert language_for(Path("data.unknownext"), {}) is None
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
| `kind` | str | `"Class"`, `"Function"`, `"Method"`, … |
| `path` | Path | File the definition came from |
| `line` | int | 0-based line of the definition |
| `col` | int | 0-based column of the name (default `0`) |
| `doc` | str \| None | Doc comment, if any (default `None`) |
