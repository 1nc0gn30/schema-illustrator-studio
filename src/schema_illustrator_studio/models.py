"""Unified Abstract Syntax Tree (AST) for schemas across all data formats.

Supports relational entities, document models, graph schemas, TypeScript interfaces,
GraphQL SDL, JSON Schema, and OpenAPI data representations with full type safety
and round-trip serialization. Zero external runtime dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union


class DataType(str, Enum):
    """Canonical data types supported across all schema formats."""

    STRING = "STRING"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    FLOAT = "FLOAT"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"
    DATE = "DATE"
    TIME = "TIME"
    UUID = "UUID"
    JSON = "JSON"
    BYTES = "BYTES"
    ARRAY = "ARRAY"
    OBJECT = "OBJECT"
    ENUM = "ENUM"
    REF = "REF"
    UNION = "UNION"
    NULL = "NULL"
    ANY = "ANY"

    def is_numeric(self) -> bool:
        """Return True if this type is numeric."""
        return self in (DataType.INTEGER, DataType.BIGINT, DataType.FLOAT, DataType.DECIMAL)

    def is_temporal(self) -> bool:
        """Return True if this type represents date or time."""
        return self in (DataType.DATETIME, DataType.DATE, DataType.TIME)

    def is_primitive(self) -> bool:
        """Return True if this type is a primitive scalar."""
        return self in (
            DataType.STRING,
            DataType.INTEGER,
            DataType.BIGINT,
            DataType.FLOAT,
            DataType.DECIMAL,
            DataType.BOOLEAN,
            DataType.UUID,
        )


class RelationshipType(str, Enum):
    """Cardinality and direction of entity relationships."""

    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:M"


class ConstraintType(str, Enum):
    """Types of field or entity constraints."""

    PRIMARY_KEY = "PRIMARY_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    UNIQUE = "UNIQUE"
    NOT_NULL = "NOT_NULL"
    CHECK = "CHECK"
    INDEX = "INDEX"
    DEFAULT = "DEFAULT"
    MIN_VALUE = "MIN_VALUE"
    MAX_VALUE = "MAX_VALUE"
    MIN_LENGTH = "MIN_LENGTH"
    MAX_LENGTH = "MAX_LENGTH"
    PATTERN = "PATTERN"
    ENUM_VALUES = "ENUM_VALUES"


@dataclass
class Constraint:
    """A constraint applied to an entity or field."""

    type: ConstraintType
    name: Optional[str] = None
    expression: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize constraint to dict."""
        return {
            "type": self.type.value,
            "name": self.name,
            "expression": self.expression,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Constraint:
        """Deserialize constraint from dict."""
        ctype = ConstraintType(data.get("type", "CHECK"))
        return cls(
            type=ctype,
            name=data.get("name"),
            expression=data.get("expression"),
            parameters=data.get("parameters", {}),
        )


@dataclass
class FieldAST:
    """A single field / column / property in an Entity."""

    name: str
    type: DataType = DataType.STRING
    raw_type: str = ""
    description: str = ""
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False
    is_nullable: bool = True
    is_array: bool = False
    default_value: Any = None
    target_entity: Optional[str] = None
    target_field: Optional[str] = None
    array_item_type: Optional[DataType] = None
    array_item_target: Optional[str] = None
    enum_values: List[str] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_required(self) -> bool:
        """Convenience property: True if field is not nullable."""
        return not self.is_nullable

    @is_required.setter
    def is_required(self, value: bool) -> None:
        self.is_nullable = not value

    def display_type(self) -> str:
        """Generate human-readable type representation."""
        if self.is_array:
            inner = self.array_item_target or (self.array_item_type.value if self.array_item_type else "ANY")
            return f"{inner}[]"
        if self.target_entity:
            return f"ref({self.target_entity})"
        if self.enum_values:
            return f"enum({', '.join(self.enum_values[:3])}{'...' if len(self.enum_values) > 3 else ''})"
        if self.raw_type:
            return self.raw_type
        return self.type.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize field to dictionary."""
        return {
            "name": self.name,
            "type": self.type.value,
            "raw_type": self.raw_type,
            "description": self.description,
            "is_primary_key": self.is_primary_key,
            "is_foreign_key": self.is_foreign_key,
            "is_unique": self.is_unique,
            "is_nullable": self.is_nullable,
            "is_array": self.is_array,
            "default_value": self.default_value,
            "target_entity": self.target_entity,
            "target_field": self.target_field,
            "array_item_type": self.array_item_type.value if self.array_item_type else None,
            "array_item_target": self.array_item_target,
            "enum_values": list(self.enum_values),
            "constraints": [c.to_dict() for c in self.constraints],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FieldAST:
        """Deserialize field from dictionary."""
        type_val = DataType(data.get("type", "STRING"))
        item_type = DataType(data["array_item_type"]) if data.get("array_item_type") else None
        constraints = [Constraint.from_dict(c) for c in data.get("constraints", [])]
        return cls(
            name=data["name"],
            type=type_val,
            raw_type=data.get("raw_type", ""),
            description=data.get("description", ""),
            is_primary_key=bool(data.get("is_primary_key", False)),
            is_foreign_key=bool(data.get("is_foreign_key", False)),
            is_unique=bool(data.get("is_unique", False)),
            is_nullable=bool(data.get("is_nullable", True)),
            is_array=bool(data.get("is_array", False)),
            default_value=data.get("default_value"),
            target_entity=data.get("target_entity"),
            target_field=data.get("target_field"),
            array_item_type=item_type,
            array_item_target=data.get("array_item_target"),
            enum_values=list(data.get("enum_values", [])),
            constraints=constraints,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class RelationshipAST:
    """A semantic relationship between two entities."""

    source_entity: str
    source_field: str
    target_entity: str
    target_field: str = ""
    relation_type: RelationshipType = RelationshipType.MANY_TO_ONE
    cardinality: str = "N:1"
    name: str = ""
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize relationship to dictionary."""
        return {
            "name": self.name,
            "source_entity": self.source_entity,
            "source_field": self.source_field,
            "target_entity": self.target_entity,
            "target_field": self.target_field,
            "relation_type": self.relation_type.value,
            "cardinality": self.cardinality,
            "on_delete": self.on_delete,
            "on_update": self.on_update,
            "description": self.description,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RelationshipAST:
        """Deserialize relationship from dictionary."""
        rtype = RelationshipType(data.get("relation_type", "N:1"))
        return cls(
            name=data.get("name", ""),
            source_entity=data["source_entity"],
            source_field=data["source_field"],
            target_entity=data["target_entity"],
            target_field=data.get("target_field", ""),
            relation_type=rtype,
            cardinality=data.get("cardinality", rtype.value),
            on_delete=data.get("on_delete"),
            on_update=data.get("on_update"),
            description=data.get("description", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class EntityAST:
    """A table, class, type, interface, or document model in the schema."""

    name: str
    description: str = ""
    fields: List[FieldAST] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    is_enum: bool = False
    is_union: bool = False
    is_type_alias: bool = False
    union_types: List[str] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_field(self, name: str) -> Optional[FieldAST]:
        """Lookup field by name (case-sensitive first, then case-insensitive)."""
        for f in self.fields:
            if f.name == name:
                return f
        lower_name = name.lower()
        for f in self.fields:
            if f.name.lower() == lower_name:
                return f
        return None

    def add_field(self, field_ast: FieldAST) -> None:
        """Add or replace a field in this entity."""
        for i, existing in enumerate(self.fields):
            if existing.name == field_ast.name:
                self.fields[i] = field_ast
                return
        self.fields.append(field_ast)

    def primary_keys(self) -> List[FieldAST]:
        """Return all primary key fields."""
        return [f for f in self.fields if f.is_primary_key]

    def foreign_keys(self) -> List[FieldAST]:
        """Return all foreign key fields."""
        return [f for f in self.fields if f.is_foreign_key or f.target_entity is not None]

    def unique_fields(self) -> List[FieldAST]:
        """Return all unique fields."""
        return [f for f in self.fields if f.is_unique]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entity to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "constraints": [c.to_dict() for c in self.constraints],
            "is_enum": self.is_enum,
            "is_union": self.is_union,
            "is_type_alias": self.is_type_alias,
            "union_types": list(self.union_types),
            "implements": list(self.implements),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EntityAST:
        """Deserialize entity from dictionary."""
        fields = [FieldAST.from_dict(f) for f in data.get("fields", [])]
        constraints = [Constraint.from_dict(c) for c in data.get("constraints", [])]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            fields=fields,
            constraints=constraints,
            is_enum=bool(data.get("is_enum", False)),
            is_union=bool(data.get("is_union", False)),
            is_type_alias=bool(data.get("is_type_alias", False)),
            union_types=list(data.get("union_types", [])),
            implements=list(data.get("implements", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class SchemaAST:
    """The root AST container representing a complete schema system."""

    name: str = "Schema"
    version: str = "1.0.0"
    description: str = ""
    entities: Dict[str, EntityAST] = field(default_factory=dict)
    relationships: List[RelationshipAST] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_entity(self, entity: EntityAST) -> None:
        """Add an entity to the schema."""
        self.entities[entity.name] = entity

    def get_entity(self, name: str) -> Optional[EntityAST]:
        """Find entity by name (exact or case-insensitive)."""
        if name in self.entities:
            return self.entities[name]
        lower_name = name.lower()
        for k, v in self.entities.items():
            if k.lower() == lower_name:
                return v
        return None

    def add_relationship(self, rel: RelationshipAST) -> None:
        """Add a relationship if not already present."""
        for existing in self.relationships:
            if (
                existing.source_entity == rel.source_entity
                and existing.source_field == rel.source_field
                and existing.target_entity == rel.target_entity
                and existing.target_field == rel.target_field
            ):
                return
        self.relationships.append(rel)

    def infer_relationships(self) -> None:
        """Infer and populate missing relationships based on entity field metadata."""
        for entity_name, entity in self.entities.items():
            for f in entity.fields:
                if f.target_entity and f.target_entity in self.entities:
                    target_ent = self.entities[f.target_entity]
                    target_pk = f.target_field
                    if not target_pk:
                        pks = target_ent.primary_keys()
                        target_pk = pks[0].name if pks else "id"

                    # Determine cardinality
                    if f.is_array:
                        rel_type = RelationshipType.ONE_TO_MANY
                        cardinality = "1:N"
                    elif f.is_unique:
                        rel_type = RelationshipType.ONE_TO_ONE
                        cardinality = "1:1"
                    else:
                        rel_type = RelationshipType.MANY_TO_ONE
                        cardinality = "N:1"

                    rel = RelationshipAST(
                        name=f"{entity_name}_{f.name}_{f.target_entity}",
                        source_entity=entity_name,
                        source_field=f.name,
                        target_entity=f.target_entity,
                        target_field=target_pk,
                        relation_type=rel_type,
                        cardinality=cardinality,
                    )
                    self.add_relationship(rel)

    def topological_sort(self) -> List[str]:
        """Return entity names sorted so dependencies come before dependents.

        Handles circular dependencies gracefully without infinite loops or crashes.
        """
        # Build dependency graph
        deps: Dict[str, set[str]] = {name: set() for name in self.entities}
        for rel in self.relationships:
            if rel.source_entity in deps and rel.target_entity in deps:
                # source depends on target (target must be created before source)
                if rel.source_entity != rel.target_entity:
                    deps[rel.source_entity].add(rel.target_entity)

        # Also inspect direct target_entity fields
        for name, ent in self.entities.items():
            for f in ent.fields:
                if f.target_entity and f.target_entity in deps and f.target_entity != name:
                    deps[name].add(f.target_entity)

        # Kahn's Algorithm / In-degree
        in_degree: Dict[str, int] = {name: len(deps[name]) for name in self.entities}
        # Reverse map: who depends on me?
        dependents: Dict[str, set[str]] = {name: set() for name in self.entities}
        for src, targets in deps.items():
            for tgt in targets:
                dependents[tgt].add(src)

        ready = [name for name, deg in in_degree.items() if deg == 0]
        sorted_list: List[str] = []

        while ready:
            curr = ready.pop(0)
            sorted_list.append(curr)
            for dep in dependents[curr]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    ready.append(dep)

        # If circular dependencies remain, append remaining entities
        for name in self.entities:
            if name not in sorted_list:
                sorted_list.append(name)

        return sorted_list

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete AST to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relationships": [r.to_dict() for r in self.relationships],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SchemaAST:
        """Deserialize AST from dictionary."""
        entities = {
            k: EntityAST.from_dict(v) for k, v in data.get("entities", {}).items()
        }
        relationships = [
            RelationshipAST.from_dict(r) for r in data.get("relationships", [])
        ]
        return cls(
            name=data.get("name", "Schema"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            entities=entities,
            relationships=relationships,
            metadata=dict(data.get("metadata", {})),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize AST to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> SchemaAST:
        """Deserialize AST from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
