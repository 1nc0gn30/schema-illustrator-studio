"""JSON Schema and OpenAPI 3.x parser converting schemas into unified SchemaAST.

Handles standard JSON Schema drafts, OpenAPI 3.0/3.1 components.schemas,
$ref resolution, allOf/oneOf/anyOf unions, enums, format validations,
and nested structures using 100% Python standard library.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

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


class JSONSchemaParser:
    """Parser for JSON Schema and OpenAPI 3.x definitions."""

    def __init__(self, raw_schema: Union[str, Dict[str, Any]]) -> None:
        if isinstance(raw_schema, str):
            self.raw_data: Dict[str, Any] = json.loads(raw_schema)
        elif isinstance(raw_schema, dict):
            self.raw_data = raw_schema
        else:
            raise TypeError("Schema must be a JSON string or dictionary")

        self.ast = SchemaAST(name="JSONSchema")
        self._defs_cache: Dict[str, Dict[str, Any]] = {}

    def parse(self) -> SchemaAST:
        """Parse JSON Schema or OpenAPI document into a SchemaAST."""
        data = self.raw_data

        # Detect OpenAPI or Swagger
        if "openapi" in data or "swagger" in data:
            self._parse_openapi(data)
        elif "$defs" in data or "definitions" in data or "components" in data:
            self._parse_definitions_container(data)
        else:
            # Single root schema
            self._parse_single_root_schema(data)

        # Infer relationships between entities
        self.ast.infer_relationships()
        return self.ast

    def _extract_ref_name(self, ref_str: str) -> str:
        """Extract the target entity name from a $ref pointer."""
        parts = ref_str.rstrip("/").split("/")
        return parts[-1]

    def _parse_openapi(self, data: Dict[str, Any]) -> None:
        """Parse OpenAPI 3.0 / 3.1 or Swagger 2.0 components."""
        info = data.get("info", {})
        self.ast.name = info.get("title", "OpenAPI_Schema")
        self.ast.version = str(info.get("version", "1.0.0"))
        self.ast.description = info.get("description", "")
        self.ast.metadata["openapi_version"] = data.get("openapi") or data.get("swagger")

        schemas_dict: Dict[str, Dict[str, Any]] = {}
        if "components" in data and "schemas" in data["components"]:
            schemas_dict = data["components"]["schemas"]
        elif "definitions" in data:
            schemas_dict = data["definitions"]

        self._defs_cache.update(schemas_dict)

        for name, schema_body in schemas_dict.items():
            entity = self._parse_entity_schema(name, schema_body)
            self.ast.add_entity(entity)

    def _parse_definitions_container(self, data: Dict[str, Any]) -> None:
        """Parse top-level JSON Schema with $defs or definitions."""
        self.ast.name = data.get("title", "JSON_Schema")
        self.ast.description = data.get("description", "")

        defs = data.get("$defs") or data.get("definitions") or {}
        if "components" in data and "schemas" in data["components"]:
            defs.update(data["components"]["schemas"])

        self._defs_cache.update(defs)

        # Also check if root itself is an object
        if data.get("type") == "object" or "properties" in data:
            root_name = data.get("title") or "Root"
            root_ent = self._parse_entity_schema(root_name, data)
            self.ast.add_entity(root_ent)

        for name, schema_body in defs.items():
            entity = self._parse_entity_schema(name, schema_body)
            self.ast.add_entity(entity)

    def _parse_single_root_schema(self, data: Dict[str, Any]) -> None:
        """Parse a standalone schema object."""
        root_name = data.get("title") or "Model"
        self.ast.name = root_name
        self.ast.description = data.get("description", "")

        entity = self._parse_entity_schema(root_name, data)
        self.ast.add_entity(entity)

    def _parse_entity_schema(self, name: str, schema: Dict[str, Any]) -> EntityAST:
        """Parse a single JSON schema definition into an EntityAST."""
        entity = EntityAST(
            name=name,
            description=schema.get("description", ""),
        )

        # Handle Enum definitions
        if "enum" in schema:
            entity.is_enum = True
            for val in schema["enum"]:
                f = FieldAST(
                    name=str(val),
                    type=DataType.STRING,
                    raw_type="ENUM_VAL",
                    default_value=val,
                    is_nullable=False,
                )
                entity.fields.append(f)
            return entity

        # Handle oneOf / anyOf union definitions
        if "oneOf" in schema or "anyOf" in schema:
            variants = schema.get("oneOf") or schema.get("anyOf", [])
            entity.is_union = True
            for v in variants:
                if "$ref" in v:
                    entity.union_types.append(self._extract_ref_name(v["$ref"]))
                elif "title" in v:
                    entity.union_types.append(v["title"])

        # Handle allOf inheritance / composition
        properties: Dict[str, Any] = {}
        required_fields: set[str] = set(schema.get("required", []))

        if "allOf" in schema:
            for item in schema["allOf"]:
                if "$ref" in item:
                    parent_name = self._extract_ref_name(item["$ref"])
                    entity.implements.append(parent_name)
                    if parent_name in self._defs_cache:
                        parent_schema = self._defs_cache[parent_name]
                        properties.update(parent_schema.get("properties", {}))
                        required_fields.update(parent_schema.get("required", []))
                elif isinstance(item, dict):
                    properties.update(item.get("properties", {}))
                    required_fields.update(item.get("required", []))

        # Direct properties
        properties.update(schema.get("properties", {}))

        for prop_name, prop_def in properties.items():
            field_ast = self._parse_field(prop_name, prop_def, required_fields)
            entity.add_field(field_ast)

        return entity

    def _parse_field(
        self,
        name: str,
        prop: Dict[str, Any],
        required_list: set[str],
    ) -> FieldAST:
        """Parse a property definition into FieldAST."""
        description = prop.get("description", "")
        default_val = prop.get("default")
        is_required = name in required_list

        # Handle $ref directly
        if "$ref" in prop:
            target = self._extract_ref_name(prop["$ref"])
            return FieldAST(
                name=name,
                type=DataType.REF,
                raw_type=target,
                description=description,
                is_nullable=not is_required,
                target_entity=target,
                default_value=default_val,
            )

        # Handle type resolution
        raw_type = prop.get("type", "string")
        if isinstance(raw_type, list):
            # Nullable union type e.g. ["string", "null"]
            is_nullable = "null" in raw_type or not is_required
            non_null_types = [t for t in raw_type if t != "null"]
            main_type = non_null_types[0] if non_null_types else "string"
        else:
            main_type = str(raw_type)
            is_nullable = not is_required

        fmt = prop.get("format", "")
        data_type, is_array, array_item_type, target_ref = self._map_json_type(main_type, fmt, prop)

        field_ast = FieldAST(
            name=name,
            type=data_type,
            raw_type=f"{main_type}:{fmt}" if fmt else main_type,
            description=description,
            is_nullable=is_nullable,
            is_array=is_array,
            default_value=default_val,
            target_entity=target_ref,
            array_item_type=array_item_type,
            array_item_target=target_ref if is_array else None,
        )

        # Primary Key heuristics (id, _id, id_..., ...Id)
        if name.lower() in ("id", "_id", f"{name.lower()}_id") and (
            data_type in (DataType.UUID, DataType.INTEGER, DataType.BIGINT, DataType.STRING)
        ):
            if name.lower() in ("id", "_id"):
                field_ast.is_primary_key = True
                field_ast.is_nullable = False

        # Enum check
        if "enum" in prop:
            field_ast.type = DataType.ENUM
            field_ast.enum_values = [str(x) for x in prop["enum"]]
            field_ast.constraints.append(
                Constraint(
                    type=ConstraintType.ENUM_VALUES,
                    parameters={"values": field_ast.enum_values},
                )
            )

        # Numeric / String Constraints
        if "minimum" in prop:
            field_ast.constraints.append(
                Constraint(
                    type=ConstraintType.MIN_VALUE,
                    expression=str(prop["minimum"]),
                    parameters={"min": prop["minimum"]},
                )
            )
        if "maximum" in prop:
            field_ast.constraints.append(
                Constraint(
                    type=ConstraintType.MAX_VALUE,
                    expression=str(prop["maximum"]),
                    parameters={"max": prop["maximum"]},
                )
            )
        if "minLength" in prop:
            field_ast.constraints.append(
                Constraint(
                    type=ConstraintType.MIN_LENGTH,
                    expression=str(prop["minLength"]),
                    parameters={"min_length": prop["minLength"]},
                )
            )
        if "maxLength" in prop:
            field_ast.constraints.append(
                Constraint(
                    type=ConstraintType.MAX_LENGTH,
                    expression=str(prop["maxLength"]),
                    parameters={"max_length": prop["maxLength"]},
                )
            )
        if "pattern" in prop:
            field_ast.constraints.append(
                Constraint(
                    type=ConstraintType.PATTERN,
                    expression=prop["pattern"],
                    parameters={"pattern": prop["pattern"]},
                )
            )

        return field_ast

    def _map_json_type(
        self,
        type_str: str,
        fmt: str,
        prop: Dict[str, Any],
    ) -> Tuple[DataType, bool, Optional[DataType], Optional[str]]:
        """Map JSON Schema type + format to DataType tuple."""
        type_lower = type_str.lower()
        fmt_lower = fmt.lower()

        if fmt_lower in ("date-time", "datetime"):
            return DataType.DATETIME, False, None, None
        if fmt_lower == "date":
            return DataType.DATE, False, None, None
        if fmt_lower == "time":
            return DataType.TIME, False, None, None
        if fmt_lower in ("uuid", "guid"):
            return DataType.UUID, False, None, None
        if fmt_lower in ("byte", "binary"):
            return DataType.BYTES, False, None, None

        if type_lower == "integer":
            if fmt_lower in ("int64", "bigint"):
                return DataType.BIGINT, False, None, None
            return DataType.INTEGER, False, None, None

        if type_lower == "number":
            if fmt_lower in ("decimal", "double"):
                return DataType.DECIMAL, False, None, None
            return DataType.FLOAT, False, None, None

        if type_lower == "boolean":
            return DataType.BOOLEAN, False, None, None

        if type_lower == "array":
            items = prop.get("items", {})
            if "$ref" in items:
                ref_target = self._extract_ref_name(items["$ref"])
                return DataType.ARRAY, True, DataType.REF, ref_target
            item_type_str = items.get("type", "string")
            item_fmt = items.get("format", "")
            item_data_type, _, _, _ = self._map_json_type(item_type_str, item_fmt, items)
            return DataType.ARRAY, True, item_data_type, None

        if type_lower == "object":
            if "additionalProperties" in prop:
                return DataType.JSON, False, None, None
            return DataType.OBJECT, False, None, None

        return DataType.STRING, False, None, None
