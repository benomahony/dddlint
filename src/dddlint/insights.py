from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .check import tokenise
from .cluster import Vector, clusters, similarities
from .config import Config
from .extract import Definition


@dataclass(frozen=True, slots=True)
class Insight:
    rule: str
    message: str
    names: tuple[str, ...]
    score: float
    path: Path | None = None
    line: int = 0


def threshold_for(config: Config) -> float:
    assert config.similarity_threshold >= 0.0, "similarity_threshold must be non-negative"
    threshold = config.embeddings.threshold
    assert threshold is None or threshold >= 0.0, "embeddings threshold must be non-negative"
    return config.similarity_threshold if threshold is None else threshold


def _first_seen(
    definitions: list[Definition], vectors: Mapping[str, Vector]
) -> dict[str, Definition]:
    assert all(d.name for d in definitions), "every definition must have a name"
    assert isinstance(vectors, Mapping), "vectors must be a mapping of name to vector"
    out: dict[str, Definition] = {}
    for definition in definitions:
        if definition.name in vectors:
            out.setdefault(definition.name, definition)
    return out


def near_synonyms(
    definitions: list[Definition], vectors: Mapping[str, Vector], config: Config
) -> list[Insight]:
    assert all(d.name for d in definitions), "every definition must have a name"
    assert all(vectors.values()), "every vector must have components"
    known = _first_seen(definitions, vectors)
    if not known:
        return []
    names = sorted(known)
    matrix = similarities([vectors[name] for name in names])
    out: list[Insight] = []
    for group in clusters([vectors[name] for name in names], threshold_for(config)):
        members = tuple(names[index] for index in group)
        if len(members) < 2 or set.intersection(*(set(tokenise(m)) for m in members)):
            continue
        score = min(matrix[a][b] for a in group for b in group if a != b)
        out.append(
            Insight(
                "near-synonym",
                f"same idea, unrelated words: {', '.join(members)}; pick one canonical term",
                members,
                float(score),
                known[members[0]].path,
                known[members[0]].line,
            )
        )
    return sorted(out, key=lambda insight: -insight.score)
