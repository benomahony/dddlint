import pytest

from dddlint.config import Config
from dddlint.insights import Insight, threshold_for

pytestmark = pytest.mark.unit


def test_threshold_falls_back_to_similarity_threshold():
    assert threshold_for(Config(similarity_threshold=0.7)) == 0.7


def test_threshold_prefers_the_embeddings_override():
    config = Config(similarity_threshold=0.99)
    config.embeddings.threshold = 0.9
    assert threshold_for(config) == 0.9


def test_insight_carries_the_names_it_relates():
    insight = Insight("near-synonym", "pick one", ("a", "b"), 0.9)
    assert insight.names == ("a", "b")
    assert insight.line == 0
