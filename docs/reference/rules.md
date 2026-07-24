---
icon: lucide/list-checks
---

# Rules reference

dddlint emits two families of findings: **code rules** against your source, and
**config rules** against `dddlint.yaml` itself. Every finding has a `rule`
name, a severity, and a message.

## Code rules

Checked against the definition names (classes, functions, methods, structs,
interfaces, enums, traits, variables, constants) extracted from your source.

### forbidden

**Severity: error.** A definition name contains a banned term from `forbidden`.

Names are tokenised on case and separator boundaries before matching, so
`OrderManager` contains the token `manager`.

```python
from pathlib import Path

from dddlint.check import check
from dddlint.config import Config
from dddlint.extract import Definition

config = Config(forbidden=["manager"])
defs = [Definition("OrderManager", "Class", Path("orders.py"), 1)]

findings = check(defs, config)

assert findings[0].rule == "forbidden"
assert "manager" in findings[0].message
```

### alias

**Severity: warning.** A definition uses a non-canonical synonym. The finding
carries a `fix` — the name rewritten to the canonical term with case preserved.
Emitted only when `enforce_canonical` is `true`.

```python
from pathlib import Path

from dddlint.check import check
from dddlint.config import Config, SynonymGroup
from dddlint.extract import Definition

config = Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])])
defs = [Definition("ClientRepository", "Class", Path("repo.py"), 1)]

alias = next(f for f in check(defs, config) if f.rule == "alias")

assert alias.fix == "CustomerRepository"
assert "customer" in alias.message
```

### drift

**Severity: info.** The same concept is spelled several different ways across
the codebase. Two names drift together when they tokenise to the same set of
tokens, regardless of order or casing.

```python
from pathlib import Path

from dddlint.check import check
from dddlint.config import Config
from dddlint.extract import Definition

defs = [
    Definition("get_user_by_id", "Function", Path("a.py"), 1),
    Definition("getUserById", "Function", Path("b.py"), 1),
]

rules = {f.rule for f in check(defs, Config())}

assert "drift" in rules
```
