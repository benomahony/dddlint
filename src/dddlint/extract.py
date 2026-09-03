from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tree_sitter_language_pack as tslp

DEFINITION_KINDS = frozenset(
    {"Function", "Method", "Class", "Struct", "Interface", "Enum", "Trait"}
)
SYMBOL_KINDS = frozenset({"Variable", "Constant"})
PATH_KINDS = frozenset({"Module", "Package"})


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    kind: str
    path: Path
    line: int
    col: int = 0
    doc: str | None = None


def _kind_name(kind: object) -> str:
    name = str(kind)
    assert name, "kind must stringify to a non-empty name"
    assert name.strip() == name, "kind name must not have surrounding whitespace"
    return name


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field whether tree-sitter-language-pack returns dataclass objects or plain dicts.

    The native build returns attribute-style ``ProcessResult`` objects, but the packaged type
    stub declares ``ProcessResult`` a ``TypedDict``, and some builds hand back dicts to match.
    The field names are the same either way, so one accessor spans both shapes.
    """
    assert name, "a field name is required to read"
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _start_line(item: Any) -> int:
    line = _field(_field(item, "span"), "start_line", 0)
    return line if isinstance(line, int) and line >= 0 else 0


def _flatten(
    items: Iterable[Any], path: Path, source_lines: list[str], out: list[Definition]
) -> None:
    assert isinstance(out, list), "out accumulator must be a list"
    assert isinstance(source_lines, list), "source_lines must be a list of source lines"
    stack: deque[Any] = deque(items)
    while stack:
        item = stack.popleft()
        name = _field(item, "name")
        kind = _kind_name(_field(item, "kind"))
        if name and kind in DEFINITION_KINDS:
            line = _start_line(item)
            line_text = source_lines[line] if line < len(source_lines) else ""
            col = line_text.find(name)
            out.append(Definition(name, kind, path, line, max(col, 0), _field(item, "doc_comment")))
        children = _field(item, "children") or []
        if children:
            stack.extendleft(reversed(list(children)))


def language_for(path: Path) -> str | None:
    assert path.name, "path must have a filename to detect a language"
    assert isinstance(path, Path), "path must be a Path object"
    return tslp.detect_language_from_path(str(path))


# tree-sitter-language-pack extracts classes and functions but not the module-level
# assignments where dynamic languages keep their vocabulary (Shopping = Lexicon(...)),
# so those are read straight from the parse tree. These are the node types that bind a
# name at module scope across common languages; the containers hold several at once.
_BINDING_CONTAINERS = frozenset(
    {
        "pattern_list",
        "tuple_pattern",
        "list_pattern",
        "expression_list",
        "tuple",
        "array_pattern",
        "object_pattern",
        "identifier_list",
    }
)
_BINDING_LEAVES = frozenset({"identifier", "constant"})


def _binding_targets(node: Any) -> list[Any]:
    """The left-hand side(s) of a module-level binding, whatever the language calls it."""
    kind = node.type
    if kind in {"assignment", "assignment_expression", "short_var_declaration"}:
        left = node.child_by_field_name("left")
        return [left] if left is not None else []
    if kind in {"variable_declaration", "lexical_declaration"}:
        return [
            d.child_by_field_name("name") for d in node.children if d.type == "variable_declarator"
        ]
    if kind in {"var_declaration", "const_declaration"}:
        return [s.child_by_field_name("name") for s in node.children if s.type.endswith("_spec")]
    if kind in {"let_declaration", "const_item", "static_item"}:
        return [node.child_by_field_name("pattern") or node.child_by_field_name("name")]
    return []


def _binding_names(target: Any) -> list[Any]:
    """The identifier nodes a target binds: a plain name, or several from a tuple pattern."""
    if target is None:
        return []
    if target.type in _BINDING_LEAVES:
        return [target]
    if target.type in _BINDING_CONTAINERS:
        return [ident for child in target.children for ident in _binding_names(child)]
    return []


def _module_bindings(
    source: str, language: str, path: Path, taken: set[tuple[str, int]]
) -> list[Definition]:
    assert language, "language must be non-empty to parse"
    try:
        tree = tslp.get_parser(language).parse(source.encode("utf-8", "ignore"))
    except Exception:  # noqa: BLE001 - an unparseable file simply yields no extra bindings
        return []
    out: list[Definition] = []
    for child in tree.root_node.children:
        statement = (
            child.children[0] if child.type == "expression_statement" and child.children else child
        )
        for target in _binding_targets(statement):
            for ident in _binding_names(target):
                name = ident.text.decode("utf-8", "ignore")
                line, col = ident.start_point[0], ident.start_point[1]
                dunder = name.startswith("__") and name.endswith("__")
                if name and not dunder and (name, line) not in taken:
                    taken.add((name, line))
                    out.append(Definition(name, "Constant", path, line, max(col, 0)))
    return out


def _package_anchor(folder: Path) -> Path:
    assert folder.name, "a package must have a directory name"
    assert not folder.is_file(), "a package must be a directory, not a file"
    init = folder / "__init__.py"
    return init if init.exists() else folder


def path_definitions(path: Path, root: Path) -> list[Definition]:
    """A package called utils names the domain as loudly as any class does."""
    assert path.is_file(), "path must be an existing file to name"
    assert root.is_dir(), "root must be an existing directory to walk up to"
    out = [Definition(path.stem, "Module", path, 0)]
    for parent in reversed(path.relative_to(root).parents):
        if parent.name:
            out.append(Definition(parent.name, "Package", _package_anchor(root / parent), 0))
    return out


def definitions(path: Path, language: str) -> list[Definition]:
    assert language, "language must be non-empty for the parser"
    assert path.exists(), "path must exist to read its source"
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
    _flatten(_field(result, "structure") or [], path, source_lines, out)
    for sym in _field(result, "symbols") or []:
        name = _field(sym, "name")
        kind = _kind_name(_field(sym, "kind"))
        if not name or kind not in SYMBOL_KINDS:
            continue
        line = _start_line(sym)
        line_text = source_lines[line] if line < len(source_lines) else ""
        col = line_text.find(name)
        out.append(Definition(name, kind, path, line, max(col, 0), _field(sym, "doc")))
    out.extend(_module_bindings(source, language, path, {(d.name, d.line) for d in out}))
    return out
