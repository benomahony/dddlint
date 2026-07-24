from pathlib import Path

import yaml
from pydantic import BaseModel


class SynonymGroup(BaseModel):
    canonical: str
    aliases: list[str] = []


class LanguageDef(BaseModel):
    extensions: list[str] = []


class Context(BaseModel):
    name: str
    include: list[str]
    forbidden: list[str] = []
    synonyms: list[SynonymGroup] = []


class Config(BaseModel):
    similarity_threshold: float = 0.85
    enforce_canonical: bool = True
    forbidden: list[str] = []
    exclude: list[str] = []
    synonyms: list[SynonymGroup] = []
    domains: list[Context] = []
    contexts: list[Context] = []
    languages: dict[str, LanguageDef] = {}

    def extension_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, spec in self.languages.items():
            for ext in spec.extensions:
                assert ext.startswith("."), f"extension '{ext}' must start with '.'"
                out[ext] = name
        assert all(out.values()), "every extension must map to a non-empty language name"
        return out


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text()) or {}
    assert isinstance(data, dict), "config root must be a YAML mapping, not a list or scalar"
    assert data.get("similarity_threshold", 1.0) >= 0.0, "similarity_threshold must be non-negative"
    return Config.model_validate(data)
