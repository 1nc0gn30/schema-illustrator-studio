"""Unit and integration tests for Schema Illustrator Studio CLI."""

import io
import json
import sys
from unittest.mock import patch
import pytest

from schema_illustrator_studio.cli import build_parser, main


def run_cli_args(args_list: list[str]) -> tuple[int, str, str]:
    """Helper to run CLI main() with captured stdout and stderr."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
        try:
            exit_code = main(args_list)
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return exit_code or 0, stdout_buf.getvalue(), stderr_buf.getvalue()


def test_cli_version():
    """Test --version flag."""
    code, stdout, _ = run_cli_args(["--version"])
    assert code == 0
    assert "0.1.0" in stdout or "schema-illustrator-studio" in stdout


def test_cli_help():
    """Test --help flag."""
    code, stdout, _ = run_cli_args(["--help"])
    assert code == 0
    assert "Universal Schema" in stdout or "commands" in stdout or "parse" in stdout


def test_cli_samples():
    """Test samples subcommand."""
    # List all
    code, stdout, _ = run_cli_args(["samples", "--list"])
    assert code == 0
    assert "ecommerce" in stdout or "auth" in stdout

    # Default output
    code_def, stdout_def, _ = run_cli_args(["samples"])
    assert code_def == 0
    assert "CREATE TABLE" in stdout_def

    # Specific sample
    code, stdout, _ = run_cli_args(["samples", "--name", "ecommerce", "--format", "sql"])
    assert code == 0
    assert "CREATE TABLE" in stdout


def test_cli_parse(sample_sql_schema, tmp_path):
    """Test parse subcommand with file path and string."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(sample_sql_schema, encoding="utf-8")

    code, stdout, _ = run_cli_args(["parse", str(sql_file), "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert "entities" in data


def test_cli_transpile(sample_sql_schema, tmp_path):
    """Test transpile subcommand with output file."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(sample_sql_schema, encoding="utf-8")
    out_file = tmp_path / "models.py"

    code, stdout, _ = run_cli_args(["transpile", str(sql_file), "--target", "pydantic", "--output", str(out_file)])
    assert code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "BaseModel" in content or "class " in content


def test_cli_erd(sample_sql_schema, tmp_path):
    """Test erd subcommand generating SVG file."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(sample_sql_schema, encoding="utf-8")
    out_svg = tmp_path / "diagram.svg"

    code, stdout, _ = run_cli_args(["erd", str(sql_file), "--output", str(out_svg)])
    assert code == 0
    assert out_svg.exists()
    assert "<svg" in out_svg.read_text(encoding="utf-8")


def test_cli_mermaid(sample_sql_schema, tmp_path):
    """Test mermaid subcommand."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(sample_sql_schema, encoding="utf-8")

    code, stdout, _ = run_cli_args(["mermaid", str(sql_file)])
    assert code == 0
    assert "erDiagram" in stdout


def test_cli_metrics(sample_sql_schema, tmp_path):
    """Test metrics subcommand."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(sample_sql_schema, encoding="utf-8")

    code, stdout, _ = run_cli_args(["metrics", str(sql_file), "--json"])
    assert code == 0
    data = json.loads(stdout)
    assert "total_entities" in data or "quality_score" in data or "entity_count" in data


def test_cli_doctor():
    """Test doctor / diagnostics subcommand."""
    code, stdout, _ = run_cli_args(["doctor"])
    assert code == 0
    assert "Environment" in stdout or "Platform" in stdout or "Diagnostics" in stdout


def test_cli_internal_test():
    """Test self-test runner subcommand."""
    code, stdout, _ = run_cli_args(["test"])
    assert code == 0
    assert "Test" in stdout or "PASSED" in stdout or "All" in stdout
