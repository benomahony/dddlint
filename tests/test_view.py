import json

import pytest

from dddlint.config import Config, Context, SynonymGroup
from dddlint.view import _build_graph, _generate_html

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
