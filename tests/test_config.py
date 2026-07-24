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


def test_config_extension_map_registers_custom_languages(tmp_path: Path):
    path = tmp_path / "dddlint.yaml"
    path.write_text("languages:\n  svelte:\n    extensions: ['.svelte', '.svlt']\n")
    config = load_config(path)
    assert config.extension_map() == {".svelte": "svelte", ".svlt": "svelte"}


def test_config_extension_map_empty_by_default():
    from dddlint.config import Config

    assert Config().extension_map() == {}


def test_load_config_rejects_non_mapping_root(tmp_path: Path):
    path = tmp_path / "dddlint.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(AssertionError, match="YAML mapping"):
        load_config(path)
