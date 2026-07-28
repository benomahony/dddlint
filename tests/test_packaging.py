import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"


def _wheel(out: Path) -> Path:
    assert out.is_dir(), "the wheel needs an existing directory to build into"
    build = subprocess.run(
        ["uv", "build", "--wheel", "--project", str(ROOT), "--out-dir", str(out)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheels = list(out.glob("dddlint-*.whl"))
    assert len(wheels) == 1, f"exactly one wheel must be built, got {wheels}"
    return wheels[0]


def _run(wheel: Path, *args: str) -> subprocess.CompletedProcess[str]:
    assert wheel.suffix == ".whl", "the CLI must run from a built wheel"
    assert args, "the CLI needs a command to run"
    return subprocess.run(
        ["uv", "run", "--isolated", "--no-project", "--with", str(wheel), "--", "dddlint", *args],
        capture_output=True,
        text=True,
    )


def test_a_plain_install_lints_without_the_embed_extras(tmp_path: Path):
    wheel = _wheel(tmp_path)
    version = _run(wheel, "--version")
    assert version.returncode == 0, version.stderr
    lint = _run(wheel, "lint", str(EXAMPLES), "--config", str(EXAMPLES / "dddlint.yaml"))
    assert lint.returncode == 1, lint.stderr
    assert "findings" in lint.stdout, lint.stdout


def test_a_plain_install_maps_by_naming_the_extra_to_install(tmp_path: Path):
    wheel = _wheel(tmp_path)
    result = _run(wheel, "map", str(EXAMPLES), "--config", str(EXAMPLES / "dddlint.yaml"))
    assert result.returncode == 2, result.stderr
    assert "dddlint[embed-local]" in result.stdout, result.stdout
