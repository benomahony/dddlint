from collections.abc import Iterator
from pathlib import Path

import pathspec

SKIP = {".git", ".venv", "node_modules", "__pycache__", "target", "dist", "build"}


def _ignore_spec(root: Path, exclude: list[str]) -> pathspec.PathSpec:
    assert all(isinstance(p, str) for p in exclude), "exclude patterns must be strings"
    lines = list(exclude)
    gitignore = root / ".gitignore"
    if gitignore.exists():
        lines += gitignore.read_text().splitlines()
    spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
    assert isinstance(spec, pathspec.PathSpec), "must build a valid PathSpec"
    return spec


def source_files(root: Path, exclude: list[str]) -> Iterator[Path]:
    assert root.is_dir(), "root must be an existing directory to walk"
    assert all(isinstance(p, str) for p in exclude), "exclude patterns must be strings"
    spec = _ignore_spec(root, exclude)
    for path in root.rglob("*"):
        if not path.is_file() or SKIP & set(path.parts):
            continue
        if spec.match_file(str(path.relative_to(root))):
            continue
        yield path
