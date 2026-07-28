from collections.abc import Sequence

import numpy as np

Vector = Sequence[float]


def _unit(vectors: Sequence[Vector]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float64)
    assert matrix.ndim == 2, "vectors must form a 2-D matrix of equal-length rows"
    assert matrix.shape[0] > 0, "need at least one vector"
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def similarities(vectors: Sequence[Vector]) -> np.ndarray:
    assert len(vectors) > 0, "need at least one vector to compare"
    unit = _unit(vectors)
    matrix = unit @ unit.T
    assert matrix.shape == (len(vectors), len(vectors)), "cosine matrix must be square"
    return matrix


def project(vectors: Sequence[Vector]) -> list[tuple[float, float]]:
    assert len(vectors) > 0, "need at least one vector to project"
    matrix = np.asarray(vectors, dtype=np.float64)
    assert matrix.ndim == 2, "vectors must form a 2-D matrix of equal-length rows"
    centred = matrix - matrix.mean(axis=0)
    axes = np.linalg.svd(centred, full_matrices=False)[2][:2]
    if axes.shape[0] < 2:
        axes = np.vstack([axes, np.zeros_like(axes[:1])])
    return [(float(x), float(y)) for x, y in centred @ axes.T]


def centroid(vectors: Sequence[Vector]) -> list[float]:
    assert len(vectors) > 0, "need at least one vector for a centroid"
    unit = _unit(vectors)
    mean = unit.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    assert norm >= 0.0, "a vector norm cannot be negative"
    return [float(component) for component in mean / (norm or 1.0)]


def nearest(vector: Vector, centroids: dict[str, Vector]) -> tuple[str, float]:
    assert centroids, "need at least one centroid to compare against"
    assert len(vector) > 0, "vector must have components to compare"
    scores = {
        label: float(similarities([vector, other])[0][1]) for label, other in centroids.items()
    }
    best = max(scores, key=lambda label: scores[label])
    assert best in centroids, "the winner must be one of the given centroids"
    return best, scores[best]


def _root(parent: list[int], index: int) -> int:
    assert 0 <= index < len(parent), "index must address a known vector"
    assert parent, "parent chain must be initialised"
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def clusters(vectors: Sequence[Vector], threshold: float) -> list[list[int]]:
    assert 0.0 <= threshold <= 1.0, "threshold must be a cosine in [0, 1]"
    assert len(vectors) > 0, "need at least one vector to cluster"
    matrix = similarities(vectors)
    parent = list(range(len(vectors)))
    for i, j in zip(*np.where(np.triu(matrix >= threshold, k=1)), strict=True):
        a, b = _root(parent, int(i)), _root(parent, int(j))
        if a != b:
            parent[b] = a
    grouped: dict[int, list[int]] = {}
    for index in range(len(vectors)):
        grouped.setdefault(_root(parent, index), []).append(index)
    out = sorted(grouped.values())
    assert sum(len(group) for group in out) == len(vectors), "every vector lands in one cluster"
    return out
