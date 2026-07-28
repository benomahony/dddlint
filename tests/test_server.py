from pathlib import Path

import pytest
from lsprotocol import types
from pygls.workspace import Workspace

from dddlint.check import Finding
from dddlint.server import (
    RENAME_COMMAND,
    DddlintServer,
    _scan,
    _to_diagnostic,
    _to_path,
    code_action,
    did_open,
    did_save,
    rename,
)

pytestmark = pytest.mark.unit


def test_server_version_tracks_package_version():
    from dddlint import __version__

    assert DddlintServer().version == __version__


class RecordingServer(DddlintServer):
    def __init__(self, root_uri: str | None) -> None:
        super().__init__()
        self.published: list[types.PublishDiagnosticsParams] = []
        self.messages: list[types.ShowMessageParams] = []
        self.protocol._workspace = Workspace(
            root_uri, position_encoding=types.PositionEncodingKind.Utf16
        )

    def text_document_publish_diagnostics(self, params: types.PublishDiagnosticsParams) -> None:
        self.published.append(params)

    def window_show_message(self, params: types.ShowMessageParams) -> None:
        self.messages.append(params)


def _write_project(tmp_path: Path) -> None:
    (tmp_path / "dddlint.yaml").write_text("forbidden: [manager]\n")
    (tmp_path / "svc.py").write_text("class OrderManager:\n    pass\n")


def test_to_path_extracts_filesystem_path():
    assert _to_path("file:///tmp/foo.py") == Path("/tmp/foo.py")


def test_to_path_decodes_percent_escapes():
    assert _to_path("file:///tmp/a%20b.py") == Path("/tmp/a b.py")


def test_to_diagnostic_maps_finding_to_range():
    finding = Finding(Path("a.py"), 2, "OrderManager", "forbidden", "banned", col=6)
    diag = _to_diagnostic(finding)
    assert diag.range.start == types.Position(line=2, character=6)
    assert diag.range.end == types.Position(line=2, character=6 + len("OrderManager"))
    assert diag.severity == types.DiagnosticSeverity.Error
    assert diag.code == "forbidden"


def test_scan_publishes_diagnostics(tmp_path: Path):
    _write_project(tmp_path)
    server = RecordingServer(tmp_path.as_uri())
    _scan(server)
    assert server.published
    assert any(p.diagnostics for p in server.published)
    assert server.ddd_findings


def test_scan_without_root_uri_is_noop():
    server = RecordingServer(None)
    _scan(server)
    assert server.published == []


def test_scan_clears_stale_findings(tmp_path: Path):
    _write_project(tmp_path)
    server = RecordingServer(tmp_path.as_uri())
    server.ddd_findings["file:///gone.py"] = [Finding(Path("/gone.py"), 0, "X", "forbidden", "m")]
    _scan(server)
    cleared = [p for p in server.published if p.uri == "file:///gone.py"]
    assert cleared and cleared[-1].diagnostics == []
    assert "file:///gone.py" not in server.ddd_findings


def test_scan_without_config_uses_defaults(tmp_path: Path):
    (tmp_path / "svc.py").write_text("class Customer:\n    pass\n")
    (tmp_path / "notes.unknownext").write_text("skip\n")
    skipped = tmp_path / ".git"
    skipped.mkdir()
    (skipped / "config.py").write_text("class Manager:\n    pass\n")
    server = RecordingServer(tmp_path.as_uri())
    _scan(server)
    assert server.ddd_findings == {}


def test_scan_skips_gitignored_files(tmp_path: Path):
    (tmp_path / "dddlint.yaml").write_text("forbidden: [manager]\n")
    (tmp_path / ".gitignore").write_text("generated/\n")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "bad.py").write_text("class OrderManager:\n    pass\n")
    server = RecordingServer(tmp_path.as_uri())
    _scan(server)
    assert server.ddd_findings == {}


def test_did_open_and_did_save_trigger_scan(tmp_path: Path):
    _write_project(tmp_path)
    server = RecordingServer(tmp_path.as_uri())
    did_open(server, types.DidOpenTextDocumentParams(text_document=None))  # type: ignore[arg-type]
    did_save(server, types.DidSaveTextDocumentParams(text_document=None))  # type: ignore[arg-type]
    assert server.published


def test_code_action_offers_fix_at_cursor_line(tmp_path: Path):
    server = RecordingServer(tmp_path.as_uri())
    uri = "file:///a.py"
    server.ddd_findings[uri] = [
        Finding(Path("/a.py"), 3, "ClientRepo", "alias", "use customer", col=0, fix="CustomerRepo")
    ]
    params = types.CodeActionParams(
        text_document=types.TextDocumentIdentifier(uri=uri),
        range=types.Range(
            start=types.Position(line=3, character=0),
            end=types.Position(line=3, character=0),
        ),
        context=types.CodeActionContext(diagnostics=[]),
    )
    actions = code_action(server, params)
    assert [action.title for action in actions] == [
        "Rename 'ClientRepo' → 'CustomerRepo' everywhere (dddlint: alias)",
        "Replace 'ClientRepo' → 'CustomerRepo' in this file only (dddlint: alias)",
    ]


def test_code_action_hands_the_rename_to_the_language_server(tmp_path: Path):
    server = RecordingServer(tmp_path.as_uri())
    uri = "file:///a.py"
    server.ddd_findings[uri] = [
        Finding(Path("/a.py"), 3, "ClientRepo", "alias", "use customer", col=6, fix="CustomerRepo")
    ]
    params = types.CodeActionParams(
        text_document=types.TextDocumentIdentifier(uri=uri),
        range=types.Range(
            start=types.Position(line=3, character=0),
            end=types.Position(line=3, character=0),
        ),
        context=types.CodeActionContext(diagnostics=[]),
    )
    delegating, in_file = code_action(server, params)
    assert delegating.edit is None
    assert delegating.command is not None
    assert delegating.command.command == RENAME_COMMAND
    assert delegating.command.arguments == [uri, 3, 6, "CustomerRepo"]
    assert in_file.edit is not None
    changes = in_file.edit.changes or {}
    assert changes[uri][0].new_text == "CustomerRepo"


def test_rename_command_is_advertised_to_clients():
    from dddlint.server import server as live

    assert RENAME_COMMAND in live.protocol.fm.commands
    assert RENAME_COMMAND.startswith("dddlint."), "the command must be namespaced to dddlint"


def test_bounced_rename_command_says_which_term_to_rename_to(tmp_path: Path):
    server = RecordingServer(tmp_path.as_uri())
    rename(server, ["file:///a.py", 3, 6, "CustomerRepo"])
    assert len(server.messages) == 1
    assert "CustomerRepo" in server.messages[0].message
    assert server.messages[0].type == types.MessageType.Warning


def test_code_action_skips_lines_without_fix(tmp_path: Path):
    server = RecordingServer(tmp_path.as_uri())
    uri = "file:///a.py"
    server.ddd_findings[uri] = [Finding(Path("/a.py"), 3, "X", "drift", "m", col=0, fix=None)]
    params = types.CodeActionParams(
        text_document=types.TextDocumentIdentifier(uri=uri),
        range=types.Range(
            start=types.Position(line=3, character=0),
            end=types.Position(line=3, character=0),
        ),
        context=types.CodeActionContext(diagnostics=[]),
    )
    assert code_action(server, params) == []
