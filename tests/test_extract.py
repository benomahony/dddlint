from pathlib import Path

import pytest

from dddlint.extract import definitions, language_for

pytestmark = pytest.mark.unit


def test_language_for_prefers_extra_override(tmp_path: Path):
    path = tmp_path / "x.weird"
    assert language_for(path, {".weird": "python"}) == "python"


def test_language_for_detects_from_suffix(tmp_path: Path):
    assert language_for(tmp_path / "x.py", {}) == "python"


def test_language_for_unknown_suffix_returns_none(tmp_path: Path):
    assert language_for(tmp_path / "x.unknownext", {}) is None


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
