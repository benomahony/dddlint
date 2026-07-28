from pathlib import Path

import pytest

from dddlint.discover import source_files

pytestmark = pytest.mark.unit


def test_source_files_skips_builtin_dirs(tmp_path: Path):
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("y = 2\n")
    found = {p.name for p in source_files(tmp_path, [])}
    assert found == {"keep.py"}


def test_source_files_respects_gitignore(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("htmlcov/\n*.min.js\n")
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "bundle.min.js").write_text("y = 2\n")
    (tmp_path / "htmlcov").mkdir()
    (tmp_path / "htmlcov" / "index.py").write_text("z = 3\n")
    found = {p.name for p in source_files(tmp_path, [])}
    assert "keep.py" in found
    assert "bundle.min.js" not in found
    assert "index.py" not in found


def test_source_files_respects_extra_excludes(tmp_path: Path):
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "gen.py").write_text("y = 2\n")
    found = {p.name for p in source_files(tmp_path, ["gen.py"])}
    assert found == {"keep.py"}


def test_source_files_anchors_patterns_to_base(tmp_path: Path):
    (tmp_path / "src" / "gen").mkdir(parents=True)
    (tmp_path / "src" / "keep.py").write_text("x = 1\n")
    (tmp_path / "src" / "gen" / "skip.py").write_text("y = 2\n")
    (tmp_path / ".gitignore").write_text("src/vendored.py\n")
    (tmp_path / "src" / "vendored.py").write_text("z = 3\n")
    found = {p.name for p in source_files(tmp_path / "src", ["src/gen"], tmp_path)}
    assert found == {"keep.py"}


def test_source_files_ignores_a_base_that_does_not_contain_root(tmp_path: Path):
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "gen.py").write_text("y = 2\n")
    found = {p.name for p in source_files(tmp_path, ["gen.py"], tmp_path.parent / "elsewhere")}
    assert found == {"keep.py"}
