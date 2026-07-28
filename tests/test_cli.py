import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dddlint import __version__
from dddlint.cli import _resolve, app
from dddlint.config import Embeddings

pytestmark = pytest.mark.unit

runner = CliRunner()
EXAMPLES = Path(__file__).parent.parent / "examples"


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_lint_reports_findings_and_exits_nonzero():
    result = runner.invoke(app, ["lint", str(EXAMPLES), "--config", str(EXAMPLES / "dddlint.yaml")])
    assert result.exit_code == 1
    assert "finding" in result.stdout


def test_lint_clean_project_exits_zero(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("")
    (tmp_path / "clean.py").write_text("class Customer:\n    pass\n")
    (tmp_path / "notes.unknownext").write_text("skipped\n")
    result = runner.invoke(app, ["lint", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "no findings" in result.stdout


def test_lint_skips_gitignored_files(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("forbidden: [manager]\n")
    (tmp_path / ".gitignore").write_text("generated/\n")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "bad.py").write_text("class OrderManager:\n    pass\n")
    result = runner.invoke(app, ["lint", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "no findings" in result.stdout


def test_lint_of_a_subdirectory_honours_root_config_excludes(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text('forbidden: [manager]\nexclude: ["src/gen"]\n')
    (tmp_path / "src" / "gen").mkdir(parents=True)
    (tmp_path / "src" / "gen" / "bad.py").write_text("class OrderManager:\n    pass\n")
    result = runner.invoke(
        app, ["lint", str(tmp_path / "src"), "--config", str(tmp_path / "dddlint.yaml")]
    )
    assert result.exit_code == 0
    assert "no findings" in result.stdout


def test_resolve_defaults_to_cwd_and_default_config(tmp_path: Path):
    root, config = _resolve(None, None)
    assert root == Path.cwd()
    assert config.name == "dddlint.yaml"


def test_resolve_falls_back_to_cwd_config_when_missing(tmp_path: Path):
    root, config = _resolve(tmp_path, None)
    assert root == tmp_path
    assert config.name == "dddlint.yaml"


def test_html_reuses_single_temp_file():
    from dddlint.cli import _write_temp_html

    p1 = _write_temp_html("<html>1</html>")
    p2 = _write_temp_html("<html>2</html>")
    assert p1 == p2
    assert Path(p2).read_text() == "<html>2</html>"


def test_html_writes_and_opens_graph(tmp_path: Path):
    result = runner.invoke(
        app,
        ["html", str(EXAMPLES), "--config", str(EXAMPLES / "dddlint.yaml")],
        env={"BROWSER": "true"},
    )
    assert result.exit_code == 0


CACHED_NAMES = {
    "Invoice": [1.0, 0.0],
    "charge": [0.99, 0.14],
    "fetch_order": [0.0, 1.0],
    "retrieve_purchase": [0.05, 0.99],
}


def _repo_with_warm_cache(tmp_path: Path) -> Path:
    (tmp_path / "dddlint.yaml").write_text(
        "contexts:\n"
        "  - name: billing\n    include: ['**/billing/**']\n"
        "  - name: core\n    include: ['**/core/**']\n"
    )
    (tmp_path / "src/billing").mkdir(parents=True)
    (tmp_path / "src/core").mkdir(parents=True)
    (tmp_path / "src/billing/a.py").write_text(
        "class Invoice:\n    def charge(self) -> None: ...\n"
    )
    (tmp_path / "src/core/b.py").write_text(
        "def fetch_order() -> None: ...\ndef retrieve_purchase() -> None: ...\n"
    )
    cache = tmp_path / ".dddlint/embeddings.json"
    cache.parent.mkdir()
    key = f"{Embeddings().model}/native"
    cache.write_text(json.dumps({"key": key, "vectors": CACHED_NAMES}))
    return tmp_path


def test_map_reports_insights_from_the_cached_vectors(tmp_path: Path):
    root = _repo_with_warm_cache(tmp_path)
    result = runner.invoke(app, ["map", str(root), "--config", str(root / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "4 names" in result.stdout
    assert "near-synonym" in result.stdout


def test_map_on_an_empty_tree_says_so(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("")
    result = runner.invoke(app, ["map", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "no definitions" in result.stdout


def test_map_writes_the_scatter_when_asked(tmp_path: Path):
    root = _repo_with_warm_cache(tmp_path)
    target = tmp_path / "map.html"
    result = runner.invoke(
        app,
        ["map", str(root), "--config", str(root / "dddlint.yaml"), "--html", str(target)],
    )
    assert result.exit_code == 0
    page = target.read_text()
    assert page.startswith("<!DOCTYPE html>")
    assert "__DATA__" not in page
    assert "retrieve_purchase" in page


def test_map_of_a_subdirectory_finds_the_cache_beside_the_config(tmp_path: Path):
    root = _repo_with_warm_cache(tmp_path)
    result = runner.invoke(app, ["map", str(root / "src"), "--config", str(root / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "4 names" in result.stdout
