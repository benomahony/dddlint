---
icon: lucide/git-branch
---

# Run dddlint in CI

Fail the build when the codebase drifts from its agreed vocabulary.

## GitHub Actions

Add a step that runs the linter with `uvx` — no install or lockfile needed.

```yaml title=".github/workflows/dddlint.yml"
name: dddlint
on: [push, pull_request]
jobs:
  language:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uvx dddlint lint
```

`dddlint lint` exits `1` when it finds anything, which fails the job.

## Any other CI

The contract is just the exit code, so any runner works:

```sh
uvx dddlint lint
```

| Exit code | Meaning |
|---|---|
| `0` | No findings — the build passes |
| `1` | Findings printed to stdout — the build fails |

## Lint only part of the repo

Pass a path to scope the scan while a monorepo migrates:

```sh
uvx dddlint lint services/billing
```

The config is looked up in that directory first, then the current working
directory. See [`dddlint lint`](../reference/cli.md#lint) for details.

## Warm the parser cache for air-gapped runners

The language pack downloads parsers on first use. Bake them into the image so
CI never reaches for the network:

```sh
python -c "import tree_sitter_language_pack as t; t.download_all()"
```
