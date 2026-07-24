from pathlib import Path

import pytest

from dddlint.config import load_config

pytestmark = pytest.mark.unit


def test_load_config_parses_yaml(tmp_path: Path):
    path = tmp_path / "dddlint.yaml"
    path.write_text("forbidden: [manager]\nenforce_canonical: false\n")
    config = load_config(path)
    assert config.forbidden == ["manager"]
    assert config.enforce_canonical is False


def test_load_config_empty_file_uses_defaults(tmp_path: Path):
    path = tmp_path / "dddlint.yaml"
    path.write_text("")
    config = load_config(path)
    assert config.forbidden == []
    assert config.enforce_canonical is True
