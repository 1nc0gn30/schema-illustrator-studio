"""schema-illustrator-studio - Pure Python Schema Modeling, Multi-Format Parsing, Transpilation & Diagram Studio."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from schema_illustrator_studio.compat import (
    atomic_write,
    ensure_directory,
    is_linux,
    is_macos,
    is_termux,
    is_windows,
    safe_normalize_path,
    safe_read_text,
    safe_write_text,
)
from schema_illustrator_studio.diagram_engine import (
    DiagramEngine,
    generate_ascii_erd,
    generate_erd_svg,
    generate_mermaid_erd,
)
from schema_illustrator_studio.metrics import (
    SchemaAnalyzer,
    SchemaMetrics,
    analyze_schema,
    calculate_metrics,
)
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
from schema_illustrator_studio.parsers import (
    GraphQLParser,
    JSONSchemaParser,
    MermaidERParser,
    SQLDDLParser,
    TypeScriptParser,
    UnifiedParser,
    detect_schema_format,
    parse_mermaid_erd,
    parse_schema,
)
from schema_illustrator_studio.transpilers import (
    GraphQLGenerator,
    JSONSchemaGenerator,
    PydanticGenerator,
    SQLGenerator,
    TypeScriptGenerator,
    transpile,
    transpile_to_graphql,
    transpile_to_json_schema,
    transpile_to_pydantic,
    transpile_to_sql,
    transpile_to_typescript,
)

__version__ = "0.1.0"
__author__ = "Schema Illustrator Studio Contributors"
__description__ = "Universal schema visualization, transpilation, ERD generation, and quality metrics engine"

# Sample Schemas Raw Text
_SQL_SAMPLE = """CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    role VARCHAR(32) DEFAULT 'customer',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(120) NOT NULL,
    parent_id UUID REFERENCES categories(id)
);

