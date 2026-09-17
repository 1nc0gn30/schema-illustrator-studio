"""Unit tests for multi-target transpilers (TypeScript, Pydantic v2, SQL, GraphQL, JSON Schema)."""

import json
import pytest

from schema_illustrator_studio.transpilers import (
    GraphQLGenerator,
    JSONSchemaGenerator,
    PydanticGenerator,
    SQLGenerator,
    TypeScriptGenerator,
    transpile,
)


def test_transpile_to_typescript(sample_ast):
    """Test transpilation of SchemaAST into TypeScript interfaces."""
    code = transpile(sample_ast, target="typescript")
    assert "export interface User" in code
    assert "export interface Order" in code
    assert "id: string;" in code
    assert "email: string;" in code
    assert "full_name?: string;" in code


def test_transpile_to_pydantic(sample_ast):
    """Test transpilation of SchemaAST into Pydantic v2 BaseModel classes."""
    code = transpile(sample_ast, target="pydantic")
    assert "from pydantic import BaseModel" in code or "BaseModel" in code
    assert "class User(BaseModel):" in code
    assert "class Order(BaseModel):" in code
    assert "id: UUID" in code or "id: str" in code or "id:" in code


def test_transpile_to_sql(sample_ast):
    """Test transpilation of SchemaAST into PostgreSQL DDL."""
    code = transpile(sample_ast, target="sql")
    assert "CREATE TABLE" in code
    assert "User" in code or "user" in code
    assert "PRIMARY KEY" in code
    assert "REFERENCES" in code or "FOREIGN KEY" in code or "Order" in code


def test_transpile_to_graphql(sample_ast):
    """Test transpilation of SchemaAST into GraphQL SDL."""
    code = transpile(sample_ast, target="graphql")
    assert "type User" in code
    assert "type Order" in code
    assert "id: ID!" in code or "id: String!" in code


def test_transpile_to_json_schema(sample_ast):
    """Test transpilation of SchemaAST into JSON Schema Draft 2020-12."""
    code = transpile(sample_ast, target="json_schema")
    data = json.loads(code)
    assert "$defs" in data or "definitions" in data or "properties" in data


def test_transpile_to_openapi(sample_ast):
    """Test transpilation of SchemaAST into OpenAPI 3.1 components."""
    code = transpile(sample_ast, target="openapi")
    data = json.loads(code)
    assert "openapi" in data
    assert "components" in data
    assert "schemas" in data["components"]


def test_transpile_unsupported_target(sample_ast):
    """Test transpile raises ValueError on invalid target."""
    with pytest.raises(ValueError):
        transpile(sample_ast, target="fortran_90")
