from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .check import scope_of, tokenise
from .cluster import Vector, centroid, clusters, nearest, similarities
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


def context_outliers(
    definitions: list[Definition], vectors: Mapping[str, Vector], config: Config
) -> list[Insight]:
    assert all(d.name for d in definitions), "every definition must have a name"
    assert config.embeddings.outlier_margin >= 0.0, "outlier margin must be non-negative"
    known = _first_seen(definitions, vectors)
    grouped: dict[str, list[Vector]] = defaultdict(list)
    for name, definition in known.items():
        grouped[scope_of(config, definition.path)].append(vectors[name])
    if len(grouped) < 2:
        return []
    centroids = {label: centroid(members) for label, members in grouped.items()}
    out: list[Insight] = []
    for name, definition in known.items():
        home = scope_of(config, definition.path)
        elsewhere, score = nearest(vectors[name], centroids)
        at_home = float(similarities([vectors[name], centroids[home]])[0][1])
        if elsewhere == home or score - at_home < config.embeddings.outlier_margin:
            continue
        out.append(
            Insight(
                "context-outlier",
                f"reads like {elsewhere} vocabulary but lives in {home}",
                (name,),
                score - at_home,
                definition.path,
                definition.line,
            )
        )
    return sorted(out, key=lambda insight: -insight.score)
