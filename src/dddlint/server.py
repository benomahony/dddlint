import logging
from pathlib import Path

from lsprotocol import types
from pygls import uris
from pygls.lsp.server import LanguageServer

from . import __version__
from .check import Finding, check
from .config import Config, load_config
from .config_check import check_config
from .discover import source_files
from .extract import Definition, definitions, language_for

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path("dddlint.yaml")

RENAME_COMMAND = "dddlint.rename"

SEVERITY: dict[str, types.DiagnosticSeverity] = {
    "forbidden": types.DiagnosticSeverity.Error,
    "alias": types.DiagnosticSeverity.Warning,
    "drift": types.DiagnosticSeverity.Information,
}


class DddlintServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("dddlint", __version__)
        self.ddd_findings: dict[str, list[Finding]] = {}
        assert self.name == "dddlint", "server name must match the package"
        assert self.version == __version__, "server version must match package version"


server = DddlintServer()


def _to_path(uri: str) -> Path:
    assert uri, "uri must be non-empty"
    assert uri.startswith("file:"), "uri must be a file:// URI"
    fs_path = uris.to_fs_path(uri)
    assert fs_path, "uri must resolve to a filesystem path"
    return Path(fs_path)


def _scan(ls: DddlintServer) -> None:
    assert isinstance(ls.ddd_findings, dict), "server must expose a findings cache"
    assert ls.workspace is not None, "server must have a workspace to scan"
    root_uri = ls.workspace.root_uri
    if not root_uri:
        return
    root = _to_path(root_uri)
    config_path = root / DEFAULT_CONFIG
    settings = load_config(config_path) if config_path.exists() else Config()

    collected: list[Definition] = []
    for path in source_files(root, settings.exclude):
        lang = language_for(path)
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
    assert f.line >= 0, "finding line must be non-negative"
    assert f.col >= 0, "finding column must be non-negative"
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
    assert isinstance(ls, DddlintServer), "handler must receive a DddlintServer"
    assert isinstance(params, types.DidOpenTextDocumentParams), "wrong event params type"
    _scan(ls)


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: DddlintServer, params: types.DidSaveTextDocumentParams) -> None:
    assert isinstance(ls, DddlintServer), "handler must receive a DddlintServer"
    assert isinstance(params, types.DidSaveTextDocumentParams), "wrong event params type"
    _scan(ls)


@server.feature(
    types.TEXT_DOCUMENT_CODE_ACTION,
    types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
)
def code_action(ls: DddlintServer, params: types.CodeActionParams) -> list[types.CodeAction]:
    assert isinstance(ls, DddlintServer), "handler must receive a DddlintServer"
    assert params.text_document.uri, "code action requires a document uri"
    uri = params.text_document.uri
    cursor_line = params.range.start.line
    actions: list[types.CodeAction] = []

    for f in ls.ddd_findings.get(uri, []):
        if f.line != cursor_line or f.fix is None:
            continue
        actions += [_delegated_rename(uri, f), _in_file_replacement(uri, f)]
    return actions


def _delegated_rename(uri: str, f: Finding) -> types.CodeAction:
    assert f.fix, "a rename must have a canonical term to rename to"
    assert uri, "a rename must name the document it starts in"
    return types.CodeAction(
        title=f"Rename '{f.name}' → '{f.fix}' everywhere (dddlint: {f.rule})",
        kind=types.CodeActionKind.QuickFix,
        command=types.Command(
            title=f"Rename '{f.name}' → '{f.fix}'",
            command=RENAME_COMMAND,
            arguments=[uri, f.line, f.col, f.fix],
        ),
    )


def _in_file_replacement(uri: str, f: Finding) -> types.CodeAction:
    assert f.fix, "a replacement must have a canonical term to write"
    assert f.col >= 0, "a replacement must start at a non-negative column"
    return types.CodeAction(
        title=f"Replace '{f.name}' → '{f.fix}' in this file only (dddlint: {f.rule})",
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


@server.command(RENAME_COMMAND)
def rename(ls: DddlintServer, arguments: list[types.LSPAny]) -> None:
    assert isinstance(ls, DddlintServer), "handler must receive a DddlintServer"
    assert len(arguments) == 4, "rename takes a uri, line, column and canonical term"
    new_name = arguments[3]
    ls.window_show_message(
        types.ShowMessageParams(
            type=types.MessageType.Warning,
            message=(
                f"dddlint knows the term but not the language: run your editor's own rename "
                f"here and use '{new_name}'. Wire {RENAME_COMMAND} to it to skip this step."
            ),
        )
    )


def main() -> None:
    assert server.name == "dddlint", "server must be the dddlint server"
    assert callable(server.start_io), "server must support stdio transport"
    server.start_io()
