import re
from collections import defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from .config import Config, Context, SynonymGroup
from .extract import Definition

_BOUNDARY = r"[-_\s]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line: int
    name: str
    rule: str
    message: str
    col: int = 0
    fix: str | None = None


def _apply_fix(name: str, old_token: str, new_token: str) -> str:
    assert old_token, "old_token must be non-empty; an empty pattern matches everywhere"
    assert name, "name must be non-empty to rewrite"

    def _recase(m: re.Match) -> str:
        s = m.group()
        assert s, "matched token must be non-empty"
        assert new_token, "canonical replacement must be non-empty"
        if s.isupper():
            return new_token.upper()
        if s[0].isupper():
            return new_token.capitalize()
        return new_token

    return re.sub(re.escape(old_token), _recase, name, flags=re.IGNORECASE)


def tokenise(name: str) -> tuple[str, ...]:
    tokens = tuple(p.lower() for p in re.split(_BOUNDARY, name) if p)
    assert all(t == t.lower() for t in tokens), "every token must be lowercased"
    assert all(tokens), "tokens must be non-empty"
    return tokens


def _scoped(context: Context, path: Path) -> bool:
    assert isinstance(path, Path), "path must be a Path, not a str"
    assert isinstance(context.include, list), "context include must be a list of patterns"
    return any(fnmatch(str(path), pattern) for pattern in context.include)


def _alias_map(groups: list[SynonymGroup]) -> dict[str, str]:
    out: dict[str, str] = {}
    for group in groups:
        for alias in group.aliases:
            out[alias.lower()] = group.canonical
    assert all(k == k.lower() for k in out), "alias keys must be lowercased for matching"
    assert all(out.values()), "every alias must map to a non-empty canonical"
    return out


def _check_one(
    definition: Definition,
    forbidden: set[str],
    aliases: dict[str, str],
    enforce_canonical: bool,
) -> list[Finding]:
    assert isinstance(forbidden, set), "forbidden must be a set for O(1) membership"
    assert definition.name, "definition must have a non-empty name to tokenise"
    out: list[Finding] = []
    for token in tokenise(definition.name):
        if token in forbidden:
            out.append(
                Finding(
                    definition.path,
                    definition.line,
                    definition.name,
                    "forbidden",
                    f"uses banned term '{token}'",
                    col=definition.col,
                )
            )
        if enforce_canonical and token in aliases:
            canonical = aliases[token]
            out.append(
                Finding(
                    definition.path,
                    definition.line,
                    definition.name,
                    "alias",
                    f"'{token}' is not the canonical term, use '{canonical}'",
                    col=definition.col,
                    fix=_apply_fix(definition.name, token, canonical),
                )
            )
    return out


def check(definitions: list[Definition], config: Config) -> list[Finding]:
    assert all(d.line >= 0 for d in definitions), "definition lines must be non-negative"
    assert all(d.name for d in definitions), "every definition must have a name"
    out: list[Finding] = []
    base_forbidden = {t.lower() for t in config.forbidden}
    base_aliases = _alias_map(config.synonyms)

    for definition in definitions:
        forbidden = set(base_forbidden)
        aliases = dict(base_aliases)
        for scope in config.domains + config.contexts:
            if _scoped(scope, definition.path):
                forbidden |= {t.lower() for t in scope.forbidden}
                aliases |= _alias_map(scope.synonyms)
        out.extend(_check_one(definition, forbidden, aliases, config.enforce_canonical))

    by_tokens: dict[tuple[str, ...], set[str]] = defaultdict(set)
    first: dict[tuple[str, ...], Definition] = {}
    for definition in definitions:
        key = tuple(sorted(tokenise(definition.name)))
        by_tokens[key].add(definition.name)
        first.setdefault(key, definition)
    for key, names in by_tokens.items():
        if len(names) > 1:
            definition = first[key]
            spellings = ", ".join(sorted(names))
            out.append(
                Finding(
                    definition.path,
                    definition.line,
                    definition.name,
                    "drift",
                    f"one concept spelled several ways: {spellings}",
                )
            )
    return out
