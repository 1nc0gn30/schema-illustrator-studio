"""Unit tests for Mermaid erDiagram parser and two-way conversion."""

import pytest
from schema_illustrator_studio import (
    DataType,
    MermaidERParser,
    detect_schema_format,
    export_mermaid_erd,
    parse_mermaid_erd,
    parse_schema,
    transpile_schema,
)

MERMAID_SAMPLE = """erDiagram
    CUSTOMER ||--o{ ORDER : "places"
    ORDER ||--|{ ORDER_ITEM : "contains"
    PRODUCT ||--o{ ORDER_ITEM : "ordered in"

    CUSTOMER {
        string id PK
        string email UK "Customer email"
        string name
    }
    ORDER {
        string id PK
        string customer_id FK
        float total_amount
    }
    PRODUCT {
        string id PK
        string title
        decimal price
    }
    ORDER_ITEM {
        string id PK
        string order_id FK
        string product_id FK
        int quantity
    }
"""


def test_detect_mermaid_format():
    fmt = detect_schema_format(MERMAID_SAMPLE)
    assert fmt == "mermaid"


def test_parse_mermaid_erd():
    ast = parse_mermaid_erd(MERMAID_SAMPLE)
    assert len(ast.entities) == 4
    assert "CUSTOMER" in ast.entities
    assert "ORDER" in ast.entities
    assert "PRODUCT" in ast.entities
    assert "ORDER_ITEM" in ast.entities

    # Check fields and constraints
    cust = ast.entities["CUSTOMER"]
    assert len(cust.fields) == 3
    id_f = cust.get_field("id")
    assert id_f.is_primary_key is True

    email_f = cust.get_field("email")
    assert email_f.is_unique is True
    assert email_f.description == "Customer email"

    # Check relationships
    assert len(ast.relationships) == 3


def test_transpile_mermaid_to_sql_and_json_schema():
    ast = parse_schema(MERMAID_SAMPLE)
    # Transpile to SQL DDL
    sql = transpile_schema(ast, target="sql")
    assert "CREATE TABLE" in sql
    assert "CUSTOMER" in sql or "customer" in sql.lower()

    # Transpile to TypeScript
    ts = transpile_schema(ast, target="typescript")
    assert "interface" in ts
    assert "CUSTOMER" in ts or "Customer" in ts


def test_two_way_mermaid_conversion():
    # Start with Mermaid -> parse to AST -> export back to Mermaid
    ast = parse_mermaid_erd(MERMAID_SAMPLE)
    re_exported = export_mermaid_erd(ast)
    assert "erDiagram" in re_exported
    assert "CUSTOMER" in re_exported
    assert "ORDER" in re_exported
