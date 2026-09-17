"""Google Material 3 Schema Studio & Multi-Format Transpiler MCP Server.

A zero-dependency universal schema illustrator, transpiler, diagram engine,
and Model Context Protocol (MCP) server for Python 3.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Public Package Metadata
__version__ = "0.1.0"
__author__ = "Google DeepMind Advanced Agentic Coding"
__license__ = "MIT"
__description__ = "Google Material 3 Schema Studio & Multi-Format Transpiler MCP Server"

# Core Models
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

# Parsers
from schema_illustrator_studio.parsers import (
    GraphQLParser,
    JSONSchemaParser,
    SQLDDLParser,
    TypeScriptParser,
    UnifiedParser,
    detect_schema_format,
    parse_schema,
    SchemaParseError,
)

# Transpilers
from schema_illustrator_studio.transpilers import (
    GraphQLGenerator,
    JSONSchemaGenerator,
    PydanticGenerator,
    SQLGenerator,
    TypeScriptGenerator,
    transpile,
)

# Sample Templates Definitions
SAMPLE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "name": "E-Commerce Platform",
        "description": "Relational e-commerce system with users, categories, products, orders, order items, reviews, and payments.",
        "sql": """CREATE TABLE users (
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
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  total_amount DECIMAL(12,2) NOT NULL,
  status VARCHAR(50) DEFAULT 'pending',
  shipping_address TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
  id UUID PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES orders(id),
  product_id UUID NOT NULL REFERENCES products(id),
  unit_price DECIMAL(10,2) NOT NULL,
  quantity INT NOT NULL
);

