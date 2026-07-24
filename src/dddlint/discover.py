from collections.abc import Iterator
from pathlib import Path

import pathspec

SKIP = {".git", ".venv", "node_modules", "__pycache__", "target", "dist", "build"}


def _ignore_spec(root: Path, exclude: list[str]) -> pathspec.PathSpec:
    assert isinstance(root, Path), "root must be a Path object"
    assert isinstance(exclude, list), "exclude must be a list"
    lines = list(exclude)
    gitignore = root / ".gitignore"
    if gitignore.exists():
        lines += gitignore.read_text().splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def source_files(root: Path, exclude: list[str]) -> Iterator[Path]:
    assert isinstance(root, Path), "root must be a Path object"
    assert isinstance(exclude, list), "exclude must be a list"
    spec = _ignore_spec(root, exclude)
    for path in root.rglob("*"):
        if not path.is_file() or SKIP & set(path.parts):
            continue
        if spec.match_file(str(path.relative_to(root))):
            continue
        yield path
