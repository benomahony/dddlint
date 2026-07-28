from pathlib import Path

import pytest

from dddlint.config import Config, load_config

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


def test_load_config_rejects_non_mapping_root(tmp_path: Path):
    path = tmp_path / "dddlint.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(AssertionError, match="YAML mapping"):
        load_config(path)


def test_embeddings_defaults():
    config = Config()
    assert config.embeddings.model.startswith("sentence-transformers:")
    assert config.embeddings.threshold is None


def test_embeddings_overrides(tmp_path: Path):
    path = tmp_path / "dddlint.yaml"
    path.write_text("embeddings:\n  model: openai:text-embedding-3-small\n  threshold: 0.7\n")
    config = load_config(path)
    assert config.embeddings.model == "openai:text-embedding-3-small"
    assert config.embeddings.threshold == 0.7
