"""Unit tests for Diagram Engine (SVG ERD, Mermaid, ASCII Tables, Graphviz DOT)."""

import pytest

from schema_illustrator_studio.diagram_engine import DiagramEngine


def test_svg_erd_generation(sample_ast):
    """Test generating high-fidelity SVG ERD diagrams in dark and light themes."""
    engine = DiagramEngine(sample_ast)

    # Dark Theme
    svg_dark = engine.generate_svg(theme="dark")
    assert "<svg" in svg_dark
    assert "</svg>" in svg_dark
    assert 'viewBox="' in svg_dark
    assert "User" in svg_dark
    assert "Order" in svg_dark
    assert "PK" in svg_dark
    assert "FK" in svg_dark
    assert "<path" in svg_dark  # Bezier connector curves

    # Light Theme
    svg_light = engine.generate_svg(theme="light")
    assert "<svg" in svg_light
    assert "#ffffff" in svg_light or "#f8fafc" in svg_light


def test_mermaid_erd_generation(sample_ast):
    """Test Mermaid erDiagram syntax generation."""
    engine = DiagramEngine(sample_ast)
    mermaid_str = engine.generate_mermaid()

    assert mermaid_str.startswith("erDiagram")
    assert "User {" in mermaid_str
    assert "Order {" in mermaid_str
    assert "uuid id PK" in mermaid_str or "string id PK" in mermaid_str or "id PK" in mermaid_str
    assert "Order" in mermaid_str and "User" in mermaid_str


def test_ascii_erd_generation(sample_ast):
    """Test Unicode box-drawing ASCII ER diagram renderer."""
    engine = DiagramEngine(sample_ast)
    ascii_out = engine.generate_ascii(max_width=80)

    assert "SCHEMA ARCHITECTURE" in ascii_out
    assert "User" in ascii_out
    assert "Order" in ascii_out
    assert "RELATIONSHIPS" in ascii_out
    assert "┌" in ascii_out
    assert "┘" in ascii_out


def test_graphviz_dot_generation(sample_ast):
    """Test Graphviz DOT diagram output."""
    engine = DiagramEngine(sample_ast)
    dot_out = engine.generate_dot()

    assert dot_out.startswith("digraph SchemaERD")
    assert '"User"' in dot_out
    assert '"Order"' in dot_out
    assert "->" in dot_out
