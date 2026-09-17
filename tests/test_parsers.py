"""Unit tests for all schema parsers (SQL, JSON Schema, TypeScript, GraphQL, Unified)."""

import pytest

from schema_illustrator_studio.models import DataType
from schema_illustrator_studio.parsers import (
    GraphQLParser,
    JSONSchemaParser,
    SQLDDLParser,
    SchemaParseError,
    TypeScriptParser,
    UnifiedParser,
    detect_schema_format,
    parse_schema,
)


def test_sql_ddl_parser(sample_sql_schema):
    """Test SQL DDL parser creates entities, primary keys, foreign keys, and relationships."""
    ast = parse_schema(sample_sql_schema, format_hint="sql")
    assert len(ast.entities) == 5
    assert "users" in ast.entities
    assert "categories" in ast.entities
    assert "products" in ast.entities
    assert "orders" in ast.entities
    assert "order_items" in ast.entities

    # Check Users table
    users = ast.entities["users"]
    pk = users.primary_keys()
    assert len(pk) == 1
    assert pk[0].name == "id"
    email_field = users.get_field("email")
    assert email_field is not None
    assert email_field.is_unique is True

    # Check Relationships
    assert len(ast.relationships) >= 4
    rel_targets = [r.target_entity for r in ast.relationships]
    assert "categories" in rel_targets or "users" in rel_targets


def test_json_schema_parser(sample_json_schema):
    """Test JSON Schema parser extracts objects, references, formats, and constraints."""
    ast = parse_schema(sample_json_schema, format_hint="json_schema")
    assert len(ast.entities) >= 3
    assert "User" in ast.entities
    assert "Role" in ast.entities
    assert "Session" in ast.entities

    user_ent = ast.entities["User"]
    assert user_ent.get_field("id") is not None
    assert user_ent.get_field("username") is not None
    role_id_field = user_ent.get_field("role_id")
    assert role_id_field is not None
    assert role_id_field.target_entity == "Role"


def test_typescript_parser(sample_ts_schema):
    """Test TypeScript interface parser extracts fields, types, and optional markers."""
    ast = parse_schema(sample_ts_schema, format_hint="typescript")
    assert len(ast.entities) == 4
    assert "Organization" in ast.entities
    assert "Plan" in ast.entities
    assert "Member" in ast.entities
    assert "Invoice" in ast.entities

    org = ast.entities["Organization"]
    assert org.get_field("id") is not None
    assert org.get_field("name").type == DataType.STRING

    invoice = ast.entities["Invoice"]
    paid_at = invoice.get_field("paidAt")
    assert paid_at is not None
    assert paid_at.is_nullable is True


def test_graphql_parser(sample_graphql_schema):
    """Test GraphQL SDL parser extracts types, required modifiers, lists, and relations."""
    ast = parse_schema(sample_graphql_schema, format_hint="graphql")
    assert len(ast.entities) == 4
    assert "User" in ast.entities
    assert "Post" in ast.entities
    assert "Profile" in ast.entities
    assert "Comment" in ast.entities

    post = ast.entities["Post"]
    author_field = post.get_field("author")
    assert author_field is not None
    assert author_field.target_entity == "User"


def test_detect_schema_format(
    sample_sql_schema,
    sample_json_schema,
    sample_ts_schema,
    sample_graphql_schema,
):
    """Test format auto-detection logic."""
    assert detect_schema_format(sample_sql_schema) == "sql"
    assert detect_schema_format(sample_json_schema) == "json_schema"
    assert detect_schema_format(sample_ts_schema) == "typescript"
    assert detect_schema_format(sample_graphql_schema) == "graphql"

    # File extensions
    assert detect_schema_format("", filepath="schema.sql") == "sql"
    assert detect_schema_format("", filepath="schema.json") == "json_schema"
    assert detect_schema_format("", filepath="schema.ts") == "typescript"
    assert detect_schema_format("", filepath="schema.graphql") == "graphql"


def test_parse_schema_auto(sample_sql_schema):
    """Test parse_schema with format=None (auto-detection)."""
    ast = parse_schema(sample_sql_schema)
    assert len(ast.entities) > 0


def test_parse_schema_invalid():
    """Test parse_schema with unsupported or malformed schema."""
    with pytest.raises(Exception):
        parse_schema("this is random non-schema text that cannot be parsed ???", format_hint="sql")
