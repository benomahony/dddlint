import re
from collections import defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from .config import Config, Context, SynonymGroup
from .extract import Definition

_BOUNDARY = re.compile(
    r"[-_\s]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)


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
    def _recase(m: re.Match) -> str:
        s = m.group()
        if s.isupper():
            return new_token.upper()
        if s[0].isupper():
            return new_token.capitalize()
        return new_token
    return re.sub(re.escape(old_token), _recase, name, flags=re.IGNORECASE)


def tokenise(name: str) -> tuple[str, ...]:
    return tuple(p.lower() for p in _BOUNDARY.split(name) if p)


def _scoped(context: Context, path: Path) -> bool:
    return any(fnmatch(str(path), pattern) for pattern in context.include)


def _alias_map(groups: list[SynonymGroup]) -> dict[str, str]:
    out: dict[str, str] = {}
    for group in groups:
        for alias in group.aliases:
            out[alias.lower()] = group.canonical
    return out


def _check_one(
    definition: Definition,
    forbidden: set[str],
    aliases: dict[str, str],
    enforce_canonical: bool,
) -> list[Finding]:
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
        out.extend(
            _check_one(definition, forbidden, aliases, config.enforce_canonical)
        )

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
