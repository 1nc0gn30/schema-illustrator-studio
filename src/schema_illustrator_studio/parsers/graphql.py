"""GraphQL SDL schema parser converting GraphQL definitions into unified SchemaAST.

Supports object types, interfaces, input types, enums, unions, custom scalars,
non-null (!) and list ([...]) modifiers, directives, and schema docstrings
using 100% Python standard library.
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


class GraphQLParser:
    """Parser for GraphQL Schema Definition Language (SDL)."""

    def __init__(self, sdl_text: str) -> None:
        self.raw_sdl = sdl_text
        self.ast = SchemaAST(name="GraphQL_Schema")

    def parse(self) -> SchemaAST:
        """Parse GraphQL SDL into SchemaAST."""
        cleaned = self._clean_sdl(self.raw_sdl)

        # Parse enums
        self._parse_enums(cleaned)
        # Parse unions
        self._parse_unions(cleaned)
        # Parse types & interfaces & inputs
        self._parse_object_types(cleaned)

        # Infer relationships
        self.ast.infer_relationships()
        return self.ast

    def _clean_sdl(self, sdl: str) -> str:
        """Clean single line # comments outside of triple-quoted strings."""
        # Replace triple-quoted string descriptions with normalized marker or preserve them
        return sdl

    def _extract_docstring(self, text_before: str) -> str:
        """Extract GraphQL docstring: \"\"\"...\"\"\" or \"...\"."""
        if not text_before:
            return ""
        # Triple quotes
        m3 = re.search(r'"""([\s\S]*?)"""\s*$', text_before)
        if m3:
            return m3.group(1).strip()
        # Single quotes
        m1 = re.search(r'"([^"\n]*)"\s*$', text_before)
        if m1:
            return m1.group(1).strip()
        return ""

    def _parse_enums(self, sdl: str) -> None:
        """Parse enum definitions: enum Role { ADMIN USER GUEST }."""
        enum_pattern = re.compile(
            r'((?:"""[\s\S]*?"""\s*|"[^"\n]*"\s*)?)enum\s+([A-Za-z0-9_]+)\s*\{([\s\S]*?)\}',
            re.MULTILINE,
        )

        for match in enum_pattern.finditer(sdl):
            doc = self._extract_docstring(match.group(1))
            name = match.group(2).strip()
            body = match.group(3).strip()

            entity = EntityAST(name=name, description=doc, is_enum=True)

            # Strip comments and split by whitespace
            clean_body = re.sub(r"#.*", "", body)
            members = clean_body.split()

            for member in members:
                m_clean = member.strip()
                if m_clean:
                    entity.fields.append(
                        FieldAST(
                            name=m_clean,
                            type=DataType.STRING,
                            raw_type="ENUM_VAL",
                            default_value=m_clean,
                            is_nullable=False,
                        )
                    )

            self.ast.add_entity(entity)

    def _parse_unions(self, sdl: str) -> None:
        """Parse union definitions: union SearchResult = User | Post."""
        union_pattern = re.compile(
            r'((?:"""[\s\S]*?"""\s*|"[^"\n]*"\s*)?)union\s+([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_|\s]+)',
            re.MULTILINE,
        )

        for match in union_pattern.finditer(sdl):
            doc = self._extract_docstring(match.group(1))
            name = match.group(2).strip()
            types_str = match.group(3).strip()

            variants = [t.strip() for t in types_str.split("|") if t.strip()]
            entity = EntityAST(
                name=name,
                description=doc,
                is_union=True,
                union_types=variants,
            )
            self.ast.add_entity(entity)

    def _parse_object_types(self, sdl: str) -> None:
        """Parse object types, interfaces, and inputs."""
        type_pattern = re.compile(
            r'((?:"""[\s\S]*?"""\s*|"[^"\n]*"\s*)?)(type|interface|input)\s+([A-Za-z0-9_]+)(?:\s+implements\s+([A-Za-z0-9_&\s]+))?(?:\s*@[\w\(\):"\s]+)?\s*\{([\s\S]*?)\}',
            re.MULTILINE,
        )

        for match in type_pattern.finditer(sdl):
            doc = self._extract_docstring(match.group(1))
            kind = match.group(2).strip()
            name = match.group(3).strip()
            implements_str = match.group(4) or ""
            body = match.group(5).strip()

            entity = EntityAST(
                name=name,
                description=doc,
            )
            entity.metadata["graphql_kind"] = kind

            if implements_str:
                # e.g. implements Node & Timestamped
                entity.implements = [
                    i.strip() for i in re.split(r"[&,]", implements_str) if i.strip()
                ]

            self._parse_fields(entity, body)
            self.ast.add_entity(entity)

    def _parse_fields(self, entity: EntityAST, body: str) -> None:
        """Parse field declarations inside a type body."""
        field_pattern = re.compile(
            r'((?:"""[\s\S]*?"""\s*|"[^"\n]*"\s*)?)([A-Za-z0-9_]+)(?:\s*\([^)]*\))?\s*:\s*([A-Za-z0-9_!\[\]]+)(?:\s*=\s*([^@\n#]+))?(?:\s*@[\w\(\):"\s]+)?',
            re.MULTILINE,
        )

        for match in field_pattern.finditer(body):
            doc = self._extract_docstring(match.group(1))
            field_name = match.group(2).strip()
            type_signature = match.group(3).strip()
            default_val = match.group(4).strip() if match.group(4) else None

            data_type, is_nullable, is_array, item_type, target = self._parse_type_signature(type_signature)

            field_ast = FieldAST(
                name=field_name,
                type=data_type,
                raw_type=type_signature,
                description=doc,
                is_nullable=is_nullable,
                is_array=is_array,
                default_value=default_val,
                array_item_type=item_type,
                target_entity=target if not is_array else None,
                array_item_target=target if is_array else None,
            )

            # Detect primary key (ID! or id)
            if (field_name.lower() in ("id", "_id")) or (data_type == DataType.UUID and not is_nullable):
                field_ast.is_primary_key = True

            entity.add_field(field_ast)

    def _parse_type_signature(
        self,
        sig: str,
    ) -> Tuple[DataType, bool, bool, Optional[DataType], Optional[str]]:
        """Parse GraphQL type signature like `[Post!]!`, `String!`, `[Int]`, `User`."""
        # Check outer nullability
        is_nullable = not sig.endswith("!")
        cleaned = sig.rstrip("!")

        # Check if list
        if cleaned.startswith("[") and cleaned.endswith("]"):
            is_array = True
            inner = cleaned[1:-1].strip()
            inner_clean = inner.rstrip("!")

            inner_data_type, _, _, _, inner_target = self._parse_type_signature(inner_clean)
            return DataType.ARRAY, is_nullable, True, inner_data_type, inner_target or inner_clean

        # Scalar or named type
        data_type, target = self._map_scalar_type(cleaned)
        return data_type, is_nullable, False, None, target

    def _map_scalar_type(self, type_name: str) -> Tuple[DataType, Optional[str]]:
        """Map GraphQL scalar to canonical DataType."""
        t = type_name.strip()
        if t == "String":
            return DataType.STRING, None
        if t == "Int":
            return DataType.INTEGER, None
        if t == "Float":
            return DataType.FLOAT, None
        if t == "Boolean":
            return DataType.BOOLEAN, None
        if t == "ID":
            return DataType.UUID, None
        if t in ("DateTime", "Date", "Time", "Timestamp"):
            return DataType.DATETIME, None
        if t in ("JSON", "JSONObject"):
            return DataType.JSON, None
        if t in ("Bytes", "Upload"):
            return DataType.BYTES, None

        # Custom type reference
        return DataType.REF, t
