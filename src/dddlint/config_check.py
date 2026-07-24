from difflib import SequenceMatcher
from pathlib import Path

from .check import Finding
from .config import Config, Context, SynonymGroup


def _alias_map(synonyms: list[SynonymGroup]) -> dict[str, str]:
    assert synonyms is not None, "synonyms must not be None"
    assert isinstance(synonyms, list), "synonyms must be a list"
    return {alias.lower(): g.canonical.lower() for g in synonyms for alias in g.aliases}


def _forbidden_canonical_clashes(config: Config, path: Path) -> list[Finding]:
    assert config is not None, "config must not be None"
    assert isinstance(path, Path), "path must be a Path object"
    forbidden = {t.lower() for t in config.forbidden}
    canonicals = {g.canonical.lower() for g in config.synonyms}
    return [
        Finding(
            path,
            0,
            term,
            "config:forbidden-canonical-clash",
            f"'{term}' is both forbidden and a canonical synonym",
        )
        for term in forbidden & canonicals
    ]


def _alias_conflicts(config: Config, path: Path) -> list[Finding]:
    assert config is not None, "config must not be None"
    assert isinstance(path, Path), "path must be a Path object"
    scopes: list[tuple[str, list[SynonymGroup]]] = [("global", config.synonyms)]
    for s in config.domains:
        scopes.append((f"domain:{s.name}", s.synonyms))
    for s in config.contexts:
        scopes.append((f"context:{s.name}", s.synonyms))

    out: list[Finding] = []
    seen: dict[str, tuple[str, str]] = {}
    for scope_name, synonyms in scopes:
        for alias, canonical in _alias_map(synonyms).items():
            if alias in seen and seen[alias][1] != canonical:
                prev_scope, prev_canonical = seen[alias]
                out.append(
                    Finding(
                        path,
                        0,
                        alias,
                        "config:alias-conflict",
                        f"'{alias}' → '{canonical}' in {scope_name} "
                        f"but → '{prev_canonical}' in {prev_scope}",
                    )
                )
            else:
                seen[alias] = (scope_name, canonical)
    return out


def _duplicate_names(config: Config, path: Path) -> list[Finding]:
    assert config is not None, "config must not be None"
    assert isinstance(path, Path), "path must be a Path object"
    out: list[Finding] = []
    all_scopes: list[Context] = config.domains + config.contexts
    for i, a in enumerate(all_scopes):
        for b in all_scopes[i + 1 :]:
            similarity = SequenceMatcher(None, a.name.lower(), b.name.lower()).ratio()
            if similarity >= config.similarity_threshold:
                out.append(
                    Finding(
                        path,
                        0,
                        a.name,
                        "config:duplicate-name",
                        f"'{a.name}' and '{b.name}' look like the same domain/context",
                    )
                )
    return out


def check_config(config: Config, path: Path) -> list[Finding]:
    assert config is not None, "config must not be None"
    assert isinstance(path, Path), "path must be a Path object"
    return (
        _forbidden_canonical_clashes(config, path)
        + _alias_conflicts(config, path)
        + _duplicate_names(config, path)
    )
