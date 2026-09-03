import re
from collections import defaultdict
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from .config import Config, Context, SynonymGroup
from .extract import PATH_KINDS, Definition

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


def owning_scope(config: Config, path: Path) -> str | None:
    assert isinstance(path, Path), "path must be a Path, not a str"
    assert config.similarity_threshold >= 0.0, "config must be a loaded Config"
    owners = [scope.name for scope in config.domains + config.contexts if _scoped(scope, path)]
    return owners[-1] if owners else None


def scope_of(config: Config, path: Path) -> str:
    assert isinstance(path, Path), "path must be a Path, not a str"
    assert config.similarity_threshold >= 0.0, "config must be a loaded Config"
    return owning_scope(config, path) or "global"


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
    named = definition.kind in PATH_KINDS
    tag = ":module" if named else ""
    out: list[Finding] = []
    for token in tokenise(definition.name):
        if token in forbidden:
            out.append(
                Finding(
                    definition.path,
                    definition.line,
                    definition.name,
                    f"forbidden{tag}",
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
                    f"alias{tag}",
                    f"'{token}' is not the canonical term, use '{canonical}'",
                    col=definition.col,
                    fix=None if named else _apply_fix(definition.name, token, canonical),
                )
            )
    return out


def _is_dunder(name: str) -> bool:
    assert name, "name must be non-empty to classify"
    assert isinstance(name, str), "name must be a string"
    return name.startswith("__") and name.endswith("__")


def _case_only_across_kinds(names: set[str], kinds: set[str]) -> bool:
    """Language convention, not drift: CapWords classes beside snake_case functions."""
    assert names, "names must be non-empty to compare"
    assert kinds, "every collision must carry at least one kind"
    return len(kinds) > 1 and len({n.lower() for n in names}) == 1


def _sides(name: str, markers: frozenset[str]) -> tuple[tuple[str, ...], ...]:
    assert name, "name must be non-empty to split"
    assert markers, "need markers to split around"
    out: list[list[str]] = [[]]
    for token in tokenise(name):
        if token in markers:
            out.append([])
        else:
            out[-1].append(token)
    return tuple(tuple(side) for side in out)


def _directional(names: set[str], markers: frozenset[str]) -> bool:
    """Order is the meaning: us_to_uk and uk_to_us are opposite directions, not drift."""
    assert names, "names must be non-empty to compare"
    assert isinstance(markers, frozenset), "markers must be a frozenset of tokens"
    if not markers:
        return False
    sided = {_sides(name.lower(), markers) for name in names}
    return len(sided) == len(names) and all(len(side) > 1 for side in sided)


def _duplicates(definitions: list[Definition], config: Config) -> list[Finding]:
    assert all(d.name for d in definitions), "every definition must have a name"
    assert config.name_uniqueness, "only call this when uniqueness is enforced"
    owned: dict[tuple[str, str], list[Definition]] = defaultdict(list)
    for definition in definitions:
        if _is_dunder(definition.name) or definition.kind in PATH_KINDS:
            continue
        owned[(scope_of(config, definition.path), definition.name)].append(definition)
    out: list[Finding] = []
    for (scope, name), sharers in sorted(owned.items()):
        if len(sharers) < 2:
            continue
        for definition in sharers:
            others = ", ".join(
                f"{o.kind} at {o.path}:{o.line + 1}" for o in sharers if o is not definition
            )
            out.append(
                Finding(
                    definition.path,
                    definition.line,
                    name,
                    "duplicate",
                    f"'{name}' is not unique in {scope}: also {others}",
                    col=definition.col,
                )
            )
    return out


_TEST_TOKENS = frozenset({"test", "tests"})
_SUBJECT_KINDS = frozenset({"Function", "Class"})


def is_test_name(name: str) -> bool:
    assert name, "name must be non-empty to classify"
    tokens = tokenise(name)
    return bool(tokens) and (tokens[0] in _TEST_TOKENS or tokens[-1] in _TEST_TOKENS)


def is_test_path(path: Path) -> bool:
    assert isinstance(path, Path), "path must be a Path, not a str"
    if {part.lower() for part in path.parts} & _TEST_TOKENS:
        return True
    stem = path.stem.lower()
    return stem.startswith("test_") or stem.endswith("_test") or stem == "conftest"


def is_test_definition(definition: Definition) -> bool:
    assert definition.name, "definition must have a name to classify"
    return is_test_name(definition.name) or is_test_path(definition.path)


def _test_subject(definition: Definition) -> tuple[str, ...] | None:
    """The concept a test covers: its name with the test word stripped, as sorted tokens."""
    if definition.kind not in _SUBJECT_KINDS or not is_test_name(definition.name):
        return None
    tokens = tokenise(definition.name)
    subject = tokens[1:] if tokens[0] in _TEST_TOKENS else tokens[:-1]
    return tuple(sorted(subject)) or None


def _implementation_scopes(definitions: list[Definition], config: Config) -> dict[tuple, set[str]]:
    assert all(d.name for d in definitions), "every definition must have a name"
    out: dict[tuple, set[str]] = defaultdict(set)
    for definition in definitions:
        if definition.kind in PATH_KINDS or is_test_definition(definition):
            continue
        out[tuple(sorted(tokenise(definition.name)))].add(scope_of(config, definition.path))
    return out


def _test_domain_drift(definitions: list[Definition], config: Config) -> list[Finding]:
    """A test sitting in one declared domain while the code it names lives in another."""
    assert all(d.name for d in definitions), "every definition must have a name"
    implementations = _implementation_scopes(definitions, config)
    out: list[Finding] = []
    for definition in definitions:
        subject = _test_subject(definition)
        if subject is None:
            continue
        home = scope_of(config, definition.path)
        if home == "global":
            continue
        owners = {scope for scope in implementations.get(subject, set()) if scope != "global"}
        if len(owners) != 1:
            continue
        (owner,) = owners
        if owner == home:
            continue
        spelled = " ".join(subject)
        out.append(
            Finding(
                definition.path,
                definition.line,
                definition.name,
                "test-domain-drift",
                f"tests '{spelled}', which belongs to {owner}, but lives in {home}",
                col=definition.col,
            )
        )
    return out


def check(definitions: list[Definition], config: Config) -> list[Finding]:
    assert all(d.line >= 0 for d in definitions), "definition lines must be non-negative"
    assert all(d.name for d in definitions), "every definition must have a name"
    exempt = set(config.exempt)
    definitions = [definition for definition in definitions if definition.name not in exempt]
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
    kinds: dict[tuple[str, ...], set[str]] = defaultdict(set)
    first: dict[tuple[str, ...], Definition] = {}
    for definition in definitions:
        if _is_dunder(definition.name) or definition.kind in PATH_KINDS:
            continue
        key = tuple(sorted(tokenise(definition.name)))
        by_tokens[key].add(definition.name)
        kinds[key].add(definition.kind)
        first.setdefault(key, definition)
    if config.name_uniqueness:
        out.extend(_duplicates(definitions, config))
    out.extend(_test_domain_drift(definitions, config))

    markers = frozenset(marker.lower() for marker in config.directional)
    for key, names in by_tokens.items():
        if len(names) < 2 or _case_only_across_kinds(names, kinds[key]):
            continue
        if _directional(names, markers):
            continue
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
