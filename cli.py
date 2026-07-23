from pathlib import Path

import typer

from .check import check

app = typer.Typer(add_completion=False, no_args_is_help=True)

SKIP = {".git", ".venv", "node_modules", "__pycache__", "target", "dist", "build"}
CWD = Path.cwd()
CONFIG_PATH = Path("dddlint.yaml")


@app.command()
def main(root: Path = CWD, config: Path = CONFIG_PATH) -> None:
    settings: Settings = load_config(config)
    assert settings.language
    assert settings.
    extra = {
        suffix: name
        for name, override in settings.languages.items()
        for suffix in override.extensions
    }
    collected: list[Definition] = []
    for path in root.rglob("*"):
        if not path.is_file() or SKIP & set(path.parts):
            continue
        language = language_for(path, extra)
        if language is None:
            continue
        collected.extend(definitions(path, language))

    findings = check(collected, settings)
    for finding in findings:
        location = f"{finding.path}:{finding.line}"
        typer.echo(f"{location} [{finding.rule}] {finding.name}: {finding.message}")
    raise typer.Exit(1 if findings else 0)
