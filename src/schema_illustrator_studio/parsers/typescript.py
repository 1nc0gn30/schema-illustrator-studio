"""TypeScript schema parser converting interfaces, types, and enums into unified SchemaAST.

Supports interface inheritance, type aliases, string/numeric enums, union types,
optional fields, JSDoc comments, generic collections (Array, Record, Map), and
complex nested types using 100% Python standard library.
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


class TypeScriptParser:
    """Parser for TypeScript interfaces, type aliases, and enums."""

    def __init__(self, code: str) -> None:
        self.raw_code = code
        self.ast = SchemaAST(name="TypeScript_Schema")

    def parse(self) -> SchemaAST:
        """Parse TypeScript source code into SchemaAST."""
        cleaned = self._clean_code(self.raw_code)

        # Parse enums
        self._parse_enums(cleaned)
        # Parse interfaces
        self._parse_interfaces(cleaned)
        # Parse type aliases
        self._parse_type_aliases(cleaned)

        if not self.ast.entities and cleaned.strip():
            from schema_illustrator_studio.parsers.unified import SchemaParseError

            raise SchemaParseError("No valid TypeScript interfaces, types, or enums could be parsed.")

        # Infer relationships
        self.ast.infer_relationships()
        return self.ast

    def _clean_code(self, ts: str) -> str:
        """Clean imports and standard boilerplate while preserving JSDocs and declarations."""
        # Remove import / export default statements
        ts = re.sub(r"import\s+[\s\S]*?from\s+['\"][^'\"]+['\"];?", "", ts)
        ts = re.sub(r"export\s+default\s+[\w\d_]+;?", "", ts)
        return ts

    def _parse_enums(self, code: str) -> None:
        """Parse enum declarations: enum Role { ADMIN = 'ADMIN', USER = 'USER' }."""
        enum_pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?(?:export\s+)?enum\s+([A-Za-z0-9_]+)\s*\{([\s\S]*?)\}",
            re.MULTILINE,
        )

        for match in enum_pattern.finditer(code):
            jsdoc = (match.group(1) or "").strip()
            name = match.group(2).strip()
            body = match.group(3).strip()

            entity = EntityAST(
                name=name,
                description=self._clean_jsdoc(jsdoc),
                is_enum=True,
            )

            # Parse enum members
            members = [m.strip() for m in body.split(",") if m.strip()]
            for member in members:
                member_clean = re.sub(r"\/\/.*", "", member).strip()
                if not member_clean:
                    continue
                if "=" in member_clean:
                    m_name, m_val = member_clean.split("=", 1)
                    m_name = m_name.strip()
                    m_val = m_val.strip().strip("'\"")
                else:
                    m_name = member_clean
                    m_val = member_clean

                field_ast = FieldAST(
                    name=m_name,
                    type=DataType.STRING,
                    raw_type="ENUM_VAL",
                    default_value=m_val,
                    is_nullable=False,
                )
                entity.fields.append(field_ast)

            self.ast.add_entity(entity)

    def _parse_interfaces(self, code: str) -> None:
        """Parse interface declarations: interface User extends Base { ... }."""
        # Find interface keywords and extract matching brace blocks
        pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?(?:export\s+)?interface\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_,\s]+))?\s*\{",
            re.MULTILINE,
        )

        for match in pattern.finditer(code):
            jsdoc = (match.group(1) or "").strip()
            name = match.group(2).strip()
            extends_str = match.group(3) or ""
            start_pos = match.end()

            body = self._extract_matching_block(code, start_pos)

            entity = EntityAST(
                name=name,
                description=self._clean_jsdoc(jsdoc),
            )

            if extends_str:
                entity.implements = [p.strip() for p in extends_str.split(",") if p.strip()]

            self._parse_fields_block(entity, body)
            self.ast.add_entity(entity)

    def _extract_matching_block(self, text: str, start_index: int) -> str:
        """Extract content inside matching curly braces starting after opening brace."""
        depth = 1
        pos = start_index
        while pos < len(text) and depth > 0:
            c = text[pos]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start_index:pos]
            pos += 1
        return text[start_index:]

    def _parse_type_aliases(self, code: str) -> None:
        """Parse type aliases: type Status = 'A' | 'B' or type User = { ... }."""
        type_pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?(?:export\s+)?type\s+([A-Za-z0-9_]+)\s*=\s*([\s\S]*?);",
            re.MULTILINE,
        )

        for match in type_pattern.finditer(code):
            jsdoc = (match.group(1) or "").strip()
            name = match.group(2).strip()
            raw_body = match.group(3).strip()

            # Skip if already parsed as interface/enum
            if self.ast.get_entity(name):
                continue

            entity = EntityAST(
                name=name,
                description=self._clean_jsdoc(jsdoc),
            )

            # Check if union of string literals: "ACTIVE" | "INACTIVE"
            if "|" in raw_body and not raw_body.startswith("{"):
                parts = [p.strip() for p in raw_body.split("|") if p.strip()]
                is_string_enum = all(
                    (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'"))
                    for p in parts
                )
                if is_string_enum:
                    entity.is_enum = True
                    for p in parts:
                        val = p.strip("'\"")
                        entity.fields.append(
                            FieldAST(
                                name=val,
                                type=DataType.STRING,
                                raw_type="ENUM_VAL",
                                default_value=val,
                                is_nullable=False,
                            )
                        )
                else:
                    entity.is_union = True
                    entity.union_types = parts
                self.ast.add_entity(entity)
                continue

            # Check if object literal: { id: string; name: string; }
            if raw_body.startswith("{") and raw_body.endswith("}"):
                inner_body = raw_body[1:-1].strip()
                self._parse_fields_block(entity, inner_body)
                self.ast.add_entity(entity)
            else:
                # Simple type alias
                entity.is_type_alias = True
                data_type, is_array, item_type, target = self._map_ts_type(raw_body)
                entity.fields.append(
                    FieldAST(
                        name="value",
                        type=data_type,
                        raw_type=raw_body,
                        is_array=is_array,
                        array_item_type=item_type,
                        target_entity=target,
                    )
                )
                self.ast.add_entity(entity)

    def _parse_fields_block(self, entity: EntityAST, body: str) -> None:
        """Parse field lines inside interface or type object body."""
        pattern = re.compile(
            r"(?:\/\*\*([\s\S]*?)\*\/\s*)?([A-Za-z0-9_$]+)(\??)\s*:\s*([^;,\n]+)[;,]?",
            re.MULTILINE,
        )

        for match in pattern.finditer(body):
            jsdoc = (match.group(1) or "").strip()
            field_name = match.group(2).strip()
            is_optional_mark = bool(match.group(3))
            raw_type = match.group(4).strip()

            # Clean inline comments
            raw_type = re.sub(r"\/\/.*", "", raw_type).strip()

            # Check nullability
            is_nullable = is_optional_mark or "null" in raw_type or "undefined" in raw_type

            # Clean null/undefined from raw_type
            type_no_null = re.sub(r"\s*\|\s*(?:null|undefined)", "", raw_type).strip()
            type_no_null = re.sub(r"(?:null|undefined)\s*\|\s*", "", type_no_null).strip()

            data_type, is_array, item_type, target_ref = self._map_ts_type(type_no_null)

            field_ast = FieldAST(
                name=field_name,
                type=data_type,
                raw_type=raw_type,
                description=self._clean_jsdoc(jsdoc),
                is_nullable=is_nullable,
                is_array=is_array,
                array_item_type=item_type,
                target_entity=target_ref if not is_array else None,
                array_item_target=target_ref if is_array else None,
            )

            if field_name.lower() in ("id", "_id"):
                field_ast.is_primary_key = True
                field_ast.is_nullable = False

            entity.add_field(field_ast)

    def _clean_jsdoc(self, jsdoc: str) -> str:
        """Strip JSDoc stars and whitespace."""
        if not jsdoc:
            return ""
        lines = []
        for line in jsdoc.splitlines():
            cleaned = re.sub(r"^\s*\*+\s?", "", line).strip()
            if cleaned:
                lines.append(cleaned)
        return " ".join(lines)

    def _map_ts_type(
        self,
        raw_type: str,
    ) -> Tuple[DataType, bool, Optional[DataType], Optional[str]]:
        """Map TypeScript type string to DataType tuple."""
        t = raw_type.strip()

        if t.endswith("[]"):
            inner = t[:-2].strip()
            inner_type, _, _, target = self._map_ts_type(inner)
            return DataType.ARRAY, True, inner_type, target or inner

        arr_match = re.match(r"^(?:Array|ReadonlyArray)<(.*)>$", t)
        if arr_match:
            inner = arr_match.group(1).strip()
            inner_type, _, _, target = self._map_ts_type(inner)
            return DataType.ARRAY, True, inner_type, target or inner

        if t.startswith("Record<") or t.startswith("Map<") or t == "object" or t == "{}":
            return DataType.JSON, False, None, None

        t_lower = t.lower()
        if t_lower == "string":
            return DataType.STRING, False, None, None
        if t_lower in ("number", "bigint"):
            return DataType.FLOAT if t_lower == "number" else DataType.BIGINT, False, None, None
        if t_lower == "boolean":
            return DataType.BOOLEAN, False, None, None
        if t in ("Date", "datetime", "DateTime"):
            return DataType.DATETIME, False, None, None
        if t in ("any", "unknown"):
            return DataType.ANY, False, None, None
        if t_lower in ("null", "undefined", "void", "never"):
            return DataType.NULL, False, None, None
        if t in ("Buffer", "Uint8Array", "Blob"):
            return DataType.BYTES, False, None, None

        return DataType.REF, False, None, t
