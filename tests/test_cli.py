from pathlib import Path

import pytest
from typer.testing import CliRunner

from dddlint import __version__
from dddlint.cli import _resolve, app

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


def test_lint_uses_custom_language_extension(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text(
        "forbidden: [manager]\nlanguages:\n  python:\n    extensions: ['.txt']\n"
    )
    (tmp_path / "code.txt").write_text("class OrderManager:\n    pass\n")
    result = runner.invoke(app, ["lint", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert result.exit_code == 1
    assert "forbidden" in result.stdout


def test_resolve_defaults_to_cwd_and_default_config(tmp_path: Path):
    root, config = _resolve(None, None)
    assert root == Path.cwd()
    assert config.name == "dddlint.yaml"


def test_resolve_falls_back_to_cwd_config_when_missing(tmp_path: Path):
    root, config = _resolve(tmp_path, None)
    assert root == tmp_path
    assert config.name == "dddlint.yaml"


def test_html_writes_and_opens_graph(tmp_path: Path):
    result = runner.invoke(
        app,
        ["html", str(EXAMPLES), "--config", str(EXAMPLES / "dddlint.yaml")],
        env={"BROWSER": "true"},
    )
    assert result.exit_code == 0
