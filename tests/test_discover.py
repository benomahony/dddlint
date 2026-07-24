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
