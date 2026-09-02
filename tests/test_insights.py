from pathlib import Path

import pytest

from dddlint.config import Config, Context, Embeddings
from dddlint.extract import Definition
from dddlint.insights import (
    UNASSIGNED,
    Insight,
    Suggestion,
    context_outliers,
    discover_domains,
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


def test_map_points_call_a_name_outside_every_context_unassigned():
    definitions = [in_context("Invoice", "billing"), Definition("Widget", "Class", Path("x.py"), 1)]
    vectors = {"Invoice": EAST, "Widget": NORTH}
    points = {p.name: p for p in map_points(definitions, vectors, BILLING)}
    assert points["Widget"].scope == UNASSIGNED
    assert points["Invoice"].scope == "billing"


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


BILLING_VECTORS = {"Invoice": [1.0, 0.0], "Charge": [0.999, 0.045], "Ledger": [0.998, 0.06]}
SHIPPING_VECTORS = {"Parcel": [0.0, 1.0], "Dispatch": [0.2, 0.98], "Courier": [0.28, 0.96]}
DISCOVER = Config(embeddings=Embeddings(threshold=0.9))


def in_folder(name: str, folder: str) -> Definition:
    return Definition(name, "Class", Path(f"src/{folder}/a.py"), 1)


def _two_clusters() -> tuple[list[Definition], dict[str, list[float]]]:
    definitions = [in_folder(name, "billing") for name in BILLING_VECTORS]
    definitions += [in_folder(name, "shipping") for name in SHIPPING_VECTORS]
    return definitions, BILLING_VECTORS | SHIPPING_VECTORS


def test_discover_suggests_the_single_strongest_domain_by_default():
    definitions, vectors = _two_clusters()
    out = discover_domains(definitions, vectors, DISCOVER)
    assert len(out) == 1
    assert out[0].name == "billing"
    assert out[0].include == "**/billing/**"
    assert set(out[0].members) == set(BILLING_VECTORS)


def test_discover_returns_every_cluster_ranked_by_strength_when_limit_is_zero():
    definitions, vectors = _two_clusters()
    out = discover_domains(definitions, vectors, DISCOVER, limit=0)
    assert [suggestion.name for suggestion in out] == ["billing", "shipping"]
    assert out[0].cohesion > out[1].cohesion


def test_discover_ignores_clusters_too_small_to_be_a_domain():
    definitions = [in_folder(name, "billing") for name in BILLING_VECTORS]
    definitions += [in_folder("Widget", "misc"), in_folder("Gadget", "misc")]
    vectors = BILLING_VECTORS | {"Widget": [0.0, 1.0], "Gadget": [0.1, 0.99]}
    out = discover_domains(definitions, vectors, DISCOVER, limit=0)
    assert [suggestion.name for suggestion in out] == ["billing"]


def test_discover_skips_names_already_inside_a_declared_domain():
    config = Config(
        domains=[Context(name="billing", include=["**/billing/**"])],
        embeddings=Embeddings(threshold=0.9),
    )
    definitions, vectors = _two_clusters()
    out = discover_domains(definitions, vectors, config, limit=0)
    assert [suggestion.name for suggestion in out] == ["shipping"]


def test_discover_whole_mode_clusters_declared_names_and_records_their_scope():
    config = Config(
        domains=[Context(name="billing", include=["**/billing/**"])],
        embeddings=Embeddings(threshold=0.9),
    )
    definitions, vectors = _two_clusters()
    out = {
        suggestion.name: suggestion
        for suggestion in discover_domains(definitions, vectors, config, whole=True, limit=0)
    }
    assert out["billing"].scopes == ("billing",)
    assert out["shipping"].scopes == ("global",)


def test_discover_names_a_scattered_cluster_after_its_vocabulary():
    definitions = [Definition(name, "Class", Path("src/a.py"), 1) for name in BILLING_VECTORS]
    out = discover_domains(definitions, BILLING_VECTORS, DISCOVER, limit=0)
    assert out[0].name == "charge"
    assert out[0].include == "**/charge/**"


def test_discover_needs_a_domains_worth_of_names():
    definitions = [in_folder("Invoice", "billing"), in_folder("Charge", "billing")]
    vectors = {"Invoice": [1.0, 0.0], "Charge": [0.999, 0.045]}
    assert discover_domains(definitions, vectors, DISCOVER, limit=0) == []


# Alpha-Bravo and Bravo-Charlie each sit at cosine 0.75, so single linkage chains all three,
# but the group averages 0.70 — below the 0.72 floor, so it should never be proposed.
CHAINED = {
    "Alpha": [1.0, 0.0, 0.0],
    "Bravo": [0.75, 0.6614378, 0.0],
    "Charlie": [0.60, 0.453561, 0.659002],
}


def test_discover_drops_a_loosely_chained_cluster_below_the_floor():
    definitions = [in_folder(name, "misc") for name in CHAINED]
    assert discover_domains(definitions, CHAINED, Config(), limit=0) == []


def test_discover_never_proposes_a_domain_of_tests():
    names = ["test_charge", "test_refund", "test_invoice"]
    definitions = [Definition(name, "Function", Path(f"tests/{name}.py"), 1) for name in names]
    vectors = {
        "test_charge": [1.0, 0.0],
        "test_refund": [0.999, 0.045],
        "test_invoice": [0.998, 0.06],
    }
    assert discover_domains(definitions, vectors, Config(), limit=0) == []


def test_discover_rejects_one_word_spelled_several_ways():
    names = ["Signal", "signal", "signals"]
    definitions = [Definition(name, "Class", Path("src/core/a.py"), 1) for name in names]
    vectors = {"Signal": [1.0, 0.0], "signal": [0.999, 0.045], "signals": [0.998, 0.06]}
    assert discover_domains(definitions, vectors, Config(), limit=0) == []


def test_suggestion_rank_weights_cohesion_by_size():
    small = Suggestion("a", "**/a/**", ("x", "y"), 0.9, ("global",))
    big = Suggestion("b", "**/b/**", ("p", "q", "r", "s"), 0.9, ("global",))
    assert big.rank > small.rank


def test_near_synonyms_ignores_names_chained_through_a_shared_word():
    definitions = [definition("_alias_map"), definition("map_points")]
    vectors = {"_alias_map": EAST, "map_points": EAST_ISH}
    config = Config(embeddings=Embeddings(threshold=0.9))
    assert near_synonyms(definitions, vectors, config) == []


def test_near_synonyms_score_averages_the_cluster_rather_than_its_weakest_pair():
    definitions = [definition("fetch"), definition("retrieve"), definition("collect")]
    vectors = {"fetch": EAST, "retrieve": EAST_ISH, "collect": [0.9, 0.44]}
    config = Config(embeddings=Embeddings(threshold=0.9))
    insights = near_synonyms(definitions, vectors, config)
    assert len(insights) == 1
    assert 0.9 < insights[0].score < 1.0
