from difflib import SequenceMatcher
from pathlib import Path

from .check import Finding
from .config import Config, Context, SynonymGroup


def _alias_map(synonyms: list[SynonymGroup]) -> dict[str, str]:
    return {alias.lower(): g.canonical.lower() for g in synonyms for alias in g.aliases}


def check_config(config: Config, path: Path) -> list[Finding]:
    out: list[Finding] = []

    global_aliases = _alias_map(config.synonyms)
    global_forbidden = {t.lower() for t in config.forbidden}
    global_canonicals = {g.canonical.lower() for g in config.synonyms}

    # forbidden term that is also a canonical (contradiction)
    for term in global_forbidden & global_canonicals:
        out.append(
            Finding(
                path, 0, term, "config:forbidden-canonical-clash",
                f"'{term}' is both forbidden and a canonical synonym",
            )
        )

    # alias resolves to different canonicals across scopes
    scopes: list[tuple[str, list[SynonymGroup]]] = [("global", config.synonyms)]
    for s in config.domains:
        scopes.append((f"domain:{s.name}", s.synonyms))
    for s in config.contexts:
        scopes.append((f"context:{s.name}", s.synonyms))

    seen: dict[str, tuple[str, str]] = {}
    for scope_name, synonyms in scopes:
        for alias, canonical in _alias_map(synonyms).items():
            if alias in seen and seen[alias][1] != canonical:
                prev_scope, prev_canonical = seen[alias]
                out.append(
                    Finding(
                        path, 0, alias, "config:alias-conflict",
                        f"'{alias}' → '{canonical}' in {scope_name} but → '{prev_canonical}' in {prev_scope}",
                    )
                )
            else:
                seen[alias] = (scope_name, canonical)

    # domains/contexts with similar names (likely duplicates)
    all_scopes: list[Context] = config.domains + config.contexts
    for i, a in enumerate(all_scopes):
        for b in all_scopes[i + 1:]:
            similarity = SequenceMatcher(None, a.name.lower(), b.name.lower()).ratio()
            if similarity >= config.similarity_threshold:
                out.append(
                    Finding(
                        path, 0, a.name, "config:duplicate-name",
                        f"'{a.name}' and '{b.name}' look like the same domain/context",
                    )
                )

    return out
