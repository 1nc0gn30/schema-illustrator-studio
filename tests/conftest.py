"""Pytest configuration, path setup, and shared fixtures for schema-illustrator-studio."""

import os
import sys
from pathlib import Path
import pytest

# Ensure src/ is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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


@pytest.fixture
def sample_sql_schema() -> str:
    """Sample PostgreSQL SQL DDL schema."""
    return """
    CREATE TABLE users (
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
    );
    """


@pytest.fixture
def sample_json_schema() -> str:
    """Sample JSON Schema (Draft 2020-12)."""
    return """{
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


@pytest.fixture
def sample_ts_schema() -> str:
    """Sample TypeScript interfaces schema."""
    return """
    export interface Organization {
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
    }
    """


@pytest.fixture
def sample_graphql_schema() -> str:
    """Sample GraphQL SDL schema."""
    return """
    type Profile {
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
    }
    """


@pytest.fixture
def sample_ast() -> SchemaAST:
    """Constructed rich SchemaAST object."""
    ast = SchemaAST(name="TestECommerce", version="1.0.0", description="E-Commerce AST")

    # User Entity
    user_ent = EntityAST(name="User", description="Registered users")
    user_ent.add_field(FieldAST(name="id", type=DataType.UUID, is_primary_key=True, is_nullable=False))
    user_ent.add_field(FieldAST(name="email", type=DataType.STRING, is_unique=True, is_nullable=False))
    user_ent.add_field(FieldAST(name="full_name", type=DataType.STRING, is_nullable=True))
    user_ent.add_field(FieldAST(name="is_active", type=DataType.BOOLEAN, default_value=True))
    ast.add_entity(user_ent)

    # Order Entity
    order_ent = EntityAST(name="Order", description="Customer orders")
    order_ent.add_field(FieldAST(name="id", type=DataType.UUID, is_primary_key=True, is_nullable=False))
    order_ent.add_field(
        FieldAST(
            name="user_id",
            type=DataType.UUID,
            is_foreign_key=True,
            is_nullable=False,
            target_entity="User",
            target_field="id",
        )
    )
    order_ent.add_field(FieldAST(name="total_amount", type=DataType.DECIMAL, is_nullable=False))
    order_ent.add_field(FieldAST(name="created_at", type=DataType.DATETIME, is_nullable=False))
    ast.add_entity(order_ent)

    # Relationship
    ast.add_relationship(
        RelationshipAST(
            name="Order_user_id_User",
            source_entity="Order",
            source_field="user_id",
            target_entity="User",
            target_field="id",
            relation_type=RelationshipType.MANY_TO_ONE,
            cardinality="N:1",
        )
    )

    return ast
