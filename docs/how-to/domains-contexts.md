---
icon: lucide/layers
---

# Scope rules to domains and contexts

Real systems are not one flat vocabulary. A term that is canonical in one
bounded context can be an alias in another. dddlint models this with three
layers of scope.

## The three layers

| Layer | Applies to | Precedence |
|---|---|---|
| Global | Every file | Base |
| `domains` | Files matching `include` globs | Adds to global |
| `contexts` | Files matching `include` globs | Adds last, **wins on conflict** |

Domain and context rules are **added** to the global rules for matching files;
they never remove a global rule. When a domain and a context disagree on an
alias mapping, the context wins because it is applied last.

## Scope a rule to a directory

```yaml title="dddlint.yaml"
# applies everywhere
forbidden: [util, helper, manager]

domains:
  - name: commerce
    include: ["**/commerce/**"]
    synonyms:
      - canonical: order
        aliases: [purchase]
```

Now `PurchaseService` under `src/commerce/` is flagged as an alias of `order`,
while the same name elsewhere is left alone.

## Let a context override a domain

```yaml title="dddlint.yaml"
domains:
  - name: commerce
    include: ["**/commerce/**"]
    synonyms:
      - canonical: order
        aliases: [invoice]

contexts:
  - name: billing
    include: ["**/commerce/billing/**"]
    synonyms:
      - canonical: invoice
        aliases: [bill, statement]
```

Under `commerce/`, `invoice` redirects to `order`. But under
`commerce/billing/`, the context makes `invoice` canonical and redirects `bill`
and `statement` to it instead. Context beats domain.

## Verify your scoping in Python

You can assert this behaviour directly against the checker:

```python
from pathlib import Path

from dddlint.check import check
from dddlint.config import Config, Context
from dddlint.extract import Definition

config = Config(
    contexts=[Context(name="billing", include=["**/billing/**"], forbidden=["discount"])]
)


def rules_for(name: str, path: str) -> set[str]:
    defs = [Definition(name, "Class", Path(path), 1)]
    return {f.rule for f in check(defs, config)}


# 'discount' is banned inside the billing context only
assert "forbidden" in rules_for("DiscountPolicy", "src/billing/rules.py")
assert "forbidden" not in rules_for("DiscountPolicy", "src/catalog/rules.py")
```

See the [configuration reference](../reference/config.md) for every key, and
[how checking works](../explanation/how-checking-works.md) for the precedence
model in depth.
