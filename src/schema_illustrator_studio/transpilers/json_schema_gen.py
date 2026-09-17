"""JSON Schema / OpenAPI generator converting SchemaAST into standard JSON Schema documents.

Supports JSON Schema Draft 2020-12 / Draft-07 and OpenAPI 3.1 schema components with
$defs references, required constraints, validation bounds, and enum definitions
using 100% Python standard library.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from schema_illustrator_studio.models import (
    ConstraintType,
    DataType,
    EntityAST,
    FieldAST,
    SchemaAST,
)


class JSONSchemaGenerator:
    """Generates standard JSON Schema or OpenAPI schemas from SchemaAST."""

    def __init__(
        self,
        ast: SchemaAST,
        draft: str = "2020-12",
        as_openapi: bool = False,
    ) -> None:
        self.ast = ast
        self.draft = draft
        self.as_openapi = as_openapi

    def generate_dict(self) -> Dict[str, Any]:
        """Generate schema as a Python dictionary."""
        if self.as_openapi:
            return self._generate_openapi()
        return self._generate_json_schema()

    def generate(self, indent: int = 2) -> str:
        """Generate schema as formatted JSON string."""
        data = self.generate_dict()
        return json.dumps(data, indent=indent)

    def _generate_json_schema(self) -> Dict[str, Any]:
        """Generate standard Draft 2020-12 JSON Schema."""
        root: Dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": self.ast.name or "Schema",
            "description": self.ast.description or f"Generated schema v{self.ast.version}",
            "$defs": {},
        }

        for ent_name, ent in self.ast.entities.items():
            root["$defs"][ent_name] = self._generate_entity_schema(ent, def_prefix="#/$defs/")

        return root

    def _generate_openapi(self) -> Dict[str, Any]:
        """Generate OpenAPI 3.1 components.schemas dictionary."""
        root: Dict[str, Any] = {
            "openapi": "3.1.0",
            "info": {
                "title": self.ast.name or "API Schema",
                "version": self.ast.version,
                "description": self.ast.description or "",
            },
            "components": {
                "schemas": {},
            },
        }

        for ent_name, ent in self.ast.entities.items():
            root["components"]["schemas"][ent_name] = self._generate_entity_schema(
                ent, def_prefix="#/components/schemas/"
            )

        return root

    def _generate_entity_schema(self, entity: EntityAST, def_prefix: str) -> Dict[str, Any]:
        """Convert single EntityAST to JSON Schema object."""
        if entity.is_enum:
            vals = [f.default_value or f.name for f in entity.fields]
            res: Dict[str, Any] = {
                "type": "string",
                "enum": vals,
            }
            if entity.description:
                res["description"] = entity.description
            return res

        if entity.is_union:
            variants = [{"$ref": f"{def_prefix}{t}"} for t in entity.union_types]
            res = {"oneOf": variants}
            if entity.description:
                res["description"] = entity.description
            return res

        properties: Dict[str, Any] = {}
        required: List[str] = []

        for f in entity.fields:
            if not f.is_nullable:
                required.append(f.name)
            properties[f.name] = self._generate_field_schema(f, def_prefix)

        schema_obj: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema_obj["required"] = required

        if entity.description:
            schema_obj["description"] = entity.description

        return schema_obj

    def _generate_field_schema(self, f: FieldAST, def_prefix: str) -> Dict[str, Any]:
        """Convert single FieldAST to JSON Schema property."""
        if f.is_array:
            items_schema: Dict[str, Any] = {}
            if f.array_item_target:
                items_schema["$ref"] = f"{def_prefix}{f.array_item_target}"
            else:
                item_type = f.array_item_type or DataType.STRING
                items_schema = self._map_json_type(item_type)

            res: Dict[str, Any] = {
                "type": "array",
                "items": items_schema,
            }
            if f.description:
                res["description"] = f.description
            return res

        if f.target_entity:
            res = {"$ref": f"{def_prefix}{f.target_entity}"}
            if f.description:
                res["description"] = f.description
            return res

        if f.enum_values:
            res = {
                "type": "string",
                "enum": list(f.enum_values),
            }
            if f.description:
                res["description"] = f.description
            return res

        res = self._map_json_type(f.type)

        if f.description:
            res["description"] = f.description

        if f.default_value is not None:
            res["default"] = f.default_value

        for c in f.constraints:
            if c.type == ConstraintType.MIN_VALUE and "min" in c.parameters:
                res["minimum"] = c.parameters["min"]
            elif c.type == ConstraintType.MAX_VALUE and "max" in c.parameters:
                res["maximum"] = c.parameters["max"]
            elif c.type == ConstraintType.MIN_LENGTH and "min_length" in c.parameters:
                res["minLength"] = c.parameters["min_length"]
            elif c.type == ConstraintType.MAX_LENGTH and "max_length" in c.parameters:
                res["maxLength"] = c.parameters["max_length"]
            elif c.type == ConstraintType.PATTERN and "pattern" in c.parameters:
                res["pattern"] = c.parameters["pattern"]

        return res

    def _map_json_type(self, dt: DataType) -> Dict[str, Any]:
        """Map canonical DataType to JSON Schema type and format."""
        if dt == DataType.STRING:
            return {"type": "string"}
        if dt == DataType.INTEGER:
            return {"type": "integer"}
        if dt == DataType.BIGINT:
            return {"type": "integer", "format": "int64"}
        if dt == DataType.FLOAT:
            return {"type": "number"}
        if dt == DataType.DECIMAL:
            return {"type": "number", "format": "decimal"}
        if dt == DataType.BOOLEAN:
            return {"type": "boolean"}
        if dt == DataType.DATETIME:
            return {"type": "string", "format": "date-time"}
        if dt == DataType.DATE:
            return {"type": "string", "format": "date"}
        if dt == DataType.TIME:
            return {"type": "string", "format": "time"}
        if dt == DataType.UUID:
            return {"type": "string", "format": "uuid"}
        if dt in (DataType.JSON, DataType.OBJECT):
            return {"type": "object"}
        if dt == DataType.BYTES:
            return {"type": "string", "format": "binary"}
        if dt == DataType.NULL:
            return {"type": "null"}

        return {"type": "string"}


def transpile_to_json_schema(ast: SchemaAST, **kwargs: Any) -> str:
    """Convenience function to transpile SchemaAST to JSON Schema string."""
    gen = JSONSchemaGenerator(ast, **kwargs)
    return gen.generate()


def transpile_to_json_schema(ast: SchemaAST, **kwargs: Any) -> str:
    """Convenience helper to transpile SchemaAST to JSON Schema."""
    gen = JSONSchemaGenerator(ast, **kwargs)
    return gen.generate()
