import asyncio
from collections.abc import Sequence

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


def test_embed_names_returns_a_vector_per_name():
    model = LetterEmbeddingModel()
    vectors = asyncio.run(embed_names(["Order", "Invoice"], Embeddings(), model))
    assert sorted(vectors) == ["Invoice", "Order"]
    assert vectors["Order"][ALPHABET.index("r")] == 2.0


def test_embed_names_batches_and_embeds_each_name_once():
    model = LetterEmbeddingModel()
    names = ["Order", "Invoice", "Order", "Customer"]
    vectors = asyncio.run(embed_names(names, Embeddings(batch_size=2), model))
    assert [len(batch) for batch in model.batches] == [2, 1]
    assert len(vectors) == 3
