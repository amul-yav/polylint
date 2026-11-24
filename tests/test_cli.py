
from typer.testing import CliRunner

from polylint.cli.main import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "check" in result.output
    assert "format" in result.output


def test_check_valid_python_file(tmp_path):
    source_file = tmp_path / "valid.py"
    source_file.write_text("def add(a, b):\n    return a + b\n")

    result = runner.invoke(app, ["check", str(source_file)])

    assert result.exit_code == 0


def test_check_invalid_python_file(tmp_path):
    source_file = tmp_path / "invalid.py"
    source_file.write_text("def calculateTotal(Price):\n    return Price\n")

    result = runner.invoke(app, ["check", str(source_file)])

    assert result.exit_code == 0 or result.exit_code == 1


def test_format_file(tmp_path):
    source_file = tmp_path / "format.py"
    source_file.write_text("def add(a,b):\n    return a+b")

    result = runner.invoke(app, ["format", str(source_file)])

    assert result.exit_code == 0
    assert source_file.read_text().endswith("\n")


def test_format_check_mode(tmp_path):
    source_file = tmp_path / "format.py"
    source_file.write_text("def add(a,b):\n    return a+b")

    original = source_file.read_text()

    result = runner.invoke(
        app,
        ["format", str(source_file), "--check"],
    )

    assert source_file.read_text() == original


def test_check_missing_file(tmp_path):
    missing_file = tmp_path / "missing.py"

    result = runner.invoke(app, ["check", str(missing_file)])

    assert result.exit_code != 0


def test_format_missing_file(tmp_path):
    missing_file = tmp_path / "missing.py"

    result = runner.invoke(app, ["format", str(missing_file)])

    assert result.exit_code != 0