CREATE TABLE products (
    id UUID PRIMARY KEY,
    category_id UUID NOT NULL REFERENCES categories(id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    total_amount DECIMAL(12,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    shipping_address TEXT,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    product_id UUID NOT NULL REFERENCES products(id),
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL
);"""

_JSON_SAMPLE = """{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AuthAndSecuritySchema",
    "$defs": {
        "User": {
            "type": "object",
            "properties": {
                "id": { "type": "string", "format": "uuid" },
                "username": { "type": "string", "minLength": 3 },
                "email": { "type": "string", "format": "email" },
                "is_mfa_enabled": { "type": "boolean", "default": false },
                "role_id": { "type": "string", "$ref": "#/$defs/Role" }
            },
            "required": ["id", "username", "email"]
        },
        "Role": {
            "type": "object",
            "properties": {
                "id": { "type": "string", "format": "uuid" },
                "name": { "type": "string" },
                "permissions": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["id", "name"]
        },
        "Session": {
            "type": "object",
            "properties": {
                "token": { "type": "string" },
                "user_id": { "type": "string", "$ref": "#/$defs/User" },
                "expires_at": { "type": "string", "format": "date-time" }
            },
            "required": ["token", "user_id"]
        }
    }
}"""

_TS_SAMPLE = """export interface Organization {
    id: string;
    name: string;
    slug: string;
    planId: string;
    createdAt: string;
}

export interface Plan {
    id: string;
    name: string;
    priceMonthly: number;
    maxMembers: number;
}

export interface Member {
    id: string;
    orgId: string;
    email: string;
    role: 'owner' | 'admin' | 'member';
}

export interface Invoice {
    id: string;
    orgId: string;
    amount: number;
    status: 'paid' | 'open' | 'void';
    paidAt?: string;
}"""

_GQL_SAMPLE = """type Profile {
    id: ID!
    userId: ID!
    bio: String
    avatarUrl: String
    website: String
}

type User {
    id: ID!
    handle: String!
    displayName: String!
    profile: Profile
    posts: [Post!]!
}

type Post {
    id: ID!
    authorId: ID!
    author: User!
    content: String!
    likeCount: Int!
    comments: [Comment!]!
    createdAt: String!
}

type Comment {
    id: ID!
    postId: ID!
    authorId: ID!
    text: String!
    createdAt: String!
}"""

SAMPLE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "id": "ecommerce",
        "name": "E-Commerce Relational Database",
        "format": "sql",
        "formats": ["sql", "json_schema", "typescript", "graphql"],
        "description": "Full relational PostgreSQL e-commerce database with users, categories, products, orders, and order items.",
        "schema": _SQL_SAMPLE,
        "sql": _SQL_SAMPLE,
        "code": _SQL_SAMPLE,
        "content": _SQL_SAMPLE,
    },
    "auth": {
        "id": "auth",
        "name": "Authentication & Security JSON Schema",
        "format": "json_schema",
        "formats": ["json_schema", "sql", "typescript", "graphql"],
        "description": "Standard JSON Schema (Draft 2020-12) for identity, RBAC roles, and authentication sessions.",
        "schema": _JSON_SAMPLE,
        "sql": _JSON_SAMPLE,
        "code": _JSON_SAMPLE,
        "content": _JSON_SAMPLE,
    },
    "saas": {
        "id": "saas",
        "name": "B2B SaaS TypeScript Domain Model",
        "format": "typescript",
        "formats": ["typescript", "sql", "json_schema", "graphql"],
        "description": "TypeScript domain model with multi-tenant organizations, subscription plans, team members, and invoices.",
        "schema": _TS_SAMPLE,
        "sql": _TS_SAMPLE,
        "code": _TS_SAMPLE,
        "content": _TS_SAMPLE,
    },
    "social": {
        "id": "social",
        "name": "Social Network GraphQL SDL",
        "format": "graphql",
        "formats": ["graphql", "sql", "typescript", "json_schema"],
        "description": "GraphQL schema with user profiles, posts, comments, relationships, and list types.",
        "schema": _GQL_SAMPLE,
        "sql": _GQL_SAMPLE,
        "code": _GQL_SAMPLE,
        "content": _GQL_SAMPLE,
    },
}


def list_sample_templates() -> List[Dict[str, Any]]:
    """Return a list of available sample template metadata."""
    res = []
    for key, val in SAMPLE_TEMPLATES.items():
        res.append({
            "id": key,
            "key": key,
            "name": val["name"],
            "format": val["format"],
            "formats": val.get("formats", [val["format"]]),
            "description": val["description"],
        })
    return res


def get_sample_template(
    name_or_format: str = "",
    template_name: Optional[str] = None,
    format_name: Optional[str] = None,
    format: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Retrieve sample template schema text by key or format name."""
    query = (template_name or format_name or format or name_or_format or "ecommerce").lower().strip()
    if query in SAMPLE_TEMPLATES:
        return SAMPLE_TEMPLATES[query]["schema"]
    for key, val in SAMPLE_TEMPLATES.items():
        if val["format"].lower() == query or key == query or query in key or query in val["format"].lower():
            return val["schema"]
    return SAMPLE_TEMPLATES["ecommerce"]["schema"]


def _ensure_ast(source: Union[SchemaAST, str, Path, Dict[str, Any]], format_hint: Optional[str] = None) -> SchemaAST:
    """Helper to convert input to SchemaAST if not already."""
    if isinstance(source, SchemaAST):
        return source
    return parse_schema(source, format_hint=format_hint)


def transpile_schema(
    source: Union[SchemaAST, str, Path, Dict[str, Any]],
    target: Optional[str] = None,
    target_format: Optional[str] = None,
    source_format: Optional[str] = None,
    format_hint: Optional[str] = None,
    **options: Any,
) -> str:
    """Transpile a schema source or SchemaAST to target language."""
    ast = _ensure_ast(source, format_hint=source_format or format_hint)
    tgt = target or target_format or "pydantic"
    return transpile(ast, target=tgt, **options)


def export_erd_svg(
    source: Union[SchemaAST, str, Path, Dict[str, Any]],
    theme: str = "dark",
    title: Optional[str] = None,
    format_hint: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate SVG ERD diagram from schema source or AST."""
    ast = _ensure_ast(source, format_hint=format_hint)
    if title:
        ast.name = title
    return generate_erd_svg(ast, theme=theme, **kwargs)


def export_mermaid_erd(
    source: Union[SchemaAST, str, Path, Dict[str, Any]],
    format_hint: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate Mermaid erDiagram from schema source or AST."""
    ast = _ensure_ast(source, format_hint=format_hint)
    return generate_mermaid_erd(ast)


def analyze_schema_metrics(
    source: Union[SchemaAST, str, Path, Dict[str, Any]],
    format_hint: Optional[str] = None,
    **kwargs: Any,
) -> SchemaMetrics:
    """Analyze schema quality metrics from schema source or AST."""
    ast = _ensure_ast(source, format_hint=format_hint)
    return analyze_schema(ast)


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__description__",
    "SAMPLE_TEMPLATES",
    "list_sample_templates",
    "get_sample_template",
    # Models
    "DataType",
    "RelationshipType",
    "ConstraintType",
    "Constraint",
    "FieldAST",
    "RelationshipAST",
    "EntityAST",
    "SchemaAST",
    # Parsers
    "JSONSchemaParser",
    "SQLDDLParser",
    "TypeScriptParser",
    "GraphQLParser",
    "MermaidERParser",
    "parse_mermaid_erd",
    "UnifiedParser",
    "detect_schema_format",
    "parse_schema",
    # Transpilers
    "TypeScriptGenerator",
    "PydanticGenerator",
    "SQLGenerator",
    "GraphQLGenerator",
    "JSONSchemaGenerator",
    "transpile",
    "transpile_schema",
    "transpile_to_typescript",
    "transpile_to_pydantic",
    "transpile_to_sql",
    "transpile_to_graphql",
    "transpile_to_json_schema",
    # Diagram Engine
    "DiagramEngine",
    "generate_erd_svg",
    "export_erd_svg",
    "generate_mermaid_erd",
    "export_mermaid_erd",
    "generate_ascii_erd",
    # Metrics
    "SchemaAnalyzer",
    "SchemaMetrics",
    "analyze_schema",
    "analyze_schema_metrics",
    "calculate_metrics",
    # Compat
    "atomic_write",
    "safe_read_text",
    "safe_write_text",
    "safe_normalize_path",
    "ensure_directory",
    "is_windows",
    "is_macos",
    "is_linux",
    "is_termux",
]
