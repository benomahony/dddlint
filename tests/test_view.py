import json

import pytest

from dddlint.config import Config, Context, SynonymGroup
from dddlint.insights import UNASSIGNED, Insight, Point
from dddlint.view import OTHER, SERIES, UNOWNED, _build_graph, _build_scatter, _generate_html

pytestmark = pytest.mark.unit


def test_build_graph_always_has_global_node():
    graph = _build_graph(Config())
    assert any(n["id"] == "global" for n in graph["nodes"])


def test_build_graph_forbidden_terms():
    graph = _build_graph(Config(forbidden=["manager"]))
    node = next(n for n in graph["nodes"] if n["id"] == "forbidden:manager")
    assert node["type"] == "forbidden"
    assert {"source": "global", "target": "forbidden:manager", "kind": "forbidden"} in graph[
        "edges"
    ]


def test_build_graph_synonyms_link_alias_to_canonical():
    graph = _build_graph(Config(synonyms=[SynonymGroup(canonical="customer", aliases=["client"])]))
    assert any(n["id"] == "canonical:customer" for n in graph["nodes"])
    assert {"source": "alias:client", "target": "canonical:customer", "kind": "alias"} in graph[
        "edges"
    ]


def test_build_graph_scopes_domains_and_contexts():
    graph = _build_graph(
        Config(
            domains=[Context(name="commerce", include=["**"], forbidden=["util"])],
            contexts=[
                Context(
                    name="billing",
                    include=["**"],
                    synonyms=[SynonymGroup(canonical="invoice", aliases=["bill"])],
                )
            ],
        )
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert "domain:commerce" in ids
    assert "context:billing" in ids
    assert "forbidden:domain:commerce:util" in ids
    assert "alias:context:billing:bill" in ids


def test_build_graph_dedupes_repeated_nodes():
    graph = _build_graph(Config(forbidden=["dup", "dup"]))
    matches = [n for n in graph["nodes"] if n["id"] == "forbidden:dup"]
    assert len(matches) == 1


def test_generate_html_embeds_graph_json():
    graph = _build_graph(Config(forbidden=["manager"]))
    html = _generate_html(Config(forbidden=["manager"]))
    assert html.startswith("<!DOCTYPE html>")
    assert json.dumps(graph) in html


def point(name: str, scope: str, cluster: int, x: float = 0.0, y: float = 0.0) -> Point:
    return Point(name, x, y, "noun", scope, cluster)


def test_scatter_colours_scopes_by_how_common_they_are():
    points = [
        point("Invoice", "billing", 0),
        point("Bill", "billing", 0),
        point("Order", "core", 1),
        point("Widget", "shop", 2),
        point("Thing", "extra", 3),
    ]
    scatter = _build_scatter(points, [])
    colors = {entry["scope"]: entry["color"] for entry in scatter["legend"]}
    assert colors["billing"] == SERIES[0]
    assert colors["extra"] == OTHER


def test_scatter_bounds_one_region_per_context():
    points = [
        point("Invoice", "billing", 0, 0.0, 0.0),
        point("Bill", "billing", 0, 1.0, 0.0),
        point("Order", "core", 1, 5.0, 5.0),
    ]
    regions = _build_scatter(points, [])["regions"]
    assert [region["scope"] for region in regions] == ["billing", "core"]
    assert [disc[:2] for disc in regions[0]["discs"]][::2] == [[0.0, 0.0], [1.0, 0.0]]
    assert regions[0]["edges"] == [[[0.0, 0.0], [1.0, 0.0]]]


def test_scatter_draws_no_boundary_around_unassigned_names():
    points = [
        point("Invoice", "billing", 0, 0.0, 0.0),
        point("Bill", "billing", 0, 1.0, 0.0),
        point("Widget", UNASSIGNED, 1, 5.0, 5.0),
    ]
    scatter = _build_scatter(points, [])
    assert [region["scope"] for region in scatter["regions"]] == ["billing"]
    assert {p["name"]: p["unassigned"] for p in scatter["points"]}["Widget"] is True


def test_scatter_keeps_the_series_colours_for_named_contexts():
    points = [
        point("Widget", UNASSIGNED, 0),
        point("Spanner", UNASSIGNED, 0),
        point("Invoice", "billing", 1),
    ]
    colors = {entry["scope"]: entry["color"] for entry in _build_scatter(points, [])["legend"]}
    assert colors == {"billing": SERIES[0], UNASSIGNED: UNOWNED}


def test_scatter_joins_a_scattered_context_into_one_region():
    points = [
        point("Invoice", "billing", 0, 0.0, 0.0),
        point("Bill", "billing", 0, 1.0, 0.0),
        point("Statement", "billing", 0, 90.0, 0.0),
    ]
    region = _build_scatter(points, [])["regions"][0]
    assert len(region["discs"]) == 6
    assert region["edges"] == [[[0.0, 0.0], [1.0, 0.0]], [[1.0, 0.0], [90.0, 0.0]]]


def test_scatter_gives_each_name_its_own_lopsided_lump():
    points = [point("Invoice", "billing", 0, 0.0, 0.0), point("Bill", "billing", 0, 1.0, 0.0)]
    discs = _build_scatter(points, [])["regions"][0]["discs"]
    assert len({disc[2] for disc in discs}) > 1
    assert all(0.6 <= disc[2] <= 1.3 for disc in discs)


def test_scatter_sizes_blobs_from_the_typical_spacing():
    points = [point("Invoice", "billing", 0, 0.0, 0.0), point("Bill", "billing", 0, 2.0, 0.0)]
    assert _build_scatter(points, [])["radius"] == pytest.approx(1.5)


def test_scatter_flags_names_reported_as_context_outliers():
    insight = Insight("context-outlier", "reads like billing", ("Order",), 0.2)
    points = [point("Invoice", "billing", 0), point("Order", "core", 1)]
    flagged = {p["name"]: p["outlier"] for p in _build_scatter(points, [insight])["points"]}
    assert flagged == {"Invoice": False, "Order": True}


def test_scatter_anchors_one_name_per_populated_cluster():
    points = [
        point("Invoice", "billing", 0, 0.0, 0.0),
        point("Bill", "billing", 0, 1.0, 0.0),
        point("Statement", "billing", 0, 4.0, 0.0),
        point("Order", "core", 1, 9.0, 9.0),
    ]
    anchored = {p["name"] for p in _build_scatter(points, [])["points"] if p["anchor"]}
    assert anchored == {"Bill"}
