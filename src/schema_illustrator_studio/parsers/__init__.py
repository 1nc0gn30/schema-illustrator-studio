"""Multi-format schema parsers for schema-illustrator-studio."""

from schema_illustrator_studio.parsers.graphql import GraphQLParser
from schema_illustrator_studio.parsers.json_schema import JSONSchemaParser
from schema_illustrator_studio.parsers.mermaid import MermaidERParser, parse_mermaid_erd
from schema_illustrator_studio.parsers.sql_ddl import SQLDDLParser
from schema_illustrator_studio.parsers.typescript import TypeScriptParser
from schema_illustrator_studio.parsers.unified import (
    SchemaParseError,
    UnifiedParser,
    detect_schema_format,
    parse_schema,
)

__all__ = [
    "GraphQLParser",
    "JSONSchemaParser",
    "SQLDDLParser",
    "TypeScriptParser",
    "MermaidERParser",
    "parse_mermaid_erd",
    "UnifiedParser",
    "detect_schema_format",
    "parse_schema",
    "SchemaParseError",
]
