import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic_ai.embeddings import Embedder, EmbeddingModel, EmbeddingSettings

from .config import Embeddings

Vector = list[float]


def _cache_key(config: Embeddings, model: EmbeddingModel | None) -> str:
    name = model.model_name if model is not None else config.model
    assert name, "an embedding model must have a name to key the cache"
    assert config.dimensions is None or config.dimensions > 0, "dimensions must be positive"
    return f"{name}/{config.dimensions or 'native'}"


def _load_cache(path: Path, key: str) -> dict[str, Vector]:
    assert key, "cache key must be non-empty"
    assert path.name, "cache path must have a filename"
    if not path.exists():
        return {}
    cached = json.loads(path.read_text() or "{}")
    assert isinstance(cached, dict), "cache file must hold a JSON object"
    if cached.get("key") != key:
        return {}
    return {name: list(vector) for name, vector in cached["vectors"].items()}


def _write_cache(path: Path, key: str, vectors: dict[str, Vector]) -> None:
    assert key, "cache key must be non-empty"
    assert vectors, "refusing to write an empty cache"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": key, "vectors": vectors}))


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
    key = _cache_key(config, model)
    vectors = _load_cache(config.cache, key)
    batches = _batches(sorted(set(names) - set(vectors)), config.batch_size)
    if batches:
        embedder = _embedder(config, model)
        results = await asyncio.gather(*(embedder.embed_documents(batch) for batch in batches))
        vectors |= {
            name: [float(component) for component in vector]
            for batch, result in zip(batches, results, strict=True)
            for name, vector in zip(batch, result.embeddings, strict=True)
        }
        _write_cache(config.cache, key, vectors)
    assert set(names) <= set(vectors), "every distinct name must receive a vector"
    return {name: vectors[name] for name in sorted(set(names))}
