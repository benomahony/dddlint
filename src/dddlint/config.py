from pathlib import Path

import yaml
from pydantic import BaseModel


class SynonymGroup(BaseModel):
    canonical: str
    aliases: list[str] = []


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


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text()) or {}
    assert isinstance(data, dict), "config root must be a YAML mapping, not a list or scalar"
    assert data.get("similarity_threshold", 1.0) >= 0.0, "similarity_threshold must be non-negative"
    return Config.model_validate(data)
