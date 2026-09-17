"""Unit and integration tests for synthetic mock data generator engine.

Tests deterministic generation, topological foreign-key integrity,
SQL/JSON/CSV exporters, MCP tool integration, CLI subcommand, and REST API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from schema_illustrator_studio import parse_schema
from schema_illustrator_studio.cli import main
from schema_illustrator_studio.mcp_server import MCPServer
from schema_illustrator_studio.mock_generator import (
    MockDataConfig,
    MockDataset,
    generate_mock_data,
)
from schema_illustrator_studio.ui_server import StudioRequestHandler


SAMPLE_RELATIONAL_SCHEMA = """
CREATE TABLE departments (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    budget DECIMAL(12,2) NOT NULL
);

CREATE TABLE employees (
    id UUID PRIMARY KEY,
    dept_id UUID NOT NULL REFERENCES departments(id),
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    salary INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMP NOT NULL
);

CREATE TABLE projects (
    id UUID PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES employees(id),
    title VARCHAR(150) NOT NULL,
    status VARCHAR(50) DEFAULT 'active'
);
"""


def test_mock_generator_topological_order():
    """Verify that parent tables are generated before child tables."""
    ast = parse_schema(SAMPLE_RELATIONAL_SCHEMA)
    config = MockDataConfig(rows_per_entity=4, seed=42)
    dataset = generate_mock_data(ast, config=config)

    assert dataset.generation_order.index("departments") < dataset.generation_order.index("employees")
    assert dataset.generation_order.index("employees") < dataset.generation_order.index("projects")

    # Verify rows generated per entity
    assert len(dataset.entities_data["departments"]) == 4
    assert len(dataset.entities_data["employees"]) == 4
    assert len(dataset.entities_data["projects"]) == 4

    # Verify foreign key referential integrity
    dept_ids = {r["id"] for r in dataset.entities_data["departments"]}
    emp_ids = {r["id"] for r in dataset.entities_data["employees"]}

    for emp in dataset.entities_data["employees"]:
        assert emp["dept_id"] in dept_ids

    for proj in dataset.entities_data["projects"]:
        assert proj["lead_id"] in emp_ids


def test_mock_generator_deterministic_seed():
    """Verify that identical seeds yield identical datasets."""
    ast = parse_schema(SAMPLE_RELATIONAL_SCHEMA)
    d1 = generate_mock_data(ast, config=MockDataConfig(rows_per_entity=3, seed=99))
    d2 = generate_mock_data(ast, config=MockDataConfig(rows_per_entity=3, seed=99))
    assert d1.to_dict() == d2.to_dict()


def test_mock_generator_sql_export():
    """Verify SQL INSERT statement formatting."""
    ast = parse_schema(SAMPLE_RELATIONAL_SCHEMA)
    dataset = generate_mock_data(ast, config=MockDataConfig(rows_per_entity=2, seed=123))
    sql = dataset.to_sql()

    assert 'INSERT INTO "departments"' in sql
    assert 'INSERT INTO "employees"' in sql
    assert 'INSERT INTO "projects"' in sql


def test_mock_generator_json_export():
    """Verify JSON formatting."""
    ast = parse_schema(SAMPLE_RELATIONAL_SCHEMA)
    dataset = generate_mock_data(ast, config=MockDataConfig(rows_per_entity=2, seed=123))
    json_str = dataset.to_json()
    parsed = json.loads(json_str)

    assert "departments" in parsed
    assert len(parsed["departments"]) == 2
    assert "email" in parsed["employees"][0]


def test_mock_generator_csv_export():
    """Verify CSV dictionary export."""
    ast = parse_schema(SAMPLE_RELATIONAL_SCHEMA)
    dataset = generate_mock_data(ast, config=MockDataConfig(rows_per_entity=2, seed=123))
    csv_map = dataset.to_csv_dict()

    assert "departments" in csv_map
    assert "id,name,budget" in csv_map["departments"]


def test_mcp_tool_schema_generate_mock_data():
    """Verify MCP tool schema_generate_mock_data returns valid output."""
    server = MCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "schema_generate_mock_data",
            "arguments": {
                "schema_content": SAMPLE_RELATIONAL_SCHEMA,
                "output_format": "json",
                "rows_per_entity": 3,
                "seed": 42,
            },
        },
    }
    res = server.handle_request(req)
    assert res is not None
    assert "result" in res
    assert not res["result"].get("isError", False)
    content = json.loads(res["result"]["content"][0]["text"])
    assert "departments" in content
    assert len(content["departments"]) == 3


def test_cli_subcommand_mock(capsys):
    """Verify CLI subcommand 'mock' runs successfully."""
    ret = main(["mock", SAMPLE_RELATIONAL_SCHEMA, "--rows", "2", "--type", "json", "--no-color"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "departments" in data
    assert len(data["departments"]) == 2
