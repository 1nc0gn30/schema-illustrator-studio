"""Unit tests for schema quality metrics and static architectural analysis."""

import json
import pytest

from schema_illustrator_studio.metrics import (
    SchemaAnalyzer,
    SchemaMetrics,
    analyze_schema,
)
from schema_illustrator_studio.models import (
    DataType,
    EntityAST,
    FieldAST,
    RelationshipAST,
    RelationshipType,
    SchemaAST,
)


def test_analyze_schema_clean_dag(sample_ast):
    """Test metrics analysis on well-structured sample schema."""
    metrics = analyze_schema(sample_ast)

    assert isinstance(metrics, SchemaMetrics)
    assert metrics.total_entities == 2
    assert metrics.total_relationships == 1
    assert metrics.quality_score >= 70.0
    assert len(metrics.tables_without_primary_key) == 0
    assert len(metrics.circular_dependencies) == 0

    # Serialization
    d = metrics.to_dict()
    assert d["total_entities"] == 2
    assert "quality_score" in d

    json_str = metrics.to_json()
    assert '"total_entities": 2' in json_str

    # Markdown report
    md = metrics.summary_markdown()
    assert "Schema Quality Audit Report" in md
    assert "Architecture Overview" in md


def test_missing_primary_key_detection():
    """Test detection and penalty for entities missing primary keys."""
    ast = SchemaAST(name="UnindexedSchema")
    ent = EntityAST(name="LogEvent")
    ent.add_field(FieldAST(name="message", type=DataType.STRING, is_primary_key=False))
    ent.add_field(FieldAST(name="level", type=DataType.STRING, is_primary_key=False))
    ast.add_entity(ent)

    metrics = analyze_schema(ast)
    assert "LogEvent" in metrics.tables_without_primary_key
    assert metrics.quality_score < 100.0


def test_circular_dependency_detection():
    """Test cycle detection in circular entity relationships (A -> B -> A)."""
    ast = SchemaAST(name="CircularSchema")

    ent_a = EntityAST(name="EntityA")
    ent_a.add_field(FieldAST(name="id", type=DataType.UUID, is_primary_key=True))
    ent_a.add_field(FieldAST(name="b_id", type=DataType.UUID, target_entity="EntityB"))
    ast.add_entity(ent_a)

    ent_b = EntityAST(name="EntityB")
    ent_b.add_field(FieldAST(name="id", type=DataType.UUID, is_primary_key=True))
    ent_b.add_field(FieldAST(name="a_id", type=DataType.UUID, target_entity="EntityA"))
    ast.add_entity(ent_b)

    ast.add_relationship(
        RelationshipAST(
            source_entity="EntityA",
            source_field="b_id",
            target_entity="EntityB",
            target_field="id",
        )
    )
    ast.add_relationship(
        RelationshipAST(
            source_entity="EntityB",
            source_field="a_id",
            target_entity="EntityA",
            target_field="id",
        )
    )

    metrics = analyze_schema(ast)
    assert len(metrics.circular_dependencies) > 0


def test_orphan_entity_detection():
    """Test identification of orphan entities without foreign keys or references."""
    ast = SchemaAST(name="OrphanSchema")

    user = EntityAST(name="User")
    user.add_field(FieldAST(name="id", type=DataType.UUID, is_primary_key=True))
    ast.add_entity(user)

    orphan = EntityAST(name="StandAloneConfig")
    orphan.add_field(FieldAST(name="key", type=DataType.STRING, is_primary_key=True))
    ast.add_entity(orphan)

    metrics = analyze_schema(ast)
    assert "StandAloneConfig" in metrics.orphan_entities or "User" in metrics.orphan_entities
