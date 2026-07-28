import asyncio
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic_ai.embeddings import EmbeddingModel, EmbeddingResult, EmbeddingSettings
from pydantic_ai.embeddings.result import EmbedInputType

from dddlint.config import Embeddings
from dddlint.embed import embed_names

pytestmark = pytest.mark.unit

ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class LetterEmbeddingModel(EmbeddingModel):
    """Real embedder: one dimension per letter, so vectors are deterministic."""

    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    @property
    def model_name(self) -> str:
        return "letter"

    @property
    def system(self) -> str:
        return "test"

    async def embed(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: EmbedInputType,
        settings: EmbeddingSettings | None = None,
    ) -> EmbeddingResult:
        texts, _ = self.prepare_embed(inputs, settings)
        self.batches.append(texts)
        return EmbeddingResult(
            [[float(text.lower().count(letter)) for letter in ALPHABET] for text in texts],
            inputs=texts,
            input_type=input_type,
            model_name=self.model_name,
            provider_name=self.system,
        )


def test_embed_names_returns_a_vector_per_name(tmp_path: Path):
    model = LetterEmbeddingModel()
    config = Embeddings(cache=tmp_path / "embeddings.json")
    vectors = asyncio.run(embed_names(["Order", "Invoice"], config, model))
    assert sorted(vectors) == ["Invoice", "Order"]
    assert vectors["Order"][ALPHABET.index("r")] == 2.0


def test_embed_names_batches_and_embeds_each_name_once(tmp_path: Path):
    model = LetterEmbeddingModel()
    names = ["Order", "Invoice", "Order", "Customer"]
    config = Embeddings(batch_size=2, cache=tmp_path / "embeddings.json")
    vectors = asyncio.run(embed_names(names, config, model))
    assert [len(batch) for batch in model.batches] == [2, 1]
    assert len(vectors) == 3


class OverlapTrackingModel(LetterEmbeddingModel):
    """Records whether two batches were ever in flight at the same time."""

    def __init__(self) -> None:
        super().__init__()
        self.in_flight = 0
        self.peak_in_flight = 0

    async def embed(
        self,
        inputs: str | Sequence[str],
        *,
        input_type: EmbedInputType,
        settings: EmbeddingSettings | None = None,
    ) -> EmbeddingResult:
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        await asyncio.sleep(0)
        try:
            return await super().embed(inputs, input_type=input_type, settings=settings)
        finally:
            self.in_flight -= 1


def test_batches_never_overlap(tmp_path: Path):
    model = OverlapTrackingModel()
    config = Embeddings(batch_size=1, cache=tmp_path / "embeddings.json")
    asyncio.run(embed_names(["Order", "Invoice", "Customer"], config, model))
    assert len(model.batches) == 3
    assert model.peak_in_flight == 1


def test_second_run_reads_the_cache_instead_of_the_model(tmp_path: Path):
    config = Embeddings(cache=tmp_path / "embeddings.json")
    first = asyncio.run(embed_names(["Order"], config, LetterEmbeddingModel()))
    second_model = LetterEmbeddingModel()
    second = asyncio.run(embed_names(["Order"], config, second_model))
    assert second == first
    assert second_model.batches == []


def test_cache_is_discarded_when_the_model_changes(tmp_path: Path):
    cache = tmp_path / "embeddings.json"
    asyncio.run(embed_names(["Order"], Embeddings(cache=cache), LetterEmbeddingModel()))
    model = LetterEmbeddingModel()
    asyncio.run(embed_names(["Order"], Embeddings(cache=cache, dimensions=4), model))
    assert model.batches == [["Order"]]


def test_cache_only_embeds_the_names_it_is_missing(tmp_path: Path):
    config = Embeddings(cache=tmp_path / "embeddings.json")
    asyncio.run(embed_names(["Order"], config, LetterEmbeddingModel()))
    model = LetterEmbeddingModel()
    vectors = asyncio.run(embed_names(["Order", "Invoice"], config, model))
    assert model.batches == [["Invoice"]]
    assert sorted(vectors) == ["Invoice", "Order"]
