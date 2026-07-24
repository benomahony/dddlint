from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tree_sitter_language_pack as tslp

DEFINITION_KINDS = frozenset(
    {"Function", "Method", "Class", "Struct", "Interface", "Enum", "Trait"}
)
SYMBOL_KINDS = frozenset({"Variable", "Constant"})


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    kind: str
    path: Path
    line: int
    col: int = 0
    doc: str | None = None


def _kind_name(kind: object) -> str:
    assert kind is not None, "kind must not be None"
    name = str(kind)
    assert name, "kind name must be non-empty"
    return name


def _flatten(
    items: Iterable[Any], path: Path, source_lines: list[str], out: list[Definition]
) -> None:
    assert path is not None, "path must not be None"
    assert isinstance(out, list), "out must be a list"
    stack: list[Any] = list(items)
    while stack:
        item = stack.pop(0)
        kind = _kind_name(item.kind)
        if item.name and kind in DEFINITION_KINDS:
            line = item.span.start_line
            line_text = source_lines[line] if line < len(source_lines) else ""
            col = line_text.find(item.name)
            out.append(Definition(item.name, kind, path, line, max(col, 0), item.doc_comment))
        if item.children:
            stack[:0] = list(item.children)


def language_for(path: Path, extra: dict[str, str]) -> str | None:
    assert isinstance(path, Path), "path must be a Path object"
    assert extra is not None, "extra must not be None"
    return extra.get(path.suffix) or tslp.detect_language_from_path(str(path))


def definitions(path: Path, language: str) -> list[Definition]:
    assert isinstance(path, Path), "path must be a Path object"
    assert language, "language must be non-empty"
    source = path.read_text(errors="ignore")
    config = tslp.ProcessConfig(
        language=language,
        structure=True,
        symbols=True,
        imports=False,
        exports=False,
        comments=False,
        docstrings=True,
        diagnostics=False,
        chunk_max_size=None,
    )
    result = tslp.process(source, config)
    source_lines = source.splitlines()
    out: list[Definition] = []
    _flatten(result.structure, path, source_lines, out)
    for sym in result.symbols:
        kind = _kind_name(sym.kind)
        if kind not in SYMBOL_KINDS:
            continue
        line = sym.span.start_line
        line_text = source_lines[line] if line < len(source_lines) else ""
        col = line_text.find(sym.name)
        out.append(Definition(sym.name, kind, path, line, max(col, 0), sym.doc))
    return out
