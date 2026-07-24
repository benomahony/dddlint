import logging
from pathlib import Path
from urllib.parse import urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .check import Finding, check
from .config import Config, load_config
from .config_check import check_config
from .extract import Definition, definitions, language_for

logger = logging.getLogger(__name__)

SKIP = {".git", ".venv", "node_modules", "__pycache__", "target", "dist", "build"}
DEFAULT_CONFIG = Path("dddlint.yaml")

SEVERITY: dict[str, types.DiagnosticSeverity] = {
    "forbidden": types.DiagnosticSeverity.Error,
    "alias": types.DiagnosticSeverity.Warning,
    "drift": types.DiagnosticSeverity.Information,
}


class DddlintServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("dddlint", "v0.1.0")
        self.ddd_findings: dict[str, list[Finding]] = {}
        assert isinstance(self.ddd_findings, dict), "findings must be a dict"
        assert self.ddd_findings == {}, "findings must start empty"


server = DddlintServer()


def _to_path(uri: str) -> Path:
    assert uri, "uri must be non-empty"
    assert isinstance(uri, str), "uri must be a string"
    return Path(urlparse(uri).path)


def _scan(ls: DddlintServer) -> None:
    assert ls is not None, "language server must not be None"
    assert isinstance(ls, DddlintServer), "ls must be a DddlintServer"
    root_uri = ls.workspace.root_uri
    if not root_uri:
        return
    root = _to_path(root_uri)
    config_path = root / DEFAULT_CONFIG
    settings = load_config(config_path) if config_path.exists() else Config()

    extra = settings.extension_map()
    collected: list[Definition] = []
    for path in root.rglob("*"):
        if not path.is_file() or SKIP & set(path.parts):
            continue
        lang = language_for(path, extra)
        if lang is None:
            continue
        try:
            collected.extend(definitions(path, lang))
        except Exception as exc:
            logger.debug("failed to extract definitions from %s: %s", path, exc)

    all_findings: list[Finding] = []
    if config_path.exists():
        all_findings += check_config(settings, config_path)
    all_findings += check(collected, settings)
    by_file: dict[Path, list[Finding]] = {}
    for f in all_findings:
        by_file.setdefault(f.path, []).append(f)

    published: set[str] = set()
    for path, file_findings in by_file.items():
        uri = path.absolute().as_uri()
        ls.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(
                uri=uri, diagnostics=[_to_diagnostic(f) for f in file_findings]
            )
        )
        ls.ddd_findings[uri] = file_findings
        published.add(uri)

    for uri in list(ls.ddd_findings):
        if uri not in published:
            ls.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(uri=uri, diagnostics=[])
            )
            del ls.ddd_findings[uri]


def _to_diagnostic(f: Finding) -> types.Diagnostic:
    assert f is not None, "finding must not be None"
    assert f.line >= 0, "line must be non-negative"
    start = types.Position(line=f.line, character=f.col)
    end = types.Position(line=f.line, character=f.col + len(f.name))
    return types.Diagnostic(
        range=types.Range(start=start, end=end),
        message=f.message,
        severity=SEVERITY.get(f.rule, types.DiagnosticSeverity.Warning),
        source="dddlint",
        code=f.rule,
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: DddlintServer, params: types.DidOpenTextDocumentParams) -> None:
    assert ls is not None, "ls must not be None"
    assert params is not None, "params must not be None"
    _scan(ls)


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: DddlintServer, params: types.DidSaveTextDocumentParams) -> None:
    assert ls is not None, "ls must not be None"
    assert params is not None, "params must not be None"
    _scan(ls)


@server.feature(
    types.TEXT_DOCUMENT_CODE_ACTION,
    types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
)
def code_action(ls: DddlintServer, params: types.CodeActionParams) -> list[types.CodeAction]:
    assert ls is not None, "ls must not be None"
    assert params is not None, "params must not be None"
    uri = params.text_document.uri
    cursor_line = params.range.start.line
    actions: list[types.CodeAction] = []

    for f in ls.ddd_findings.get(uri, []):
        if f.line != cursor_line or f.fix is None:
            continue
        actions.append(
            types.CodeAction(
                title=f"Rename '{f.name}' → '{f.fix}' (dddlint: {f.rule})",
                kind=types.CodeActionKind.QuickFix,
                edit=types.WorkspaceEdit(
                    changes={
                        uri: [
                            types.TextEdit(
                                range=types.Range(
                                    start=types.Position(line=f.line, character=f.col),
                                    end=types.Position(line=f.line, character=f.col + len(f.name)),
                                ),
                                new_text=f.fix,
                            )
                        ]
                    }
                ),
            )
        )
    return actions


def main() -> None:
    assert server is not None, "server must be initialized"
    assert isinstance(server, DddlintServer), "server must be a DddlintServer"
    server.start_io()
