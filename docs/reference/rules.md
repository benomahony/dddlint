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
carries a `fix`, the name rewritten to the canonical term with case preserved.
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

### duplicate

**Severity: warning.** One name is claimed by more than one definition inside
the same context: two concepts wearing one word. Every sharer is reported, each
message naming the others. Set `name_uniqueness: false` to allow it, for
instance where a variable and a method deliberately share a name.

Matching is on the exact name, and only within one context, since two bounded
contexts owning the same word is what a bounded context is for. Dunder names are
exempt. Collisions are scoped by [`domains` and `contexts`](config.md#scope), so
an unscoped project treats the whole codebase as one context.

```python
from pathlib import Path

from dddlint.check import check
from dddlint.config import Config
from dddlint.extract import Definition

defs = [
    Definition("balance", "Method", Path("account.py"), 3),
    Definition("balance", "Variable", Path("ledger.py"), 9),
]

findings = [f for f in check(defs, Config()) if f.rule == "duplicate"]

assert len(findings) == 2
assert "Variable at ledger.py:10" in findings[0].message
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

Language conventions are not drift, so two cases are exempt:

- **Dunder names.** `__init__` is a protocol slot, not a naming choice, so it
  never drifts against an `init` function.
- **Case-only collisions across kinds.** An `Entity` class beside an `entity()`
  method is PEP 8, not duplication.

Visibility-only pairs still report: `_validate` against `validate` in another
module is genuine duplication.

## Insights

Emitted by [`dddlint map`](cli.md#map) rather than `lint`, from embeddings of
the definition names. Insights carry a `score` instead of a severity and never
affect the exit code, because meaning is a judgement call and not a gate.

| Rule | Score | Description |
|---|---|---|
| `near-synonym` | weakest cosine similarity in the cluster | Names that mean the same thing while sharing no token |
| `context-outlier` | how much closer the other scope sits | A name whose vocabulary belongs to a different domain or context |

`near-synonym` is the counterpart to `drift`: drift catches one concept spelled
several ways, this catches one concept **worded** several ways. Names sharing
any token are skipped, since `drift` already covers those.

```python
from pathlib import Path

from dddlint.config import Config
from dddlint.extract import Definition
from dddlint.insights import near_synonyms

defs = [
    Definition("fetch_order", "Function", Path("a.py"), 1),
    Definition("retrieve_purchase", "Function", Path("b.py"), 1),
]
vectors = {"fetch_order": [0.0, 1.0], "retrieve_purchase": [0.05, 0.99]}

insight = near_synonyms(defs, vectors, Config())[0]

assert insight.rule == "near-synonym"
assert insight.names == ("fetch_order", "retrieve_purchase")
```

## Config rules

Checked against `dddlint.yaml` on every run so a broken vocabulary is caught
before it hides real findings.

| Rule | Severity | Description |
|---|---|---|
| `config:forbidden-canonical-clash` | error | A term is both `forbidden` and a canonical synonym |
| `config:alias-conflict` | warning | The same alias maps to different canonicals in different scopes |
| `config:duplicate-name` | info | Two domains or contexts have names more similar than `similarity_threshold` |

```python
from pathlib import Path

from dddlint.config import Config, SynonymGroup
from dddlint.config_check import check_config

config = Config(
    forbidden=["order"],
    synonyms=[SynonymGroup(canonical="order", aliases=["purchase"])],
)

findings = check_config(config, Path("dddlint.yaml"))
rules = {f.rule for f in findings}

assert "config:forbidden-canonical-clash" in rules
```
