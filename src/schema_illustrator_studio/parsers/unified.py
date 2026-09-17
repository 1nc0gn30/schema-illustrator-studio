"""Unified schema parser and format auto-detector.

Auto-detects schema format from raw source string, dictionary, or file path,
and parses into the canonical SchemaAST using 100% Python standard library.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

from schema_illustrator_studio.compat import safe_normalize_path, safe_read_text
from schema_illustrator_studio.models import SchemaAST
from schema_illustrator_studio.parsers.graphql import GraphQLParser
from schema_illustrator_studio.parsers.json_schema import JSONSchemaParser
from schema_illustrator_studio.parsers.sql_ddl import SQLDDLParser
from schema_illustrator_studio.parsers.typescript import TypeScriptParser


class SchemaParseError(Exception):
    """Raised when schema parsing fails or format is unsupported."""


def detect_schema_format(source: Union[str, Dict[str, Any]], filepath: Optional[Union[str, Path]] = None) -> str:
    """Auto-detect the format of the schema source.

    Returns one of: 'json_schema', 'openapi', 'sql', 'graphql', 'typescript'
    """
    # Check by file extension first if path is provided
    if filepath:
        ext = Path(filepath).suffix.lower()
        if ext in (".json",):
            return "json_schema"
        if ext in (".sql", ".ddl"):
            return "sql"
        if ext in (".graphql", ".gql"):
            return "graphql"
        if ext in (".ts", ".tsx", ".d.ts"):
            return "typescript"

    # If already a dictionary
    if isinstance(source, dict):
        if "openapi" in source or "swagger" in source:
            return "openapi"
        return "json_schema"

    raw_text = str(source).strip()

    # Check if valid JSON
    if (raw_text.startswith("{") and raw_text.endswith("}")) or (raw_text.startswith("[") and raw_text.endswith("]")):
        try:
            parsed_json = json.loads(raw_text)
            if isinstance(parsed_json, dict):
                if "openapi" in parsed_json or "swagger" in parsed_json:
                    return "openapi"
                return "json_schema"
        except json.JSONDecodeError:
            pass

    # Clean comments for heuristics
    upper_sample = raw_text[:4000].upper()

    # Check SQL
    if "CREATE TABLE" in upper_sample or "CREATE TYPE" in upper_sample or "ALTER TABLE" in upper_sample:
        return "sql"

    # Check GraphQL
    gql_matches = re.findall(r"\b(type|interface|input|enum|union|schema)\s+[A-Za-z0-9_]+\s*(?:implements\s+[^{]+)?\{", raw_text)
    if gql_matches:
        # Verify it's not TypeScript interface/type
        if not re.search(r"\binterface\s+[A-Za-z0-9_]+\s*\{[^}]*:\s*(?:string|number|boolean)", raw_text):
            return "graphql"

    # Check TypeScript
    if re.search(r"(?:export\s+)?(?:interface|type|enum)\s+[A-Za-z0-9_]+", raw_text):
        return "typescript"

    # Fallback heuristics
    if "SELECT " in upper_sample or "INSERT " in upper_sample:
        return "sql"

    return "typescript"


def parse_schema(
    source: Union[str, Path, Dict[str, Any]],
    format_hint: Optional[str] = None,
) -> SchemaAST:
    """Parse schema from a string, dict, or file path into a canonical SchemaAST.

    Parameters:
        source: Raw schema string, dictionary, or Path to a schema file.
        format_hint: Optional format override: 'json_schema', 'openapi', 'sql', 'typescript', 'ts', 'graphql', 'gql'
    """
    raw_content: Union[str, Dict[str, Any]]
    filepath: Optional[Path] = None

    if isinstance(source, (Path, str)) and not isinstance(source, dict):
        # Check if source is an existing file path
        try:
            p = safe_normalize_path(source)
            if p.exists() and p.is_file():
                filepath = p
                raw_content = safe_read_text(p)
            else:
                raw_content = str(source)
        except Exception:
            raw_content = str(source)
    else:
        raw_content = source

    detected_format = (format_hint or detect_schema_format(raw_content, filepath)).lower()

    if detected_format in ("json_schema", "jsonschema", "json", "openapi", "swagger"):
        parser = JSONSchemaParser(raw_content)
        return parser.parse()

    if isinstance(raw_content, dict):
        # Dict is always JSON Schema / OpenAPI
        parser = JSONSchemaParser(raw_content)
        return parser.parse()

    text_content = str(raw_content)

    if detected_format in ("sql", "ddl", "postgres", "postgresql", "mysql", "sqlite"):
        sql_parser = SQLDDLParser(text_content)
        return sql_parser.parse()

    if detected_format in ("graphql", "gql"):
        gql_parser = GraphQLParser(text_content)
        return gql_parser.parse()

    if detected_format in ("typescript", "ts", "dts"):
        ts_parser = TypeScriptParser(text_content)
        return ts_parser.parse()

    raise SchemaParseError(f"Unsupported or unrecognized schema format: {detected_format}")


class UnifiedParser:
    """Unified Parser wrapper providing object-oriented interface."""

    def __init__(self, source: Union[str, Path, Dict[str, Any]], format_hint: Optional[str] = None) -> None:
        self.source = source
        self.format_hint = format_hint

    def parse(self) -> SchemaAST:
        """Parse the configured source into SchemaAST."""
        return parse_schema(self.source, self.format_hint)