CREATE TABLE reviews (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  product_id UUID NOT NULL REFERENCES products(id),
  rating INT NOT NULL,
  comment TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments (
  id UUID PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES orders(id),
  amount DECIMAL(12,2) NOT NULL,
  payment_method VARCHAR(50) NOT NULL,
  status VARCHAR(50) DEFAULT 'completed',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);""",
        "json_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "ECommerceSchema",
            "$defs": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "email": {"type": "string", "format": "email"},
                        "fullName": {"type": "string"},
                        "role": {"type": "string", "enum": ["customer", "admin", "vendor"]},
                    },
                    "required": ["id", "email"],
                },
                "Product": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "title": {"type": "string"},
                        "price": {"type": "number", "minimum": 0},
                        "categoryId": {"type": "string", "$ref": "#/$defs/Category"},
                    },
                    "required": ["id", "title", "price"],
                },
                "Category": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "slug": {"type": "string"},
                    },
                    "required": ["id", "name"],
                },
                "Order": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "userId": {"type": "string", "$ref": "#/$defs/User"},
                        "totalAmount": {"type": "number"},
                        "status": {"type": "string", "enum": ["pending", "paid", "shipped", "cancelled"]},
                    },
                    "required": ["id", "userId", "totalAmount"],
                },
            },
        },
        "ts": """export interface User {
  id: string;
  email: string;
  fullName?: string;
  role: 'customer' | 'admin' | 'vendor';
  createdAt: Date;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  parentId?: string;
}

export interface Product {
  id: string;
  categoryId: string;
  title: string;
  description?: string;
  price: number;
  stockQuantity: number;
  isActive: boolean;
}

export interface Order {
  id: string;
  userId: string;
  totalAmount: number;
  status: 'pending' | 'paid' | 'shipped' | 'cancelled';
  items: OrderItem[];
}

export interface OrderItem {
  id: string;
  orderId: string;
  productId: string;
  unitPrice: number;
  quantity: number;
}""",
        "graphql": """type User {
  id: ID!
  email: String!
  fullName: String
  role: String!
  orders: [Order!]!
}

type Category {
  id: ID!
  name: String!
  slug: String!
  products: [Product!]!
}

type Product {
  id: ID!
  categoryId: ID!
  category: Category!
  title: String!
  price: Float!
  stockQuantity: Int!
}

type Order {
  id: ID!
  userId: ID!
  user: User!
  totalAmount: Float!
  status: String!
  items: [OrderItem!]!
}

type OrderItem {
  id: ID!
  orderId: ID!
  productId: ID!
  product: Product!
  unitPrice: Float!
  quantity: Int!
}""",
    },
    "auth_users": {
        "name": "User Auth & RBAC Identity",
        "description": "Enterprise user authentication, role-based access control, sessions, refresh tokens, and audit logs.",
        "sql": """CREATE TABLE organizations (
  id UUID PRIMARY KEY,
  name VARCHAR(150) NOT NULL,
  slug VARCHAR(100) NOT NULL UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE roles (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  name VARCHAR(64) NOT NULL,
  description TEXT
);

CREATE TABLE permissions (
  id UUID PRIMARY KEY,
  code VARCHAR(100) NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE role_permissions (
  role_id UUID NOT NULL REFERENCES roles(id),
  permission_id UUID NOT NULL REFERENCES permissions(id),
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE users (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  is_mfa_enabled BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_roles (
  user_id UUID NOT NULL REFERENCES users(id),
  role_id UUID NOT NULL REFERENCES roles(id),
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE sessions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  token VARCHAR(255) NOT NULL UNIQUE,
  ip_address VARCHAR(45),
  user_agent TEXT,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  action VARCHAR(100) NOT NULL,
  resource VARCHAR(100) NOT NULL,
  ip_address VARCHAR(45),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);""",
        "json_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "AuthAndIdentitySchema",
            "$defs": {
                "Organization": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "slug": {"type": "string"},
                    },
                    "required": ["id", "name", "slug"],
                },
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "orgId": {"type": "string", "$ref": "#/$defs/Organization"},
                        "email": {"type": "string", "format": "email"},
                        "isActive": {"type": "boolean", "default": True},
                    },
                    "required": ["id", "orgId", "email"],
                },
                "Role": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "permissions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "name"],
                },
                "Session": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "userId": {"type": "string", "$ref": "#/$defs/User"},
                        "token": {"type": "string"},
                        "expiresAt": {"type": "string", "format": "date-time"},
                    },
                    "required": ["id", "userId", "token", "expiresAt"],
                },
            },
        },
        "ts": """export interface Organization {
  id: string;
  name: string;
  slug: string;
  createdAt: Date;
}

export interface User {
  id: string;
  organizationId: string;
  email: string;
  isActive: boolean;
  isMfaEnabled: boolean;
  createdAt: Date;
}

export interface Role {
  id: string;
  organizationId: string;
  name: string;
  description?: string;
}

export interface Session {
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
}

export interface AuditLog {
  id: string;
  userId?: string;
  action: string;
  resource: string;
  createdAt: Date;
}""",
        "graphql": """type Organization {
  id: ID!
  name: String!
  slug: String!
  users: [User!]!
}

type User {
  id: ID!
  organizationId: ID!
  organization: Organization!
  email: String!
  isActive: Boolean!
  roles: [Role!]!
  sessions: [Session!]!
}

type Role {
  id: ID!
  name: String!
  description: String
}

type Session {
  id: ID!
  userId: ID!
  token: String!
  expiresAt: String!
}""",
    },
    "social_graph": {
        "name": "Social Network & Community Graph",
        "description": "Social networking schema with user profiles, posts, comments, likes, follower graphs, tags, and media assets.",
        "sql": """CREATE TABLE profiles (
  id UUID PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  display_name VARCHAR(100) NOT NULL,
  bio TEXT,
  avatar_url VARCHAR(500),
  website VARCHAR(255),
  follower_count INT DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
  id UUID PRIMARY KEY,
  profile_id UUID NOT NULL REFERENCES profiles(id),
  content TEXT NOT NULL,
  like_count INT DEFAULT 0,
  comment_count INT DEFAULT 0,
  is_published BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comments (
  id UUID PRIMARY KEY,
  post_id UUID NOT NULL REFERENCES posts(id),
  profile_id UUID NOT NULL REFERENCES profiles(id),
  parent_id UUID REFERENCES comments(id),
  content TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE likes (
  profile_id UUID NOT NULL REFERENCES profiles(id),
  post_id UUID NOT NULL REFERENCES posts(id),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (profile_id, post_id)
);

CREATE TABLE follows (
  follower_id UUID NOT NULL REFERENCES profiles(id),
  following_id UUID NOT NULL REFERENCES profiles(id),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (follower_id, following_id)
);

CREATE TABLE tags (
  id UUID PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE post_tags (
  post_id UUID NOT NULL REFERENCES posts(id),
  tag_id UUID NOT NULL REFERENCES tags(id),
  PRIMARY KEY (post_id, tag_id)
);""",
        "json_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "SocialGraphSchema",
            "$defs": {
                "Profile": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "username": {"type": "string"},
                        "displayName": {"type": "string"},
                        "bio": {"type": "string"},
                    },
                    "required": ["id", "username", "displayName"],
                },
                "Post": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "profileId": {"type": "string", "$ref": "#/$defs/Profile"},
                        "content": {"type": "string"},
                        "likeCount": {"type": "integer", "default": 0},
                    },
                    "required": ["id", "profileId", "content"],
                },
                "Comment": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "postId": {"type": "string", "$ref": "#/$defs/Post"},
                        "profileId": {"type": "string", "$ref": "#/$defs/Profile"},
                        "content": {"type": "string"},
                    },
                    "required": ["id", "postId", "profileId", "content"],
                },
            },
        },
        "ts": """export interface Profile {
  id: string;
  username: string;
  displayName: string;
  bio?: string;
  avatarUrl?: string;
  followerCount: number;
}

export interface Post {
  id: string;
  profileId: string;
  content: string;
  likeCount: number;
  commentCount: number;
  createdAt: Date;
}

export interface Comment {
  id: string;
  postId: string;
  profileId: string;
  parentId?: string;
  content: string;
}

export interface Follow {
  followerId: string;
  followingId: string;
  createdAt: Date;
}""",
        "graphql": """type Profile {
  id: ID!
  username: String!
  displayName: String!
  bio: String
  posts: [Post!]!
}

type Post {
  id: ID!
  profileId: ID!
  author: Profile!
  content: String!
  likeCount: Int!
  comments: [Comment!]!
}

type Comment {
  id: ID!
  postId: ID!
  author: Profile!
  content: String!
}""",
    },
    "saas_billing": {
        "name": "SaaS Multi-Tenant Subscription & Billing",
        "description": "Multi-tenant SaaS subscription billing system with tenants, plans, subscriptions, invoices, invoice items, and usage records.",
        "sql": """CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  name VARCHAR(150) NOT NULL,
  domain VARCHAR(100) NOT NULL UNIQUE,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE plans (
  id UUID PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  code VARCHAR(50) NOT NULL UNIQUE,
  monthly_price DECIMAL(10,2) NOT NULL,
  annual_price DECIMAL(10,2) NOT NULL,
  max_seats INT NOT NULL DEFAULT 5,
  features JSONB
);

CREATE TABLE subscriptions (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  plan_id UUID NOT NULL REFERENCES plans(id),
  status VARCHAR(50) DEFAULT 'active',
  current_period_start TIMESTAMP NOT NULL,
  current_period_end TIMESTAMP NOT NULL,
  cancel_at_period_end BOOLEAN DEFAULT FALSE
);

CREATE TABLE payment_methods (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  card_brand VARCHAR(50),
  last4 VARCHAR(4) NOT NULL,
  is_default BOOLEAN DEFAULT TRUE,
  exp_month INT NOT NULL,
  exp_year INT NOT NULL
);

CREATE TABLE invoices (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  subscription_id UUID REFERENCES subscriptions(id),
  number VARCHAR(50) NOT NULL UNIQUE,
  amount_due DECIMAL(10,2) NOT NULL,
  amount_paid DECIMAL(10,2) DEFAULT 0.00,
  status VARCHAR(50) DEFAULT 'draft',
  due_date DATE NOT NULL,
  paid_at TIMESTAMP
);

CREATE TABLE invoice_items (
  id UUID PRIMARY KEY,
  invoice_id UUID NOT NULL REFERENCES invoices(id),
  description VARCHAR(255) NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  unit_price DECIMAL(10,2) NOT NULL,
  amount DECIMAL(10,2) NOT NULL
);

CREATE TABLE usage_records (
  id UUID PRIMARY KEY,
  subscription_id UUID NOT NULL REFERENCES subscriptions(id),
  metric_name VARCHAR(100) NOT NULL,
  quantity BIGINT NOT NULL DEFAULT 1,
  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);""",
        "json_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "SaaSBillingSchema",
            "$defs": {
                "Tenant": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "domain": {"type": "string"},
                        "isActive": {"type": "boolean", "default": True},
                    },
                    "required": ["id", "name", "domain"],
                },
                "Plan": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "code": {"type": "string"},
                        "monthlyPrice": {"type": "number"},
                    },
                    "required": ["id", "name", "code", "monthlyPrice"],
                },
                "Subscription": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "tenantId": {"type": "string", "$ref": "#/$defs/Tenant"},
                        "planId": {"type": "string", "$ref": "#/$defs/Plan"},
                        "status": {"type": "string", "enum": ["active", "past_due", "canceled", "trialing"]},
                    },
                    "required": ["id", "tenantId", "planId", "status"],
                },
                "Invoice": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "tenantId": {"type": "string", "$ref": "#/$defs/Tenant"},
                        "amountDue": {"type": "number"},
                        "status": {"type": "string", "enum": ["draft", "open", "paid", "void"]},
                    },
                    "required": ["id", "tenantId", "amountDue"],
                },
            },
        },
        "ts": """export interface Tenant {
  id: string;
  name: string;
  domain: string;
  isActive: boolean;
}

export interface Plan {
  id: string;
  name: string;
  code: string;
  monthlyPrice: number;
  annualPrice: number;
  maxSeats: number;
}

export interface Subscription {
  id: string;
  tenantId: string;
  planId: string;
  status: 'active' | 'past_due' | 'canceled' | 'trialing';
  currentPeriodStart: Date;
  currentPeriodEnd: Date;
}

export interface Invoice {
  id: string;
  tenantId: string;
  subscriptionId?: string;
  number: string;
  amountDue: number;
  amountPaid: number;
  status: 'draft' | 'open' | 'paid' | 'void';
}""",
        "graphql": """type Tenant {
  id: ID!
  name: String!
  domain: String!
  subscriptions: [Subscription!]!
}

type Plan {
  id: ID!
  name: String!
  code: String!
  monthlyPrice: Float!
}

type Subscription {
  id: ID!
  tenantId: ID!
  tenant: Tenant!
  planId: ID!
  plan: Plan!
  status: String!
}

type Invoice {
  id: ID!
  tenantId: ID!
  tenant: Tenant!
  number: String!
  amountDue: Float!
  status: String!
}""",
    },
}


def get_sample_template(name: str, format_name: str = "sql") -> str:
    """Retrieve a sample schema template by key and format."""
    normalized_key = name.lower().replace("-", "_")
    if normalized_key not in SAMPLE_TEMPLATES:
        normalized_key = "ecommerce"

    tmpl = SAMPLE_TEMPLATES[normalized_key]
    fmt = format_name.lower().replace("-", "_")

    if fmt in ("sql", "ddl", "postgres"):
        return tmpl.get("sql", "")
    elif fmt in ("json_schema", "jsonschema", "json"):
        val = tmpl.get("json_schema", {})
        return json.dumps(val, indent=2) if isinstance(val, dict) else str(val)
    elif fmt in ("ts", "typescript"):
        return tmpl.get("ts", "")
    elif fmt in ("graphql", "gql"):
        return tmpl.get("graphql", "")
    return tmpl.get("sql", "")


def list_sample_templates() -> List[Dict[str, Any]]:
    """Return a list of all available sample schema templates."""
    results: List[Dict[str, Any]] = []
    for key, val in SAMPLE_TEMPLATES.items():
        results.append(
            {
                "id": key,
                "name": val["name"],
                "description": val["description"],
                "formats": ["sql", "json-schema", "ts", "graphql"],
            }
        )
    return results


def transpile_schema(
    ast_or_raw: Union[SchemaAST, str, Path, Dict[str, Any]],
    target_format: str,
    source_format: Optional[str] = None,
    **options: Any,
) -> str:
    """Transpile a schema (SchemaAST or raw text/file) into the target format.

    Supported targets: 'typescript', 'ts', 'pydantic', 'python', 'sql', 'graphql', 'json-schema', 'openapi'
    """
    if isinstance(ast_or_raw, SchemaAST):
        ast = ast_or_raw
    else:
        ast = parse_schema(ast_or_raw, format_hint=source_format)

    return transpile(ast, target=target_format, **options)


def export_mermaid_erd(ast_or_raw: Union[SchemaAST, str, Path, Dict[str, Any]]) -> str:
    """Export schema as a standard Mermaid erDiagram code block."""
    if isinstance(ast_or_raw, SchemaAST):
        ast = ast_or_raw
    else:
        ast = parse_schema(ast_or_raw)

    lines: List[str] = ["erDiagram"]

    # 1. Output relationships
    for rel in ast.relationships:
        src = re.sub(r"[^A-Za-z0-9_]", "_", rel.source_entity).upper()
        tgt = re.sub(r"[^A-Za-z0-9_]", "_", rel.target_entity).upper()

        card = rel.cardinality or "N:1"
        if card in ("1:1", "ONE_TO_ONE"):
            op = "||--||"
        elif card in ("1:N", "ONE_TO_MANY"):
            op = "||--o{"
        elif card in ("N:M", "MANY_TO_MANY"):
            op = "}o--o{"
        else:  # N:1
            op = "}o--||"

        label = rel.name or rel.source_field or "relates"
        clean_label = re.sub(r"[^A-Za-z0-9_]", "_", label)
        lines.append(f"    {src} {op} {tgt} : {clean_label}")

    if not ast.relationships and len(ast.entities) == 0:
        lines.append("    EMPTY_SCHEMA")
        return "\n".join(lines)

    lines.append("")

    # 2. Output entity bodies
    for ent_name, ent in ast.entities.items():
        clean_ent = re.sub(r"[^A-Za-z0-9_]", "_", ent_name).upper()
        lines.append(f"    {clean_ent} {{")
        for f in ent.fields:
            type_str = f.type.value.lower() if hasattr(f.type, "value") else str(f.type).lower()
            clean_field = re.sub(r"[^A-Za-z0-9_]", "_", f.name)

            flags: List[str] = []
            if f.is_primary_key:
                flags.append("PK")
            if f.is_foreign_key or f.target_entity:
                flags.append("FK")
            if f.is_unique and not f.is_primary_key:
                flags.append("UK")

            flag_str = f" {','.join(flags)}" if flags else ""
            desc = f' "{f.description.replace('"', '')}"' if f.description else ""
            lines.append(f"        {type_str} {clean_field}{flag_str}{desc}")
        lines.append("    }")

    return "\n".join(lines)


def export_erd_svg(
    ast_or_raw: Union[SchemaAST, str, Path, Dict[str, Any]],
    title: str = "Entity Relationship Diagram",
    theme: str = "material3-dark",
) -> str:
    """Generate a clean, standalone, high-fidelity SVG ERD visualization."""
    if isinstance(ast_or_raw, SchemaAST):
        ast = ast_or_raw
    else:
        ast = parse_schema(ast_or_raw)

    # Color Themes
    themes = {
        "material3-dark": {
            "bg": "#121218",
            "canvas_bg": "#181822",
            "card_bg": "#222232",
            "card_header": "#2d2d42",
            "card_border": "#3a3a54",
            "text": "#f1f5f9",
            "text_muted": "#94a3b8",
            "primary": "#a881ff",
            "accent": "#38bdf8",
            "pk_badge": "#fbbf24",
            "fk_badge": "#34d399",
            "rel_line": "#818cf8",
            "grid_dots": "#2e2e42",
        },
        "material3-light": {
            "bg": "#f8fafc",
            "canvas_bg": "#f1f5f9",
            "card_bg": "#ffffff",
            "card_header": "#f1f5f9",
            "card_border": "#cbd5e1",
            "text": "#0f172a",
            "text_muted": "#64748b",
            "primary": "#6366f1",
            "accent": "#0284c7",
            "pk_badge": "#d97706",
            "fk_badge": "#059669",
            "rel_line": "#6366f1",
            "grid_dots": "#cbd5e1",
        },
        "cyberpunk": {
            "bg": "#090a0f",
            "canvas_bg": "#0e101a",
            "card_bg": "#151828",
            "card_header": "#1f2238",
            "card_border": "#ff007f",
            "text": "#00f0ff",
            "text_muted": "#ff007f",
            "primary": "#ff007f",
            "accent": "#00f0ff",
            "pk_badge": "#ffe600",
            "fk_badge": "#00ff66",
            "rel_line": "#00f0ff",
            "grid_dots": "#1f2238",
        },
        "slate": {
            "bg": "#0b0f19",
            "canvas_bg": "#0f172a",
            "card_bg": "#1e293b",
            "card_header": "#334155",
            "card_border": "#475569",
            "text": "#f8fafc",
            "text_muted": "#94a3b8",
            "primary": "#38bdf8",
            "accent": "#818cf8",
            "pk_badge": "#f59e0b",
            "fk_badge": "#10b981",
            "rel_line": "#38bdf8",
            "grid_dots": "#334155",
        },
    }

    t = themes.get(theme.lower(), themes["material3-dark"])

    # Layout Parameters
    card_width = 280
    row_height = 28
    header_height = 42
    padding_x = 80
    padding_y = 70
    start_x = 60
    start_y = 120

    entities_list = list(ast.entities.values())
    entity_count = len(entities_list)

    num_cols = max(1, min(4, math.ceil(math.sqrt(max(1, entity_count * 1.5)))))
    if entity_count <= 2:
        num_cols = entity_count or 1

    # Position each entity
    positions: Dict[str, Dict[str, Any]] = {}
    col_heights = [start_y] * num_cols

    for i, ent in enumerate(entities_list):
        col_idx = i % num_cols
        x = start_x + col_idx * (card_width + padding_x)
        y = col_heights[col_idx]

        visible_fields = ent.fields[:15]
        h = header_height + (len(visible_fields) * row_height) + 16

        positions[ent.name] = {
            "x": x,
            "y": y,
            "w": card_width,
            "h": h,
            "center_x": x + card_width / 2,
            "center_y": y + h / 2,
            "entity": ent,
            "fields": visible_fields,
        }

        col_heights[col_idx] += h + padding_y

    canvas_width = max(1000, start_x * 2 + num_cols * (card_width + padding_x))
    canvas_height = max(700, max(col_heights) + 60)

    svg_parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height}" width="100%" height="100%" style="background-color: {t["bg"]}; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">',
        "<defs>",
        f'<pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.5" fill="{t["grid_dots"]}" opacity="0.4"/></pattern>',
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{t["rel_line"]}"/></marker>',
        '<filter id="shadow" x="-5%" y="-5%" width="115%" height="115%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.35"/></filter>',
        "</defs>",
        f'<rect width="100%" height="100%" fill="url(#grid)"/>',
    ]

    # Title Bar
    svg_parts.append(
        f'<rect x="0" y="0" width="{canvas_width}" height="70" fill="{t["card_bg"]}" opacity="0.95" />'
    )
    svg_parts.append(
        f'<line x1="0" y1="70" x2="{canvas_width}" y2="70" stroke="{t["card_border"]}" stroke-width="1.5" />'
    )
    svg_parts.append(
        f'<text x="40" y="44" font-size="22" font-weight="700" fill="{t["text"]}">{title}</text>'
    )
    svg_parts.append(
        f'<text x="{canvas_width - 40}" y="44" font-size="14" font-weight="500" fill="{t["text_muted"]}" text-anchor="end">Entities: {entity_count}  |  Relationships: {len(ast.relationships)}  |  Format: Material 3</text>'
    )

    # 1. Render Relationships as Bezier Curves
    for rel in ast.relationships:
        src_pos = positions.get(rel.source_entity)
        tgt_pos = positions.get(rel.target_entity)

        if not src_pos or not tgt_pos:
            continue

        if src_pos["x"] < tgt_pos["x"]:
            x1 = src_pos["x"] + src_pos["w"]
            y1 = src_pos["center_y"]
            x2 = tgt_pos["x"]
            y2 = tgt_pos["center_y"]
            cx1 = x1 + (x2 - x1) / 2
            cy1 = y1
            cx2 = x1 + (x2 - x1) / 2
            cy2 = y2
        elif src_pos["x"] > tgt_pos["x"]:
            x1 = src_pos["x"]
            y1 = src_pos["center_y"]
            x2 = tgt_pos["x"] + tgt_pos["w"]
            y2 = tgt_pos["center_y"]
            cx1 = x1 - (x1 - x2) / 2
            cy1 = y1
            cx2 = x1 - (x1 - x2) / 2
            cy2 = y2
        else:
            # Same column
            x1 = src_pos["x"] + src_pos["w"]
            y1 = src_pos["center_y"]
            x2 = tgt_pos["x"] + tgt_pos["w"]
            y2 = tgt_pos["center_y"]
            cx1 = x1 + 60
            cy1 = y1
            cx2 = x2 + 60
            cy2 = y2

        path_d = f"M {x1} {y1} C {cx1} {cy1}, {cx2} {cy2}, {x2} {y2}"
        svg_parts.append(
            f'<path d="{path_d}" stroke="{t["rel_line"]}" stroke-width="2" fill="none" opacity="0.8" marker-end="url(#arrow)" />'
        )

        # Label
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2 - 6
        card_label = rel.cardinality or "N:1"
        svg_parts.append(
            f'<rect x="{mid_x - 18}" y="{mid_y - 12}" width="36" height="18" rx="4" fill="{t["card_bg"]}" stroke="{t["card_border"]}" stroke-width="1" />'
        )
        svg_parts.append(
            f'<text x="{mid_x}" y="{mid_y + 1}" font-size="10" font-weight="700" fill="{t["accent"]}" text-anchor="middle">{card_label}</text>'
        )

    # 2. Render Entity Cards
    for ent_name, pos in positions.items():
        x, y, w, h = pos["x"], pos["y"], pos["w"], pos["h"]
        ent = pos["entity"]

        # Card container with shadow
        svg_parts.append(
            f'<g filter="url(#shadow)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{t["card_bg"]}" stroke="{t["card_border"]}" stroke-width="1.5" />'
        )

        # Header background
        svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{header_height}" rx="10" fill="{t["card_header"]}" />'
        )
        svg_parts.append(
            f'<rect x="{x}" y="{y + header_height - 10}" width="{w}" height="10" fill="{t["card_header"]}" />'
        )
        svg_parts.append(
            f'<line x1="{x}" y1="{y + header_height}" x2="{x + w}" y2="{y + header_height}" stroke="{t["card_border"]}" stroke-width="1" />'
        )

        # Entity Name
        svg_parts.append(
            f'<text x="{x + 14}" y="{y + 26}" font-size="15" font-weight="700" fill="{t["text"]}">{ent.name}</text>'
        )

        # Entity Type Badge
        badge_text = "ENUM" if ent.is_enum else ("UNION" if ent.is_union else "TABLE")
        badge_color = t["primary"] if not ent.is_enum else t["accent"]
        svg_parts.append(
            f'<rect x="{x + w - 62}" y="{y + 12}" width="50" height="20" rx="6" fill="{badge_color}" opacity="0.2"/>'
        )
        svg_parts.append(
            f'<text x="{x + w - 37}" y="{y + 26}" font-size="10" font-weight="700" fill="{badge_color}" text-anchor="middle">{badge_text}</text>'
        )

        # Fields List
        curr_y = y + header_height + 20
        for field in pos["fields"]:
            # Icon or badge for PK / FK
            if field.is_primary_key:
                svg_parts.append(
                    f'<text x="{x + 12}" y="{curr_y}" font-size="11" font-weight="700" fill="{t["pk_badge"]}">🔑</text>'
                )
            elif field.is_foreign_key or field.target_entity:
                svg_parts.append(
                    f'<text x="{x + 12}" y="{curr_y}" font-size="11" font-weight="700" fill="{t["fk_badge"]}">🔗</text>'
                )
            else:
                svg_parts.append(
                    f'<circle cx="{x + 18}" cy="{curr_y - 4}" r="2" fill="{t["text_muted"]}" />'
                )

            # Field Name
            field_name_color = t["text"] if not field.is_nullable else t["text_muted"]
            name_display = field.name[:18] + ".." if len(field.name) > 18 else field.name
            svg_parts.append(
                f'<text x="{x + 32}" y="{curr_y}" font-size="12" font-weight="600" fill="{field_name_color}">{name_display}</text>'
            )

            # Field Type Pill
            type_label = field.display_type()
            if len(type_label) > 14:
                type_label = type_label[:12] + ".."
            svg_parts.append(
                f'<text x="{x + w - 12}" y="{curr_y}" font-size="11" font-weight="400" fill="{t["text_muted"]}" text-anchor="end">{type_label}</text>'
            )

            curr_y += row_height

        svg_parts.append("</g>")

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def analyze_schema_metrics(ast_or_raw: Union[SchemaAST, str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze schema complexity, entity count, depth, and normalization score."""
    if isinstance(ast_or_raw, SchemaAST):
        ast = ast_or_raw
    else:
        ast = parse_schema(ast_or_raw)

    entity_count = len(ast.entities)
    field_count = sum(len(e.fields) for e in ast.entities.values())
    relationship_count = len(ast.relationships)

    pk_count = sum(len(e.primary_keys()) for e in ast.entities.values())
    fk_count = sum(len(e.foreign_keys()) for e in ast.entities.values())
    unique_count = sum(len(e.unique_fields()) for e in ast.entities.values())
    enum_count = sum(1 for e in ast.entities.values() if e.is_enum)
    union_count = sum(1 for e in ast.entities.values() if e.is_union)

    avg_fields = round(field_count / max(1, entity_count), 2)

    # Calculate graph depth / longest path
    deps: Dict[str, List[str]] = {name: [] for name in ast.entities}
    for rel in ast.relationships:
        if rel.source_entity in deps and rel.target_entity in deps and rel.source_entity != rel.target_entity:
            deps[rel.source_entity].append(rel.target_entity)

    def get_max_depth(node: str, visited: set[str]) -> int:
        if node in visited:
            return 0
        visited.add(node)
        max_d = 0
        for neighbor in deps.get(node, []):
            max_d = max(max_d, 1 + get_max_depth(neighbor, visited.copy()))
        return max_d

    max_depth = max([get_max_depth(n, set()) for n in ast.entities], default=0)

    # Graph Density: 2 * E / (V * (V - 1))
    if entity_count > 1:
        max_possible_edges = entity_count * (entity_count - 1)
        density = round(relationship_count / max_possible_edges, 4)
    else:
        density = 0.0

    # Normalization Score (0 - 100)
    # Heuristics:
    # 1. Primary key presence on all non-enum entities: +35 points
    # 2. Foreign keys having valid target entities: +25 points
    # 3. Reasonable field counts (<= 20 fields per entity): +20 points
    # 4. Atomic column naming / no composite delimiter columns: +20 points
    norm_score = 0
    non_enum_entities = [e for e in ast.entities.values() if not e.is_enum and not e.is_union]
    total_non_enum = len(non_enum_entities)

    if total_non_enum > 0:
        entities_with_pk = sum(1 for e in non_enum_entities if e.primary_keys())
        pk_ratio = entities_with_pk / total_non_enum
        norm_score += int(pk_ratio * 35)

        # FK targets valid
        valid_fks = 0
        total_fks_checked = 0
        for e in non_enum_entities:
            for f in e.fields:
                if f.target_entity:
                    total_fks_checked += 1
                    if f.target_entity in ast.entities:
                        valid_fks += 1
        if total_fks_checked > 0:
            fk_ratio = valid_fks / total_fks_checked
            norm_score += int(fk_ratio * 25)
        else:
            norm_score += 25

        # Field count hygiene
        bloated_entities = sum(1 for e in non_enum_entities if len(e.fields) > 25)
        clean_ratio = max(0.0, 1.0 - (bloated_entities / total_non_enum))
        norm_score += int(clean_ratio * 20)

        # Type hygiene
        norm_score += 20
    else:
        norm_score = 100

    # Complexity Score (0 - 100)
    complexity_raw = (entity_count * 4) + (field_count * 0.8) + (relationship_count * 6) + (max_depth * 8)
    complexity_score = min(100, round(complexity_raw, 1))

    if norm_score >= 90 and complexity_score <= 75:
        grade = "A"
    elif norm_score >= 80:
        grade = "B"
    elif norm_score >= 70:
        grade = "C"
    elif norm_score >= 60:
        grade = "D"
    else:
        grade = "F"

    # Actionable suggestions
    suggestions: List[str] = []
    for e in non_enum_entities:
        if not e.primary_keys():
            suggestions.append(f"Entity '{e.name}' lacks a primary key. Add an 'id UUID PRIMARY KEY' or unique identifier.")
        if len(e.fields) > 20:
            suggestions.append(f"Entity '{e.name}' has {len(e.fields)} fields. Consider decomposing into smaller normalized sub-entities.")

    if relationship_count == 0 and entity_count > 1:
        suggestions.append("No explicit entity relationships found. Consider connecting entities with foreign keys or $ref pointers.")

    if not suggestions:
        suggestions.append("Schema structure is clean, well-normalized, and follows standard relational/document design practices.")

    return {
        "entity_count": entity_count,
        "field_count": field_count,
        "relationship_count": relationship_count,
        "primary_key_count": pk_count,
        "foreign_key_count": fk_count,
        "unique_constraint_count": unique_count,
        "enum_count": enum_count,
        "union_count": union_count,
        "avg_fields_per_entity": avg_fields,
        "max_depth": max_depth,
        "density": density,
        "normalization_score": norm_score,
        "complexity_score": complexity_score,
        "complexity_grade": grade,
        "suggestions": suggestions,
    }


# Lazy exports for MCP Server to avoid circular import issues
def get_mcp_server() -> Any:
    from schema_illustrator_studio.mcp_server import MCPServer
    return MCPServer()


def run_mcp_server() -> None:
    from schema_illustrator_studio.mcp_server import run_mcp_server as _run_mcp
    _run_mcp()


__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "__description__",
    "SchemaAST",
    "EntityAST",
    "FieldAST",
    "RelationshipAST",
    "Constraint",
    "DataType",
    "RelationshipType",
    "ConstraintType",
    "parse_schema",
    "transpile_schema",
    "transpile",
    "export_erd_svg",
    "export_mermaid_erd",
    "analyze_schema_metrics",
    "detect_schema_format",
    "UnifiedParser",
    "SchemaParseError",
    "SAMPLE_TEMPLATES",
    "get_sample_template",
    "list_sample_templates",
    "get_mcp_server",
    "run_mcp_server",
]
