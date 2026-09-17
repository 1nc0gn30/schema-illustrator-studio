"""Unit tests for Unified Schema AST models."""

import json
import pytest

from schema_illustrator_studio.models import (
    Constraint,
    ConstraintType,
    DataType,
    EntityAST,
    FieldAST,
    RelationshipAST,
    RelationshipType,
    SchemaAST,
)


def test_data_type_methods():
    """Test DataType classification methods."""
    assert DataType.INTEGER.is_numeric()
    assert DataType.FLOAT.is_numeric()
    assert not DataType.STRING.is_numeric()

    assert DataType.DATETIME.is_temporal()
    assert DataType.DATE.is_temporal()
    assert not DataType.INTEGER.is_temporal()

    assert DataType.STRING.is_primitive()
    assert DataType.BOOLEAN.is_primitive()
    assert not DataType.OBJECT.is_primitive()


def test_constraint_serialization():
    """Test Constraint to_dict and from_dict."""
    c = Constraint(
        type=ConstraintType.MIN_VALUE,
        name="min_age_check",
        expression="age >= 18",
        parameters={"min": 18},
    )
    d = c.to_dict()
    assert d["type"] == "MIN_VALUE"
    assert d["name"] == "min_age_check"

    c2 = Constraint.from_dict(d)
    assert c2.type == ConstraintType.MIN_VALUE
    assert c2.parameters["min"] == 18


def test_field_ast_properties_and_display():
    """Test FieldAST helpers, display_type, and required flag."""
    f = FieldAST(name="email", type=DataType.STRING, is_nullable=False, is_unique=True)
    assert f.is_required is True
    assert f.display_type() == "STRING"

    # Set required
    f.is_required = False
    assert f.is_nullable is True

    # Array display type
    arr_field = FieldAST(name="tags", is_array=True, array_item_type=DataType.STRING)
    assert "STRING[]" in arr_field.display_type()

    # Enum display type
    enum_field = FieldAST(name="status", enum_values=["active", "pending", "banned"])
    assert "enum(" in enum_field.display_type()

    # Serialization
    d = f.to_dict()
    assert d["name"] == "email"
    f_restored = FieldAST.from_dict(d)
    assert f_restored.name == "email"


def test_entity_ast_field_operations():
    """Test EntityAST operations (add_field, get_field, primary_keys, foreign_keys)."""
    entity = EntityAST(name="Product")
    f_id = FieldAST(name="id", type=DataType.UUID, is_primary_key=True, is_nullable=False)
    f_cat = FieldAST(name="category_id", type=DataType.UUID, is_foreign_key=True, target_entity="Category")
    f_sku = FieldAST(name="sku", type=DataType.STRING, is_unique=True)

    entity.add_field(f_id)
    entity.add_field(f_cat)
    entity.add_field(f_sku)

    assert len(entity.fields) == 3
    assert entity.get_field("id") == f_id
    assert entity.get_field("ID") == f_id  # Case-insensitive lookup
    assert len(entity.primary_keys()) == 1
    assert len(entity.foreign_keys()) == 1
    assert len(entity.unique_fields()) == 1

    # Replace field
    f_sku_updated = FieldAST(name="sku", type=DataType.STRING, description="Unique stock SKU")
    entity.add_field(f_sku_updated)
    assert len(entity.fields) == 3
    assert entity.get_field("sku").description == "Unique stock SKU"

    # Serialization
    e_dict = entity.to_dict()
    restored_e = EntityAST.from_dict(e_dict)
    assert restored_e.name == "Product"
    assert len(restored_e.fields) == 3


def test_schema_ast_full_lifecycle(sample_ast):
    """Test SchemaAST infer_relationships, topological_sort, and JSON round-trip."""
    assert len(sample_ast.entities) == 2
    assert sample_ast.get_entity("User") is not None
    assert sample_ast.get_entity("order") is not None  # Case-insensitive

    # Topological sort: User before Order
    sorted_names = sample_ast.topological_sort()
    assert sorted_names.index("User") < sorted_names.index("Order")

    # JSON Serialization & Deserialization
    json_str = sample_ast.to_json()
    assert "TestECommerce" in json_str

    restored_ast = SchemaAST.from_json(json_str)
    assert restored_ast.name == "TestECommerce"
    assert len(restored_ast.entities) == 2
    assert len(restored_ast.relationships) == 1
