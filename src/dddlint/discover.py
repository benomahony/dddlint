from collections.abc import Iterator
from pathlib import Path

import pathspec

SKIP = {".git", ".venv", "node_modules", "__pycache__", "target", "dist", "build"}


def _ignore_spec(base: Path, exclude: list[str]) -> pathspec.PathSpec:
    assert base.is_dir(), "base must be an existing directory"
    assert all(isinstance(p, str) for p in exclude), "exclude patterns must be strings"
    lines = list(exclude)
    gitignore = base / ".gitignore"
    if gitignore.exists():
        lines += gitignore.read_text().splitlines()
    spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
    assert isinstance(spec, pathspec.PathSpec), "must build a valid PathSpec"
    return spec


def _anchor(root: Path, base: Path | None) -> Path:
    assert root.is_dir(), "root must be an existing directory"
    assert base is None or isinstance(base, Path), "base must be a Path when given"
    resolved = root.resolve()
    if base is None:
        return resolved
    candidate = base.resolve()
    return candidate if resolved.is_relative_to(candidate) else resolved


def source_files(root: Path, exclude: list[str], base: Path | None = None) -> Iterator[Path]:
    assert root.is_dir(), "root must be an existing directory to walk"
    assert all(isinstance(p, str) for p in exclude), "exclude patterns must be strings"
    anchor = _anchor(root, base)
    spec = _ignore_spec(anchor, exclude)
    prefix = root.resolve().relative_to(anchor)
    for path in root.rglob("*"):
        if not path.is_file() or SKIP & set(path.parts):
            continue
        if spec.match_file(str(prefix / path.relative_to(root))):
            continue
        yield path
