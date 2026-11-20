
from pathlib import Path
import typer

from polylint.core.config import PolyLintConfig, ConfigError
from polylint.core.severity import Severity
from polylint.engine.rule_engine import RuleEngine
from polylint.languages.python.lexer import Lexer
from polylint.languages.python.parser import Parser, ParserError
from polylint.formatter.python_formatter import (
    PythonFormatter,
    FormatterConfig,
)


app = typer.Typer(
    name="polylint",
    help="A fast, multi-language linter and formatter.",
    no_args_is_help=True,
)


def load_config(config_path: Path | None, target: Path) -> PolyLintConfig:
    """Load an explicit config or discover pyproject.toml."""

    if config_path is not None:
        if not config_path.is_file():
            raise ConfigError(f"Configuration file not found: {config_path}")
        return PolyLintConfig.from_file(config_path)

    for directory in (target.parent, *target.parent.parents, Path.cwd()):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return PolyLintConfig.from_file(candidate)

    return PolyLintConfig()


def collect_python_files(path: Path, config: PolyLintConfig) -> list[Path]:
    """Collect Python files while respecting exclusions."""

    if path.is_file():
        candidates = [path] if path.suffix == ".py" else []
    elif path.is_dir():
        ignored_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            "build",
            "dist",
        }

        candidates = [
            file
            for file in path.rglob("*.py")
            if not any(part in ignored_dirs for part in file.parts)
            and not any(part.startswith(".") for part in file.relative_to(path).parts)
        ]
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")

    result = []

    for file in sorted(candidates):
        try:
            relative = file.relative_to(Path.cwd())
        except ValueError:
            relative = file

        if not config.is_excluded(str(relative)):
            result.append(file)

    return result


def analyze_file(
    file_path: Path,
    config: PolyLintConfig,
) -> tuple[list, str | None]:
    """Tokenize, parse, and run lint rules on one Python file."""

    try:
        source = file_path.read_text(encoding="utf-8")

        tokens = Lexer(source).tokenize()
        tree = Parser(tokens).parse()

        disabled_ids = {
            rule_id
            for rule_id, enabled in config.enabled_rules.items()
            if not enabled
        }

        severities = config.rule_severities

        engine = RuleEngine(
            disabled_ids=disabled_ids,
            severities=severities,
        )

        diagnostics = engine.run(
            tree,
            source,
            file_path=str(file_path),
        )

        return diagnostics, None

    except (SyntaxError, ParserError, UnicodeDecodeError, OSError) as error:
        return [], str(error)


@app.command()
def check(
    path: Path = typer.Argument(
        Path("."),
        help="Python file or directory to check.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a PolyLint configuration file.",
    ),
):
    """Check Python files for lint errors."""

    try:
        settings = load_config(config, path)
        files = collect_python_files(path, settings)
    except (ConfigError, FileNotFoundError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2)

    if not files:
        typer.echo("No Python files found.")
        raise typer.Exit(code=0)

    total_diagnostics = 0
    total_errors = 0

    for file in files:
        diagnostics, error = analyze_file(file, settings)

        if error:
            typer.echo(f"{file}: error: {error}")
            total_errors += 1
            continue

        for diagnostic in diagnostics:
            typer.echo(diagnostic.format())
            total_diagnostics += 1

            if diagnostic.severity == Severity.ERROR:
                total_errors += 1

    typer.echo(
        f"\nChecked {len(files)} file(s): "
        f"{total_diagnostics} diagnostic(s), "
        f"{total_errors} error(s)."
    )

    raise typer.Exit(code=1 if total_errors else 0)


@app.command()
def format(
    path: Path = typer.Argument(
        ...,
        help="Python file or directory to format.",
    ),
    check_only: bool = typer.Option(
        False,
        "--check",
        help="Check formatting without changing files.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a PolyLint configuration file.",
    ),
):
    """Format Python files."""

    try:
        settings = load_config(config, path)
        files = collect_python_files(path, settings)
    except (ConfigError, FileNotFoundError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2)

    if not files:
        typer.echo("No Python files found.")
        raise typer.Exit(code=0)

    formatter_config = FormatterConfig(
        indent_size=settings.indent_size,
        max_line_length=settings.max_line_length,
        final_newline=settings.final_newline,
        remove_trailing_whitespace=settings.remove_trailing_whitespace,
    )

    formatter = PythonFormatter(formatter_config)

    changed = 0

    for file in files:
        try:
            original = file.read_text(encoding="utf-8")
            formatted = formatter.format_code(original)

            if original == formatted:
                continue

            changed += 1

            if check_only:
                typer.echo(f"Would reformat: {file}")
            else:
                file.write_text(formatted, encoding="utf-8")
                typer.echo(f"Formatted: {file}")

        except (OSError, UnicodeDecodeError, ValueError) as error:
            typer.echo(f"Error processing {file}: {error}", err=True)
            raise typer.Exit(code=2)

    if check_only and changed:
        typer.echo(f"\n{changed} file(s) need formatting.")
        raise typer.Exit(code=1)

    if check_only:
        typer.echo("All files are correctly formatted.")
    else:
        typer.echo(f"\nFormatted {changed} file(s).")


@app.command()
def version():
    """Display the PolyLint version."""

    typer.echo("PolyLint 0.1.0")


if __name__ == "__main__":
    app()
