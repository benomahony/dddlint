import json

import pytest

from dddlint.config import Config, Context, SynonymGroup
from dddlint.insights import UNASSIGNED, Insight, Point, Suggestion
from dddlint.view import (
    OTHER,
    SERIES,
    UNOWNED,
    _build_graph,
    _build_scatter,
    _generate_html,
    _generate_scatter,
    _hull,
)

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
    return Point(name, x, y, "noun", scope, cluster, f"{name.lower()}.py")


def test_scatter_embeds_the_dendrogram_and_file_labels_for_the_slider():
    points = [point("Invoice", "billing", 0), point("Charge", "billing", 0)]
    scatter = _build_scatter(points, [], None, [[0, 1]])
    assert scatter["merges"] == [[0, 1]]
    assert scatter["points"][0]["file"] == "invoice.py"


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


def suggestion(name: str, *members: str) -> Suggestion:
    return Suggestion(name, f"**/{name}/**", members, 0.9, ("global",))


def test_scatter_has_no_proposed_boundaries_without_suggestions():
    points = [point("Widget", UNASSIGNED, 0), point("Gadget", UNASSIGNED, 0)]
    assert _build_scatter(points, [])["proposed"] == []


def test_scatter_draws_a_proposed_boundary_around_a_suggested_cluster():
    points = [
        point("Widget", UNASSIGNED, 0, 0.0, 0.0),
        point("Gadget", UNASSIGNED, 0, 4.0, 0.0),
        point("Sprocket", UNASSIGNED, 0, 2.0, 4.0),
    ]
    proposed = _build_scatter(points, [], [suggestion("hardware", "Widget", "Gadget", "Sprocket")])[
        "proposed"
    ]
    assert [region["name"] for region in proposed] == ["hardware"]
    assert len(proposed[0]["hull"]) >= 3


def test_scatter_ignores_a_suggestion_too_small_to_bound():
    points = [point("Widget", UNASSIGNED, 0, 0.0, 0.0), point("Gadget", UNASSIGNED, 0, 1.0, 0.0)]
    proposed = _build_scatter(points, [], [suggestion("hardware", "Widget", "Gadget")])["proposed"]
    assert proposed == []


def test_hull_pushes_the_boundary_out_past_the_members():
    members = [
        point("a", UNASSIGNED, 0, 0.0, 0.0),
        point("b", UNASSIGNED, 0, 2.0, 0.0),
        point("c", UNASSIGNED, 0, 1.0, 2.0),
    ]
    hull = _hull(members, 1.0)
    assert len(hull) >= 3
    xs = [x for x, _ in hull]
    assert min(xs) < 0.0 and max(xs) > 2.0


def test_hull_falls_back_to_a_box_for_collinear_members():
    members = [
        point("a", UNASSIGNED, 0, 0.0, 0.0),
        point("b", UNASSIGNED, 0, 1.0, 0.0),
        point("c", UNASSIGNED, 0, 2.0, 0.0),
    ]
    hull = _hull(members, 0.5)
    assert len(hull) == 4


def test_generate_scatter_embeds_the_proposed_colour_when_a_domain_is_suggested():
    points = [
        point("Widget", UNASSIGNED, 0, 0.0, 0.0),
        point("Gadget", UNASSIGNED, 0, 4.0, 0.0),
        point("Sprocket", UNASSIGNED, 0, 2.0, 4.0),
    ]
    html = _generate_scatter(points, [], [suggestion("hardware", "Widget", "Gadget", "Sprocket")])
    assert "__PROPOSED__" not in html
    assert '"name": "hardware"' in html or '"name":"hardware"' in html
