"""Mermaid ER diagram parser converting erDiagram syntax into canonical SchemaAST.

Parses entities, attributes, primary/foreign/unique keys, comments, and relationship connectors
(||--||, ||--o{, }o--||, }o--o{) from Mermaid erDiagram notation.
100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

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


class MermaidERParser:
    """Parser for Mermaid erDiagram syntax."""

    MERMAID_TYPE_MAP: Dict[str, DataType] = {
        "string": DataType.STRING,
        "varchar": DataType.STRING,
        "text": DataType.STRING,
        "char": DataType.STRING,
        "int": DataType.INTEGER,
        "integer": DataType.INTEGER,
        "smallint": DataType.INTEGER,
        "bigint": DataType.BIGINT,
        "float": DataType.FLOAT,
        "double": DataType.FLOAT,
        "real": DataType.FLOAT,
        "decimal": DataType.DECIMAL,
        "numeric": DataType.DECIMAL,
        "bool": DataType.BOOLEAN,
        "boolean": DataType.BOOLEAN,
        "datetime": DataType.DATETIME,
        "timestamp": DataType.DATETIME,
        "date": DataType.DATE,
        "time": DataType.TIME,
        "uuid": DataType.UUID,
        "json": DataType.JSON,
        "jsonb": DataType.JSON,
        "bytes": DataType.BYTES,
        "blob": DataType.BYTES,
    }

    REL_PATTERN = re.compile(
        r"^\s*([A-Za-z0-9_]+)\s+([|o\}\{]{2}--[|o\}\{]{2})\s+([A-Za-z0-9_]+)\s*:\s*\"?([^\"]*)\"?\s*$"
    )

    ENTITY_BLOCK_PATTERN = re.compile(r"^\s*([A-Za-z0-9_]+)\s*\{", re.MULTILINE)

    def __init__(self, mermaid_text: str) -> None:
        self.raw_text = mermaid_text
        self.ast = SchemaAST(name="Mermaid_Schema")

    def parse(self) -> SchemaAST:
        """Parse Mermaid text into SchemaAST."""
        lines = self.raw_text.splitlines()

        current_entity: Optional[EntityAST] = None
        in_entity_block = False

        for line in lines:
            line_clean = line.strip()
            # Skip empty lines, comments, and diagram header
            if not line_clean or line_clean.startswith("%%") or line_clean.startswith("erDiagram"):
                continue

            # Check entity start block: EntityName {
            block_match = re.match(r"^([A-Za-z0-9_]+)\s*\{$", line_clean)
            if block_match:
                ent_name = block_match.group(1)
                current_entity = self._get_or_create_entity(ent_name)
                in_entity_block = True
                continue

            # Check entity end block: }
            if in_entity_block and line_clean == "}":
                in_entity_block = False
                current_entity = None
                continue

            # Parse attribute line inside entity block: type name [PK|FK|UK] ["comment"]
            if in_entity_block and current_entity is not None:
                self._parse_attribute_line(current_entity, line_clean)
                continue

            # Parse relationship outside block: Entity1 ||--o{ Entity2 : "label"
            rel_match = self.REL_PATTERN.match(line_clean)
            if rel_match:
                src_ent, rel_symbol, tgt_ent, label = rel_match.groups()
                self._parse_relationship(src_ent, rel_symbol, tgt_ent, label)
                continue

        self.ast.infer_relationships()
        return self.ast

    def _parse_attribute_line(self, entity: EntityAST, line: str) -> None:
        """Parse field attribute in Mermaid format."""
        # Tokens separated by space, but comments can be in quotes
        comment = ""
        quote_match = re.search(r'"([^"]*)"', line)
        if quote_match:
            comment = quote_match.group(1).strip()
            line = line[:quote_match.start()] + line[quote_match.end():]

        tokens = line.strip().split()
        if len(tokens) < 2:
            return

        raw_type = tokens[0].lower()
        field_name = tokens[1]
        keys = [t.upper() for t in tokens[2:]]

        dt = self.MERMAID_TYPE_MAP.get(raw_type, DataType.STRING)
        is_pk = "PK" in keys
        is_fk = "FK" in keys
        is_uk = "UK" in keys

        f = FieldAST(
            name=field_name,
            type=dt,
            raw_type=raw_type,
            is_primary_key=is_pk,
            is_foreign_key=is_fk,
            is_unique=is_uk,
            is_nullable=not is_pk,
            description=comment or None,
        )
        entity.add_field(f)

    def _get_or_create_entity(self, name: str) -> EntityAST:
        """Helper to get existing or create new EntityAST."""
        ent = self.ast.get_entity(name)
        if ent is None:
            ent = EntityAST(name=name)
            self.ast.add_entity(ent)
        return ent

    def _parse_relationship(self, src: str, symbol: str, tgt: str, label: str) -> None:
        """Parse relationship and map connector symbols to cardinality."""
        self._get_or_create_entity(src)
        self._get_or_create_entity(tgt)

        # Connector mappings
        # ||--||: One to One
        # ||--o{: One to Many
        # }o--||: Many to One
        # }o--o{: Many to Many
        if symbol == "||--||":
            rel_type = RelationshipType.ONE_TO_ONE
            cardinality = "1:1"
        elif symbol in ("||--o{", "||--|{"):
            rel_type = RelationshipType.ONE_TO_MANY
            cardinality = "1:N"
        elif symbol in ("}o--||", "}|--||"):
            rel_type = RelationshipType.MANY_TO_ONE
            cardinality = "N:1"
        elif symbol in ("}o--o{", "}|--|{", "}o--|{", "}|--o{"):
            rel_type = RelationshipType.MANY_TO_MANY
            cardinality = "N:M"
        else:
            rel_type = RelationshipType.MANY_TO_ONE
            cardinality = "N:1"

        rel = RelationshipAST(
            name=label.strip() or f"{src}_{tgt}",
            source_entity=src,
            source_field="id",
            target_entity=tgt,
            target_field="id",
            relation_type=rel_type,
            cardinality=cardinality,
        )
        self.ast.add_relationship(rel)


def parse_mermaid_erd(mermaid_text: str) -> SchemaAST:
    """Convenience helper to parse Mermaid erDiagram string into SchemaAST."""
    parser = MermaidERParser(mermaid_text)
    return parser.parse()
