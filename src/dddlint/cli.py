import asyncio
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

from .check import Finding, check
from .config import Config, load_config
from .config_check import check_config
from .discover import source_files
from .extract import Definition, definitions, language_for, path_definitions

if TYPE_CHECKING:
    from .insights import Insight

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
    "forbidden:module": "bold red",
    "alias": "bold yellow",
    "alias:module": "bold yellow",
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


def _require_config(path: Path) -> Config:
    assert path.name, "config path must have a filename"
    assert isinstance(path, Path), "config must be a Path"
    if not path.exists():
        console.print(f"[bold red]no config found at {path}[/bold red]")
        console.print("[dim]run 'dddlint init' to write a starter dddlint.yaml[/dim]")
        raise typer.Exit(2)
    return load_config(path)


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


def _collect(root: Path, exclude: list[str], base: Path, paths: bool = False) -> list[Definition]:
    assert isinstance(root, Path), "root must be a Path to walk"
    assert isinstance(exclude, list), "exclude must be a list of patterns"
    assert base.is_dir(), "exclude patterns must be anchored to an existing directory"
    collected: list[Definition] = []
    named: set[tuple[str, Path]] = set()
    for path in source_files(root, exclude, base):
        language = language_for(path)
        if language is None:
            continue
        collected.extend(definitions(path, language))
        for named_path in path_definitions(path, root) if paths else []:
            if (named_path.name, named_path.path) not in named:
                named.add((named_path.name, named_path.path))
                collected.append(named_path)
    return collected


STARTER_CONFIG = """\
# https://benomahony.github.io/dddlint/reference/config/
enforce_canonical: true
name_uniqueness: true

# terms that must never appear in a definition name
forbidden: []

# paths to skip, gitignore syntax, relative to this file
exclude: []

# canonical terms and the aliases that must give way to them
synonyms: []
  # - canonical: customer
  #   aliases: [client, user]

# bounded contexts, each with its own vocabulary
contexts: []
  # - name: billing
  #   include: ["**/billing/**"]
"""


@app.command()
def init(
    root: Annotated[Path | None, typer.Argument()] = None,
) -> None:
    """Write a starter dddlint.yaml."""
    assert STARTER_CONFIG.endswith("\n"), "the starter config must end with a newline"
    assert "name_uniqueness" in STARTER_CONFIG, "the starter config must show the defaults"
    target = (root or Path.cwd()) / DEFAULT_CONFIG
    if target.exists():
        console.print(f"[bold red]{target} already exists[/bold red]")
        raise typer.Exit(1)
    target.write_text(STARTER_CONFIG)
    console.print(f"[bold green]✔ wrote {target}[/bold green]")


@app.command()
def lint(
    root: Annotated[Path | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Lint a codebase for DDD ubiquitous language violations."""
    root, config = _resolve(root, config)
    assert config.name, "config path must have a name"
    settings = _require_config(config)
    collected = _collect(root, settings.exclude, config.parent, paths=True)
    findings = check_config(settings, config) + check(collected, settings)
    assert all(f.path for f in findings), "every finding must reference a file"
    if findings:
        _print_findings(findings)
        n = len(findings)
        console.print(f"\n[bold red]✖ {n} finding{'s' if n != 1 else ''}[/bold red]")
    else:
        console.print("[bold green]✔ no findings[/bold green]")
    raise typer.Exit(1 if findings else 0)


INSIGHT_STYLE: dict[str, str] = {
    "near-synonym": "bold magenta",
    "context-outlier": "bold yellow",
}


def _backend_missing(model: str, error: ImportError) -> str:
    assert model, "the message must name the configured model"
    assert str(error), "the message must carry the import failure"
    extra = "embed-local" if model.startswith("sentence-transformers:") else "embed"
    return (
        f"'{model}' needs a backend that is not installed.\n"
        f"install it with: uv add 'dddlint[{extra}]'\n"
        f"{error}"
    )


def _print_backend_missing(target: Console, model: str, error: ImportError) -> None:
    assert model, "the message must name the configured model"
    assert error is not None, "the message must carry the import failure"
    target.print(_backend_missing(model, error), style="bold red", markup=False)


def _vectors(names: list[str], settings: Config, base: Path) -> dict[str, list[float]]:
    assert names, "there must be names to embed"
    assert base.is_dir(), "the cache must be anchored to an existing directory"
    cache = settings.embeddings.cache
    embeddings = settings.embeddings.model_copy(
        update={"cache": cache if cache.is_absolute() else base / cache}
    )
    try:
        from .embed import embed_names

        return asyncio.run(embed_names(names, embeddings))
    except ImportError as error:
        _print_backend_missing(console, settings.embeddings.model, error)
        raise typer.Exit(2) from error


def _print_insights(insights: list["Insight"]) -> None:
    assert all(insight.rule for insight in insights), "every insight must carry a rule tag"
    assert all(insight.names for insight in insights), "every insight must name something"
    for insight in insights:
        style = INSIGHT_STYLE.get(insight.rule, "bold white")
        console.print(
            f"  [dim]{insight.score:.2f}[/dim]  [{style}]{insight.rule:<16}[/{style}]"
            f"  [bold]{', '.join(insight.names)}[/bold]  [dim]{insight.message}[/dim]"
        )


@app.command("map")
def vocabulary_map(
    root: Annotated[Path | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Report project-level vocabulary insights from name embeddings."""
    root, config = _resolve(root, config)
    assert config.name, "config path must have a name"
    settings = _require_config(config)
    collected = _collect(root, settings.exclude, config.parent)
    assert all(d.name for d in collected), "every collected definition must have a name"
    if not collected:
        console.print("[bold yellow]no definitions found[/bold yellow]")
        raise typer.Exit(0)
    vectors = _vectors([d.name for d in collected], settings, config.parent)
    from .insights import context_outliers, map_points, near_synonyms

    insights = near_synonyms(collected, vectors, settings) + context_outliers(
        collected, vectors, settings
    )
    console.print(f"\n[bold white]{len(vectors)} names[/bold white]")
    console.rule(style="dim")
    _print_insights(insights)
    console.print(f"\n[bold cyan]◆ {len(insights)} insights[/bold cyan]")
    import webbrowser

    from .view import _generate_scatter

    points = map_points(collected, vectors, settings)
    target = config.parent / "dddmap.html"
    target.write_text(_generate_scatter(points, insights))
    console.print(f"[dim]map written to file://{target.resolve()}[/dim]", soft_wrap=True)
    webbrowser.open(f"file://{target.resolve()}")


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
    settings = _require_config(config)
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
