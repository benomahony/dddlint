from pathlib import Path

import pytest

from dddlint.config import Config, Context, Embeddings
from dddlint.extract import Definition
from dddlint.insights import (
    Insight,
    context_outliers,
    map_points,
    near_synonyms,
    role_of,
    threshold_for,
)

pytestmark = pytest.mark.unit


def test_threshold_defaults_below_the_scope_name_scale():
    assert threshold_for(Config()) == 0.6


def test_threshold_reads_the_configured_cosine():
    config = Config()
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
    insights = near_synonyms(definitions, vectors, Config(embeddings=Embeddings(threshold=0.9)))
    assert [i.rule for i in insights] == ["near-synonym"]
    assert insights[0].names == ("fetch_order", "retrieve_purchase")
    assert insights[0].score == pytest.approx(0.96)


def test_near_synonyms_ignores_names_that_already_share_vocabulary():
    definitions = [definition("fetch_order"), definition("order_fetcher")]
    vectors = {"fetch_order": EAST, "order_fetcher": EAST_ISH}
    assert near_synonyms(definitions, vectors, Config(embeddings=Embeddings(threshold=0.9))) == []


def test_near_synonyms_ignores_distant_names():
    definitions = [definition("fetch_order"), definition("send_invoice")]
    vectors = {"fetch_order": EAST, "send_invoice": NORTH}
    assert near_synonyms(definitions, vectors, Config(embeddings=Embeddings(threshold=0.9))) == []


def in_context(name: str, folder: str) -> Definition:
    return Definition(name, "Class", Path(f"src/{folder}/a.py"), 2)


BILLING = Config(
    contexts=[
        Context(name="billing", include=["**/billing/**"]),
        Context(name="core", include=["**/core/**"]),
    ]
)


def test_context_outlier_flags_a_name_clustering_with_another_context():
    definitions = [
        in_context("Invoice", "billing"),
        in_context("InvoiceLine", "billing"),
        in_context("Order", "core"),
        in_context("InvoiceTotal", "core"),
    ]
    vectors = {
        "Invoice": EAST,
        "InvoiceLine": EAST_ISH,
        "Order": NORTH,
        "InvoiceTotal": [0.98, 0.2],
    }
    insights = context_outliers(definitions, vectors, BILLING)
    assert [i.names for i in insights] == [("InvoiceTotal",)]
    assert "billing" in insights[0].message and "core" in insights[0].message


def test_context_outlier_stays_quiet_when_names_sit_in_their_own_context():
    definitions = [in_context("Invoice", "billing"), in_context("Order", "core")]
    vectors = {"Invoice": EAST, "Order": NORTH}
    assert context_outliers(definitions, vectors, BILLING) == []


def test_context_outlier_needs_at_least_two_contexts():
    definitions = [in_context("Invoice", "billing"), in_context("Order", "billing")]
    vectors = {"Invoice": EAST, "Order": NORTH}
    assert context_outliers(definitions, vectors, BILLING) == []


def test_role_splits_nouns_from_verbs():
    assert role_of("Class") == "noun"
    assert role_of("Method") == "verb"
    assert role_of("Constant") == "noun"


def test_map_points_carry_layout_role_scope_and_cluster():
    definitions = [
        in_context("Invoice", "billing"),
        Definition("charge_card", "Function", Path("src/billing/a.py"), 3),
        in_context("Order", "core"),
    ]
    vectors = {"Invoice": EAST, "charge_card": EAST_ISH, "Order": NORTH}
    points = {p.name: p for p in map_points(definitions, vectors, BILLING)}
    assert points["Invoice"].role == "noun" and points["charge_card"].role == "verb"
    assert points["Order"].scope == "core"
    assert points["Invoice"].cluster != points["Order"].cluster
    assert points["Invoice"].cluster == points["charge_card"].cluster


def test_near_synonyms_ignores_a_plural_of_the_same_token():
    definitions = [definition("Definition"), definition("definitions")]
    vectors = {"Definition": EAST, "definitions": EAST_ISH}
    config = Config(embeddings=Embeddings(threshold=0.9))
    assert near_synonyms(definitions, vectors, config) == []


def test_near_synonyms_ignores_one_word_family():
    definitions = [definition("Embeddings"), definition("_embedder"), definition("embed_names")]
    vectors = {"Embeddings": EAST, "_embedder": EAST_ISH, "embed_names": [0.97, 0.24]}
    config = Config(embeddings=Embeddings(threshold=0.9))
    assert near_synonyms(definitions, vectors, config) == []


def test_near_synonyms_ignores_names_chained_through_a_shared_word():
    definitions = [definition("_alias_map"), definition("map_points")]
    vectors = {"_alias_map": EAST, "map_points": EAST_ISH}
    config = Config(embeddings=Embeddings(threshold=0.9))
    assert near_synonyms(definitions, vectors, config) == []
