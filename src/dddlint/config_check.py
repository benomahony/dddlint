from difflib import SequenceMatcher
from pathlib import Path

from .check import Finding
from .config import Config, Context, SynonymGroup


def _lowered_alias_map(synonyms: list[SynonymGroup]) -> dict[str, str]:
    result = {alias.lower(): g.canonical.lower() for g in synonyms for alias in g.aliases}
    assert all(k == k.lower() for k in result), "alias keys must be lowercased"
    assert all(v == v.lower() for v in result.values()), "canonicals must be lowercased"
    return result


def _forbidden_canonical_clashes(config: Config, path: Path) -> list[Finding]:
    forbidden = {t.lower() for t in config.forbidden}
    canonicals = {g.canonical.lower() for g in config.synonyms}
    out = [
        Finding(
            path,
            0,
            term,
            "config:forbidden-canonical-clash",
            f"'{term}' is both forbidden and a canonical synonym",
        )
        for term in forbidden & canonicals
    ]
    assert all(f.line == 0 for f in out), "config findings must anchor to line 0"
    assert all(f.rule == "config:forbidden-canonical-clash" for f in out), "wrong rule tag"
    return out


def _alias_conflicts(config: Config, path: Path) -> list[Finding]:
    scopes: list[tuple[str, list[SynonymGroup]]] = [("global", config.synonyms)]
    for s in config.domains:
        scopes.append((f"domain:{s.name}", s.synonyms))
    for s in config.contexts:
        scopes.append((f"context:{s.name}", s.synonyms))

    out: list[Finding] = []
    seen: dict[str, tuple[str, str]] = {}
    for scope_name, synonyms in scopes:
        for alias, canonical in _lowered_alias_map(synonyms).items():
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
    assert all(f.rule == "config:alias-conflict" for f in out), "wrong rule tag"
    assert all(f.path == path for f in out), "findings must reference the config path"
    return out


def _duplicate_names(config: Config, path: Path) -> list[Finding]:
    assert config.similarity_threshold >= 0.0, "similarity_threshold must be non-negative"
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
    assert all(f.rule == "config:duplicate-name" for f in out), "wrong rule tag"
    return out


def check_config(config: Config, path: Path) -> list[Finding]:
    result = (
        _forbidden_canonical_clashes(config, path)
        + _alias_conflicts(config, path)
        + _duplicate_names(config, path)
    )
    assert all(f.rule.startswith("config:") for f in result), (
        "config findings must use config: rules"
    )
    assert all(f.line == 0 for f in result), "config findings anchor to line 0"
    return result
