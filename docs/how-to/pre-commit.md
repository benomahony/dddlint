---
icon: lucide/git-commit-horizontal
---

# Run dddlint as a pre-commit hook

Catch vocabulary drift before it ever reaches a commit.

## Add the hook

dddlint runs as a `local` hook so it uses the version already on the project's
path:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: local
    hooks:
      - id: dddlint
        name: dddlint
        entry: dddlint lint
        language: python
        pass_filenames: false
```

`pass_filenames: false` matters: dddlint scans the whole tree every run so it
can catch [drift](../reference/rules.md#drift) across files, not just the ones
in the current commit.

## Install and run

```sh
pre-commit install
pre-commit run dddlint --all-files
```

From now on the hook runs on every `git commit`. A finding blocks the commit
with a non-zero exit code.

## Use uvx instead of a project install

If dddlint is not a project dependency, invoke it through `uvx`:

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: local
    hooks:
      - id: dddlint
        name: dddlint
        entry: uvx dddlint lint
        language: system
        pass_filenames: false
```
