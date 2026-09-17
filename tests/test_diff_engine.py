"""Tests for Differential Schema Evolution, Breaking Change Detection & Migration Drift Analyzer."""

from __future__ import annotations

import json
from schema_illustrator_studio.cli import main
from schema_illustrator_studio.diff_engine import (
    ChangeAction,
    ChangeSeverity,
    SchemaDiffEngine,
    diff_schemas,
)
from schema_illustrator_studio.mcp_server import MCPServer
from schema_illustrator_studio.parsers import parse_schema


def test_schema_diff_detects_created_and_dropped_tables() -> None:
    base_sql = """
    CREATE TABLE users (
        id UUID PRIMARY KEY,
        email VARCHAR(255) NOT NULL
    );
    CREATE TABLE legacy_tokens (
        token_id INT PRIMARY KEY
    );
    """
    target_sql = """
    CREATE TABLE users (
        id UUID PRIMARY KEY,
        email VARCHAR(255) NOT NULL
    );
    CREATE TABLE orders (
        order_id UUID PRIMARY KEY,
        amount DECIMAL NOT NULL
    );
    """
    ast_base = parse_schema(base_sql, format_hint="sql")
    ast_target = parse_schema(target_sql, format_hint="sql")

    report = diff_schemas(ast_base, ast_target)

    # legacy_tokens was dropped (BREAKING)
    # orders was created (SAFE)
    assert report.total_changes == 2
    assert report.breaking_changes_count == 1
    assert report.risk_level in ("BREAKING", "CRITICAL")

    actions = {c.action for c in report.changes}
    assert ChangeAction.DROP_ENTITY in actions
    assert ChangeAction.CREATE_ENTITY in actions

    assert "DROP TABLE legacy_tokens;" in report.sql_migration_up
    assert "CREATE TABLE orders" in report.sql_migration_up
    assert "DROP TABLE orders;" in report.sql_migration_down


def test_schema_diff_detects_column_additions_and_type_changes() -> None:
    base_sql = """
    CREATE TABLE products (
        id INT PRIMARY KEY,
        title VARCHAR(100) NOT NULL,
        price INT NOT NULL
    );
    """
    target_sql = """
    CREATE TABLE products (
        id INT PRIMARY KEY,
        title VARCHAR(100) NOT NULL,
        price DECIMAL NOT NULL,
        in_stock BOOLEAN DEFAULT true
    );
    """
    ast_base = parse_schema(base_sql, format_hint="sql")
    ast_target = parse_schema(target_sql, format_hint="sql")

    report = diff_schemas(ast_base, ast_target)

    # in_stock added (SAFE)
    # price type changed from INT to DECIMAL (WARNING - safe widening)
    assert report.total_changes == 2
    assert report.breaking_changes_count == 0

    actions = {c.action: c for c in report.changes}
    assert ChangeAction.ADD_FIELD in actions
    assert ChangeAction.MODIFY_TYPE in actions
    assert actions[ChangeAction.ADD_FIELD].severity == ChangeSeverity.SAFE
    assert actions[ChangeAction.MODIFY_TYPE].severity == ChangeSeverity.WARNING

    assert "ALTER TABLE products ADD COLUMN in_stock" in report.sql_migration_up
    assert "ALTER TABLE products ALTER COLUMN price TYPE DECIMAL" in report.sql_migration_up


def test_mcp_tool_schema_diff() -> None:
    server = MCPServer()
    base_schema = "CREATE TABLE users (id UUID PRIMARY KEY);"
    target_schema = "CREATE TABLE users (id UUID PRIMARY KEY, name VARCHAR(100));"

    req = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {
            "name": "schema_diff",
            "arguments": {
                "base_schema": base_schema,
                "target_schema": target_schema,
            },
        },
    }
    resp = server.handle_request(req)
    assert resp is not None
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    data = json.loads(content)
    assert "drift_score" in data
    assert "changes" in data
    assert len(data["changes"]) == 1
    assert data["changes"][0]["action"] == "ADD_FIELD"


def test_cli_diff_command(capsys) -> None:
    base_schema = "CREATE TABLE users (id UUID PRIMARY KEY);"
    target_schema = "CREATE TABLE users (id UUID PRIMARY KEY, active BOOLEAN);"

    code = main(["diff", base_schema, target_schema, "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "drift_score" in data
    assert data["total_changes"] == 1
