---
icon: lucide/graduation-cap
---

# Your first lint

In this tutorial you will lint a tiny project, watch dddlint catch a naming
drift, and fix it. It takes about five minutes. You need only `uv` installed.

## 1. Make a project

Create an empty directory and drop in two files that disagree about what to
call a customer.

```sh
mkdir language-demo && cd language-demo
```

```python title="repo.py"
class ClientRepository:
    def get_client(self, client_id: str) -> dict:
        return {}
```

```python title="service.py"
class CustomerService:
    def load_customer(self, customer_id: str) -> dict:
        return {}
```

One file says `client`, the other says `customer`. That is exactly the kind of
split dddlint exists to surface.

## 2. Write the vocabulary

Tell dddlint that `customer` is the canonical term and `client` is an alias.

```yaml title="dddlint.yaml"
synonyms:
  - canonical: customer
    aliases: [client]
```

## 3. Run the linter

```sh
uvx dddlint lint
```

You will see two findings:

```text
repo.py
────────────────────────────────────
   1  alias       ClientRepository  'client' is not the canonical term, use 'customer'
   2  alias       get_client        'client' is not the canonical term, use 'customer'

✖ 2 findings
```

dddlint exited with code `1`. That non-zero exit is what makes it useful in CI
and commit hooks: the build fails until the language is consistent.

## 4. Fix the drift

Rename the identifiers in `repo.py` to use `customer`:

```python title="repo.py"
class CustomerRepository:
    def get_customer(self, customer_id: str) -> dict:
        return {}
```

Run the linter again:

```sh
uvx dddlint lint
```

```text
✔ no findings
```

Exit code `0`. The whole codebase now speaks one language.

## What you learned

- A `dddlint.yaml` at the project root defines the vocabulary.
- `dddlint lint` scans every file tree-sitter recognises and reports findings.
- The exit code is `0` when clean and `1` when there are findings.

## Next steps

- Make it automatic: [run dddlint in CI](../how-to/ci.md) or as a
  [pre-commit hook](../how-to/pre-commit.md).
- Get findings inline while you type: [editor diagnostics](../how-to/editor-lsp.md).
- Learn the full vocabulary syntax in the [configuration reference](../reference/config.md).
