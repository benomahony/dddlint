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
    synonyms: list[SynonymGroup] = []
    domains: list[Context] = []
    contexts: list[Context] = []
    languages: dict[str, LanguageDef] = {}

    def extension_map(self) -> dict[str, str]:
        assert isinstance(self.languages, dict), "languages must be a mapping"
        out: dict[str, str] = {}
        for name, spec in self.languages.items():
            for ext in spec.extensions:
                assert ext.startswith("."), f"extension '{ext}' must start with '.'"
                out[ext] = name
        return out


def load_config(path: Path) -> Config:
    assert path is not None, "path must not be None"
    assert isinstance(path, Path), "path must be a Path object"
    return Config.model_validate(yaml.safe_load(path.read_text()) or {})
