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


class LanguageOverride(BaseModel):
    extensions: list[str] = []


class Config(BaseModel):
    similarity_threshold: float = 0.85
    enforce_canonical: bool = True
    forbidden: list[str] = []
    synonyms: list[SynonymGroup] = []
    domains: list[Context] = []
    contexts: list[Context] = []
    languages: dict[str, LanguageOverride] = {}


def load_config(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()) or {})
