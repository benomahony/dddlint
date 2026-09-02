from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import takewhile
from math import sqrt
from pathlib import Path

from .check import is_test_definition, owning_scope, scope_of, tokenise
from .cluster import Vector, centroid, clusters, nearest, project, similarities
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
    threshold = config.embeddings.threshold
    assert 0.0 <= threshold <= 1.0, "embeddings threshold must be a cosine in [0, 1]"
    assert config.embeddings.model, "an embedding model must be configured"
    return threshold


def discover_threshold_for(config: Config) -> float:
    threshold = config.embeddings.discover_threshold
    assert 0.0 <= threshold <= 1.0, "discover threshold must be a cosine in [0, 1]"
    assert config.embeddings.model, "an embedding model must be configured"
    return threshold


def _same_token(first: str, second: str) -> bool:
    assert first and second, "tokens must be non-empty to compare"
    assert first == first.lower() and second == second.lower(), "tokens must be lowercased"
    if first == second:
        return True
    shared = sum(1 for _ in takewhile(lambda pair: pair[0] == pair[1], zip(first, second)))
    return shared >= 5


def _shares_a_token(names: tuple[str, ...]) -> bool:
    assert len(names) > 1, "need at least two names to compare"
    assert all(names), "every name must be non-empty"
    spellings = [tokenise(name) for name in names]
    return any(
        _same_token(left, right)
        for index, first in enumerate(spellings)
        for second in spellings[index + 1 :]
        for left in first
        for right in second
    )


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
        if len(members) < 2 or _shares_a_token(members):
            continue
        pairs = [matrix[a][b] for a in group for b in group if a != b]
        score = sum(pairs) / len(pairs)
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


VERB_KINDS = frozenset({"Function", "Method"})


def role_of(kind: str) -> str:
    assert kind, "kind must be non-empty to classify"
    assert isinstance(kind, str), "kind must be a string"
    return "verb" if kind in VERB_KINDS else "noun"


UNASSIGNED = "unassigned"


@dataclass(frozen=True, slots=True)
class Point:
    name: str
    x: float
    y: float
    role: str
    scope: str
    cluster: int


def map_points(
    definitions: list[Definition], vectors: Mapping[str, Vector], config: Config
) -> list[Point]:
    assert all(d.name for d in definitions), "every definition must have a name"
    assert all(vectors.values()), "every vector must have components"
    known = _first_seen(definitions, vectors)
    if not known:
        return []
    names = sorted(known)
    matrix = [vectors[name] for name in names]
    labels: dict[int, int] = {}
    for label, group in enumerate(clusters(matrix, threshold_for(config))):
        labels |= {index: label for index in group}
    assert len(labels) == len(names), "every name must land in exactly one cluster"
    return [
        Point(
            name,
            x,
            y,
            role_of(known[name].kind),
            owning_scope(config, known[name].path) or UNASSIGNED,
            labels[index],
        )
        for index, ((x, y), name) in enumerate(zip(project(matrix), names, strict=True))
    ]


# a domain is more than a coincidence: below this a cluster is a pair, not a boundary
MIN_DOMAIN = 3
# directory names too generic to name a domain after; fall back to the vocabulary instead
GENERIC_DIRS = frozenset({"src", "lib", "app", "source", "internal", "pkg", "main", ""})


@dataclass(frozen=True, slots=True)
class Suggestion:
    name: str
    include: str
    members: tuple[str, ...]
    cohesion: float
    scopes: tuple[str, ...]

    @property
    def rank(self) -> float:
        """Cohesion weighted by size: a tight pair should not outrank a broad, coherent group."""
        assert 0.0 <= self.cohesion <= 1.0, "cohesion must be a cosine in [0, 1]"
        return self.cohesion * sqrt(len(self.members))


def _concepts(names: list[str]) -> int:
    """Distinct concepts in a cluster, so one word spelled several ways is not a domain.

    ``Signal``, ``signal`` and ``signals`` are one idea restated — that is drift, not a
    bounded context. A domain has to gather several different words to be worth proposing.
    """
    assert all(names), "every clustered name must be non-empty"
    return len({tuple(sorted(tokenise(name))) for name in names})


def _cohesion(vectors: list[Vector]) -> float:
    assert len(vectors) > 1, "cohesion needs at least two vectors to average over pairs"
    matrix = similarities(vectors)
    pairs = [matrix[a][b] for a in range(len(vectors)) for b in range(a + 1, len(vectors))]
    assert pairs, "a cluster of two or more names has at least one pair"
    return sum(pairs) / len(pairs)


def _glob_and_name(paths: list[Path], vocabulary: str) -> tuple[str, str]:
    """Where the cluster lives (a path glob) and what to call it (its directory, else its words)."""
    assert paths, "a suggestion must have member paths to place"
    assert vocabulary, "need a fallback name drawn from the vocabulary"
    modal, _ = Counter(path.parent.name for path in paths).most_common(1)[0]
    if modal in GENERIC_DIRS:
        return f"**/{vocabulary}/**", vocabulary
    return f"**/{modal}/**", modal


def _domain_name(names: list[str], vectors: Mapping[str, Vector]) -> str:
    """The cluster's centre of gravity: the first token of the name nearest its centroid."""
    assert names, "a cluster names at least one definition"
    hub = centroid([vectors[name] for name in names])
    nearest_name = max(names, key=lambda name: similarities([vectors[name], hub])[0][1])
    return tokenise(nearest_name)[0]


def discover_domains(
    definitions: list[Definition],
    vectors: Mapping[str, Vector],
    config: Config,
    *,
    whole: bool = False,
    limit: int = 1,
) -> list[Suggestion]:
    """Cluster names into candidate domains, ranked strongest first.

    By default only names outside every declared domain are considered, so the result
    is the next domain hiding in code you have not carved out yet. With ``whole`` set,
    every name is clustered, which also surfaces clusters that straddle existing
    boundaries. ``limit`` caps how many suggestions are returned; ``limit <= 0`` returns all.

    Tests never form a domain of their own — they belong to whatever they exercise — so
    they are dropped before clustering. A cluster is proposed only when its average
    cohesion clears the discover threshold, so a loose blob chained together by single
    linkage is left unsaid rather than named.
    """
    assert all(d.name for d in definitions), "every definition must have a name"
    assert all(vectors.values()), "every vector must have components"
    known = _first_seen(definitions, vectors)
    chosen = {
        name: definition
        for name, definition in known.items()
        if not is_test_definition(definition)
        and (whole or owning_scope(config, definition.path) is None)
    }
    if len(chosen) < MIN_DOMAIN:
        return []
    floor = discover_threshold_for(config)
    names = sorted(chosen)
    out: list[Suggestion] = []
    for group in clusters([vectors[name] for name in names], floor):
        members = [names[index] for index in group]
        if _concepts(members) < MIN_DOMAIN:
            continue
        cohesion = _cohesion([vectors[member] for member in members])
        if cohesion < floor:
            continue
        vocabulary = _domain_name(members, vectors)
        include, name = _glob_and_name([chosen[member].path for member in members], vocabulary)
        scopes = Counter(scope_of(config, chosen[member].path) for member in members)
        out.append(
            Suggestion(
                name,
                include,
                tuple(members),
                cohesion,
                tuple(scope for scope, _ in scopes.most_common()),
            )
        )
    ranked = sorted(out, key=lambda suggestion: -suggestion.rank)
    return ranked if limit <= 0 else ranked[:limit]
