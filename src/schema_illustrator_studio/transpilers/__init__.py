"""Multi-target code generators for schema-illustrator-studio."""

from __future__ import annotations

from typing import Any

from schema_illustrator_studio.models import SchemaAST
from schema_illustrator_studio.transpilers.graphql_gen import GraphQLGenerator, transpile_to_graphql
from schema_illustrator_studio.transpilers.json_schema_gen import (
    JSONSchemaGenerator,
    transpile_to_json_schema,
)
from schema_illustrator_studio.transpilers.pydantic_gen import (
    PydanticGenerator,
    transpile_to_pydantic,
)
from schema_illustrator_studio.transpilers.sql_gen import SQLGenerator, transpile_to_sql
from schema_illustrator_studio.transpilers.ts_gen import (
    TypeScriptGenerator,
    transpile_to_typescript,
)


def transpile(ast: SchemaAST, target: str, **options: Any) -> str:
    """Transpile a SchemaAST into the specified target language/format.

    Parameters:
        ast: The unified schema AST.
        target: Target format: 'typescript', 'ts', 'pydantic', 'python', 'sql', 'postgres', 'sqlite', 'mysql', 'graphql', 'gql', 'json_schema', 'json-schema', 'json', 'openapi'
        **options: Keyword arguments passed to the specific generator.
    """
    t = target.lower().strip().replace("-", "_")

    if t in ("typescript", "ts"):
        return transpile_to_typescript(ast, **options)

    if t in ("pydantic", "python", "py"):
        return transpile_to_pydantic(ast, **options)

    if t in ("sql", "postgres", "postgresql", "sqlite", "mysql", "ddl"):
        if t in ("sqlite", "mysql", "postgres", "postgresql") and "dialect" not in options:
            options["dialect"] = t
        return transpile_to_sql(ast, **options)

    if t in ("graphql", "gql", "sdl"):
        return transpile_to_graphql(ast, **options)

    if t in ("json_schema", "jsonschema", "json"):
        return transpile_to_json_schema(ast, as_openapi=False, **options)

    if t in ("openapi", "swagger"):
        return transpile_to_json_schema(ast, as_openapi=True, **options)

    raise ValueError(f"Unsupported transpilation target: {target}")


__all__ = [
    "TypeScriptGenerator",
    "PydanticGenerator",
    "SQLGenerator",
    "GraphQLGenerator",
    "JSONSchemaGenerator",
    "transpile",
    "transpile_to_typescript",
    "transpile_to_pydantic",
    "transpile_to_sql",
    "transpile_to_graphql",
    "transpile_to_json_schema",
]
