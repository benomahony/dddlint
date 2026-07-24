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
    assert isinstance(value, bool), "value must be a bool"
    if not value:
        return value
    from . import __version__

    assert __version__, "version string must be non-empty"
    typer.echo(__version__)
    raise typer.Exit()


@app.callback()
def _cli(
    version: Annotated[
        bool, typer.Option("--version", "-v", callback=_version, is_eager=True)
    ] = False,
) -> None:
    """Polyglot ubiquitous language linter for codebases and coding agents."""
    assert isinstance(version, bool), "version flag must be a bool"
    assert app is not None, "app must be initialized"


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
    assert root is None or isinstance(root, Path), "root must be a Path or None"
    assert config is None or isinstance(config, Path), "config must be a Path or None"
    if root is None:
        root = Path.cwd()
    if config is None:
        config = root / DEFAULT_CONFIG
        if not config.exists():
            config = Path.cwd() / DEFAULT_CONFIG
    return root, config


def _print_findings(findings: list[Finding]) -> None:
    assert findings is not None, "findings must not be None"
    assert isinstance(findings, list), "findings must be a list"
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


@app.command()
def lint(
    root: Annotated[Path | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Lint a codebase for DDD ubiquitous language violations."""
    root, config = _resolve(root, config)
    assert isinstance(root, Path), "resolved root must be a Path"
    assert config.name, "config path must have a name"
    settings = load_config(config)
    extra = settings.extension_map()
    collected: list[Definition] = []
    for path in source_files(root, settings.exclude):
        language = language_for(path, extra)
        if language is None:
            continue
        collected.extend(definitions(path, language))

    findings = check_config(settings, config) + check(collected, settings)
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
    assert isinstance(root, Path), "resolved root must be a Path"
    assert config.name, "config path must have a name"
    settings = load_config(config)
    path = _write_temp_html(_generate_html(settings))
    webbrowser.open(f"file://{path}")


@app.command()
def lsp(
    root: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    """Start the LSP server (stdio transport)."""
    assert root is None or isinstance(root, Path), "root must be a Path or None"
    from .server import main as server_main

    assert callable(server_main), "server entrypoint must be callable"
    server_main()
