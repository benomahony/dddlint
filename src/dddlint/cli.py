from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .check import Finding, check
from .config import load_config
from .config_check import check_config
from .discover import source_files
from .extract import Definition, definitions, language_for

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def _version(value: bool = False) -> bool:
    if not value:
        return value
    from . import __version__

    assert __version__, "version string must be non-empty"
    assert __version__[0].isdigit(), "version must start with a digit"
    typer.echo(__version__)
    raise typer.Exit()


@app.callback()
def _cli(
    version: Annotated[
        bool, typer.Option("--version", "-v", callback=_version, is_eager=True)
    ] = False,
) -> None:
    """Polyglot ubiquitous language linter for codebases and coding agents."""
    assert version is False, "version is handled by the eager callback before the body runs"
    assert app.registered_commands, "CLI must have registered commands"


DEFAULT_CONFIG = Path("dddlint.yaml")

RULE_STYLE: dict[str, str] = {
    "forbidden": "bold red",
    "alias": "bold yellow",
    "drift": "bold cyan",
    "config:forbidden-canonical-clash": "bold red",
    "config:alias-conflict": "bold yellow",
    "config:duplicate-name": "bold cyan",
}


def _resolve(root: Path | None, config: Path | None) -> tuple[Path, Path]:
    if root is None:
        root = Path.cwd()
    if config is None:
        config = root / DEFAULT_CONFIG
        if not config.exists():
            config = Path.cwd() / DEFAULT_CONFIG
    assert isinstance(root, Path), "root must be resolved to a concrete Path"
    assert config.name, "resolved config must have a filename"
    return root, config


def _print_findings(findings: list[Finding]) -> None:
    assert all(f.line >= 0 for f in findings), "findings must have non-negative lines"
    assert all(f.rule for f in findings), "every finding must carry a rule tag"
    by_file: dict[Path, list[Finding]] = defaultdict(list)
    for f in findings:
        by_file[f.path].append(f)
    for path, file_findings in by_file.items():
        console.print(f"\n[bold white]{path}[/bold white]")
        console.rule(style="dim")
        for f in file_findings:
            style = RULE_STYLE.get(f.rule, "bold white")
            console.print(
                f"  [dim]{f.line:>4}[/dim]  [{style}]{f.rule:<10}[/{style}]"
                f"  [bold]{f.name}[/bold]  [dim]{f.message}[/dim]"
            )


def _collect(root: Path, exclude: list[str]) -> list[Definition]:
    assert isinstance(root, Path), "root must be a Path to walk"
    assert isinstance(exclude, list), "exclude must be a list of patterns"
    collected: list[Definition] = []
    for path in source_files(root, exclude):
        language = language_for(path)
        if language is None:
            continue
        collected.extend(definitions(path, language))
    return collected


@app.command()
def lint(
    root: Annotated[Path | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Lint a codebase for DDD ubiquitous language violations."""
    root, config = _resolve(root, config)
    assert config.name, "config path must have a name"
    settings = load_config(config)
    collected = _collect(root, settings.exclude)
    findings = check_config(settings, config) + check(collected, settings)
    assert all(f.path for f in findings), "every finding must reference a file"
    if findings:
        _print_findings(findings)
        n = len(findings)
        console.print(f"\n[bold red]✖ {n} finding{'s' if n != 1 else ''}[/bold red]")
    else:
        console.print("[bold green]✔ no findings[/bold green]")
    raise typer.Exit(1 if findings else 0)


def _write_temp_html(content: str) -> str:
    import tempfile

    assert content, "content must be non-empty"
    path = Path(tempfile.gettempdir()) / "dddlint-graph.html"
    path.write_text(content)
    assert path.exists(), "graph file must be written"
    return str(path)


@app.command()
def html(
    root: Annotated[Path | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Open an interactive DDD graph in the browser."""
    import webbrowser

    from .view import _generate_html

    root, config = _resolve(root, config)
    assert config.name, "config path must have a name"
    settings = load_config(config)
    path = _write_temp_html(_generate_html(settings))
    assert path.endswith(".html"), "graph must be written to an .html file"
    webbrowser.open(f"file://{path}")


@app.command()
def lsp(
    root: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    """Start the LSP server (stdio transport)."""
    from .server import main as server_main

    assert callable(server_main), "server entrypoint must be callable"
    assert server_main.__name__ == "main", "must import the server main entrypoint"
    server_main()
