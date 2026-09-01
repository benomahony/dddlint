import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from dddlint import __version__
from dddlint.cli import _backend_missing, _print_backend_missing, _resolve, app
from dddlint.config import Embeddings, load_config

pytestmark = pytest.mark.unit

runner = CliRunner()
EXAMPLES = Path(__file__).parent.parent / "examples"


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_starting_the_cli_does_not_import_numpy():
    probe = "import sys, dddlint.cli; sys.exit('numpy' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert not result.stderr, result.stderr
    assert result.returncode == 0, "numpy is an extra, so importing the CLI must not need it"


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


def test_lint_reports_a_forbidden_term_in_a_package_name(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("forbidden: [utils]\n")
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "file_utils.py").write_text("class Customer:\n    pass\n")
    result = runner.invoke(app, ["lint", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert result.exit_code == 1
    assert "forbidden:module" in result.stdout
    assert "2 findings" in result.stdout


def test_lint_names_one_shared_package_once(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("forbidden: [helpers]\n")
    (tmp_path / "helpers").mkdir()
    (tmp_path / "helpers" / "one.py").write_text("class Customer:\n    pass\n")
    (tmp_path / "helpers" / "two.py").write_text("class Order:\n    pass\n")
    result = runner.invoke(app, ["lint", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert "1 finding\n" in result.stdout


def test_resolve_defaults_to_cwd_and_default_config(tmp_path: Path):
    root, config = _resolve(None, None)
    assert root == Path.cwd()
    assert config.name == "dddlint.yaml"


def test_resolve_falls_back_to_cwd_config_when_missing(tmp_path: Path):
    root, config = _resolve(tmp_path, None)
    assert root == tmp_path
    assert config.name == "dddlint.yaml"


def test_missing_config_says_so_without_a_traceback(tmp_path: Path):
    (tmp_path / "a.py").write_text("class Customer:\n    pass\n")
    result = runner.invoke(app, ["lint", str(tmp_path), "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 2
    assert "no config found" in result.stdout
    assert "dddlint init" in result.stdout
    assert "Traceback" not in result.stdout


def test_init_writes_a_starter_config(tmp_path: Path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    written = (tmp_path / "dddlint.yaml").read_text()
    assert "forbidden:" in written
    assert load_config(tmp_path / "dddlint.yaml").name_uniqueness is True


def test_init_refuses_to_overwrite(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("forbidden: [mine]\n")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 1
    assert (tmp_path / "dddlint.yaml").read_text() == "forbidden: [mine]\n"


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
    result = runner.invoke(
        app,
        ["map", str(root), "--config", str(root / "dddlint.yaml")],
        env={"BROWSER": "true"},
    )
    assert result.exit_code == 0
    assert "4 names" in result.stdout
    assert "near-synonym" in result.stdout


def test_map_on_an_empty_tree_says_so(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("")
    result = runner.invoke(app, ["map", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "no definitions" in result.stdout


def test_map_writes_dddmap_beside_the_config_and_opens_it(tmp_path: Path):
    root = _repo_with_warm_cache(tmp_path)
    result = runner.invoke(
        app,
        ["map", str(root), "--config", str(root / "dddlint.yaml")],
        env={"BROWSER": "true"},
    )
    assert result.exit_code == 0
    target = root / "dddmap.html"
    assert "dddmap.html" in result.stdout
    page = target.read_text()
    assert page.startswith("<!DOCTYPE html>")
    assert "__DATA__" not in page
    assert "retrieve_purchase" in page


def test_map_of_a_subdirectory_finds_the_cache_beside_the_config(tmp_path: Path):
    root = _repo_with_warm_cache(tmp_path)
    result = runner.invoke(
        app,
        ["map", str(root / "src"), "--config", str(root / "dddlint.yaml")],
        env={"BROWSER": "true"},
    )
    assert result.exit_code == 0
    assert "4 names" in result.stdout


DISCOVER_NAMES = {
    "Invoice": [1.0, 0.0],
    "Charge": [0.999, 0.045],
    "Ledger": [0.998, 0.06],
    "Parcel": [0.0, 1.0],
    "Dispatch": [0.2, 0.98],
    "Courier": [0.28, 0.96],
}


def _repo_for_discover(tmp_path: Path) -> Path:
    (tmp_path / "dddlint.yaml").write_text("embeddings:\n  threshold: 0.9\n")
    (tmp_path / "src/billing").mkdir(parents=True)
    (tmp_path / "src/shipping").mkdir(parents=True)
    (tmp_path / "src/billing/a.py").write_text(
        "class Invoice: ...\nclass Charge: ...\nclass Ledger: ...\n"
    )
    (tmp_path / "src/shipping/b.py").write_text(
        "class Parcel: ...\nclass Dispatch: ...\nclass Courier: ...\n"
    )
    cache = tmp_path / ".dddlint/embeddings.json"
    cache.parent.mkdir()
    key = f"{Embeddings().model}/native"
    cache.write_text(json.dumps({"key": key, "vectors": DISCOVER_NAMES}))
    return tmp_path


def test_discover_suggests_the_strongest_domain_and_prints_yaml(tmp_path: Path):
    root = _repo_for_discover(tmp_path)
    result = runner.invoke(app, ["discover", str(root), "--config", str(root / "dddlint.yaml")])
    assert result.exit_code == 0
    assert "billing" in result.stdout
    assert "**/billing/**" in result.stdout
    assert "domains:" in result.stdout


def test_discover_all_with_limit_lists_every_cluster(tmp_path: Path):
    root = _repo_for_discover(tmp_path)
    result = runner.invoke(
        app,
        ["discover", str(root), "--all", "--limit", "0", "--config", str(root / "dddlint.yaml")],
    )
    assert result.exit_code == 0
    assert "billing" in result.stdout and "shipping" in result.stdout


def test_scope_note_flags_a_cluster_that_straddles_two_domains():
    from dddlint.cli import _scope_note

    assert "overlap" in _scope_note(("billing", "shipping"))
    assert _scope_note(("billing", "global")) == "extends billing into unassigned code"
    assert _scope_note(("global",)) == "new domain in unassigned code"


def test_discover_on_an_empty_tree_says_so(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("")
    result = runner.invoke(
        app, ["discover", str(tmp_path), "--config", str(tmp_path / "dddlint.yaml")]
    )
    assert result.exit_code == 0
    assert "no definitions" in result.stdout


def test_missing_backend_message_names_the_extra_to_install():
    local = _backend_missing("sentence-transformers:all-MiniLM-L6-v2", ImportError("no torch"))
    assert "dddlint[embed-local]" in local
    assert "no torch" in local
    remote = _backend_missing("openai:text-embedding-3-small", ImportError("no httpx"))
    assert "dddlint[embed]" in remote


def test_missing_backend_message_keeps_the_extra_through_rich():
    output = StringIO()
    _print_backend_missing(
        Console(file=output, width=200),
        "sentence-transformers:all-MiniLM-L6-v2",
        ImportError("no torch"),
    )
    assert "dddlint[embed-local]" in output.getvalue()
