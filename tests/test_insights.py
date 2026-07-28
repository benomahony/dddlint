from pathlib import Path

import pytest

from dddlint.config import Config
from dddlint.extract import Definition
from dddlint.insights import Insight, near_synonyms, threshold_for

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


EAST = [1.0, 0.0]
EAST_ISH = [0.96, 0.28]
NORTH = [0.0, 1.0]


def definition(name: str) -> Definition:
    return Definition(name, "Function", Path("src/core/a.py"), 1)


def test_near_synonyms_reports_close_names_with_no_shared_token():
    definitions = [definition("fetch_order"), definition("retrieve_purchase")]
    vectors = {"fetch_order": EAST, "retrieve_purchase": EAST_ISH}
    insights = near_synonyms(definitions, vectors, Config(similarity_threshold=0.9))
    assert [i.rule for i in insights] == ["near-synonym"]
    assert insights[0].names == ("fetch_order", "retrieve_purchase")
    assert insights[0].score == pytest.approx(0.96)


def test_near_synonyms_ignores_names_that_already_share_vocabulary():
    definitions = [definition("fetch_order"), definition("order_fetcher")]
    vectors = {"fetch_order": EAST, "order_fetcher": EAST_ISH}
    assert near_synonyms(definitions, vectors, Config(similarity_threshold=0.9)) == []


def test_near_synonyms_ignores_distant_names():
    definitions = [definition("fetch_order"), definition("send_invoice")]
    vectors = {"fetch_order": EAST, "send_invoice": NORTH}
    assert near_synonyms(definitions, vectors, Config(similarity_threshold=0.9)) == []
