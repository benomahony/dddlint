from dataclasses import dataclass
from pathlib import Path

from .config import Config


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
