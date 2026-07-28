import asyncio
from collections.abc import Sequence

from pydantic_ai.embeddings import Embedder, EmbeddingModel, EmbeddingSettings

from .config import Embeddings

Vector = list[float]


def _batches(names: list[str], size: int) -> list[list[str]]:
    assert size > 0, "batch size must be positive"
    assert isinstance(names, list), "names must be a list to slice into batches"
    return [names[start : start + size] for start in range(0, len(names), size)]


def _embedder(config: Embeddings, model: EmbeddingModel | None) -> Embedder:
    assert config.model, "an embedding model must be configured"
    assert config.dimensions is None or config.dimensions > 0, "dimensions must be positive"
    settings = EmbeddingSettings(dimensions=config.dimensions) if config.dimensions else None
    return Embedder(model or config.model, settings=settings)


async def embed_names(
    names: Sequence[str], config: Embeddings, model: EmbeddingModel | None = None
) -> dict[str, Vector]:
    assert all(names), "every name must be non-empty to embed"
    assert config.batch_size > 0, "batch size must be positive"
    batches = _batches(sorted(set(names)), config.batch_size)
    embedder = _embedder(config, model)
    results = await asyncio.gather(*(embedder.embed_documents(batch) for batch in batches))
    vectors = {
        name: [float(component) for component in vector]
        for batch, result in zip(batches, results, strict=True)
        for name, vector in zip(batch, result.embeddings, strict=True)
    }
    assert len(vectors) == len(set(names)), "every distinct name must receive a vector"
    return vectors
