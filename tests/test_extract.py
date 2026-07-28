from dataclasses import dataclass, field
from pathlib import Path

import pytest

from dddlint.extract import _flatten, definitions, language_for, path_definitions

pytestmark = pytest.mark.unit


@dataclass
class _Span:
    start_line: int = 0


@dataclass
class _Node:
    name: str
    kind: str = "Class"
    doc_comment: str | None = None
    span: _Span = field(default_factory=_Span)
    children: list["_Node"] = field(default_factory=list)


def test_flatten_preorder_depth_first():
    tree = [
        _Node("A", children=[_Node("A1"), _Node("A2")]),
        _Node("B"),
    ]
    out: list = []
    _flatten(tree, Path("x.py"), [], out)
    assert [d.name for d in out] == ["A", "A1", "A2", "B"]


def test_language_for_detects_from_suffix(tmp_path: Path):
    assert language_for(tmp_path / "x.py") == "python"


def test_language_for_unknown_suffix_returns_none(tmp_path: Path):
    assert language_for(tmp_path / "x.unknownext") is None


def test_definitions_extracts_nested_defs(tmp_path: Path):
    src = tmp_path / "m.py"
    src.write_text("class Repo:\n    def find(self):\n        return 1\n")
    defs = definitions(src, "python")
    kinds = {(d.kind, d.name) for d in defs}
    assert ("Class", "Repo") in kinds
    assert ("Method", "find") in kinds or ("Function", "find") in kinds


def test_definitions_records_column_of_name(tmp_path: Path):
    src = tmp_path / "m.py"
    src.write_text("class Repo:\n    pass\n")
    repo = next(d for d in definitions(src, "python") if d.name == "Repo")
    assert repo.col == "class Repo:".index("Repo")
    assert repo.line == 0


def test_definitions_captures_constant_symbols(tmp_path: Path):
    src = tmp_path / "m.rs"
    src.write_text("const MAX: i32 = 5;\n")
    names = {d.name for d in definitions(src, "rust")}
    assert "MAX" in names


def test_path_definitions_name_every_directory_and_the_module(tmp_path: Path):
    src = tmp_path / "commons" / "utils" / "file_utils.py"
    src.parent.mkdir(parents=True)
    src.write_text("")
    named = path_definitions(src, tmp_path)
    assert [(d.name, d.kind) for d in named] == [
        ("file_utils", "Module"),
        ("commons", "Package"),
        ("utils", "Package"),
    ]
    assert all(d.line == 0 for d in named)


def test_path_definitions_anchor_a_package_at_its_init(tmp_path: Path):
    src = tmp_path / "utils" / "m.py"
    src.parent.mkdir()
    src.write_text("")
    (src.parent / "__init__.py").write_text("")
    package = next(d for d in path_definitions(src, tmp_path) if d.kind == "Package")
    assert package.path == tmp_path / "utils" / "__init__.py"
