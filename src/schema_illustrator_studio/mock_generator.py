"""Deterministic Mock Data & Synthetic Seed Generator Engine.

Generates realistic, relational-referential synthetic mock datasets from a SchemaAST.
Topologically sorts tables to ensure foreign key dependencies are populated in order.
Produces standard SQL INSERT statements, JSON arrays, and CSV tables.
Zero external dependencies (100% Python Standard Library).
"""

from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from .models import ConstraintType, DataType, EntityAST, FieldAST, SchemaAST

# Realistic sample data pools
SAMPLE_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Sam",
    "Elena", "Marcus", "Chloe", "Julian", "Maya", "Lucas", "Sophia", "Liam",
]

SAMPLE_LAST_NAMES = [
    "Vance", "Kovacs", "Sterling", "Chen", "Patel", "Novak", "O'Connor", "Dubois",
    "Mercer", "Sinclair", "Hawthorne", "Tanaka", "Lindqvist", "Al-Mansoor", "Rossi", "Kim",
]

SAMPLE_DOMAINS = [
    "example.com", "acme.io", "techcorp.dev", "cloudnexus.org", "dataflow.net",
]

SAMPLE_TITLES = [
    "Lead Cloud Architect", "Senior Systems Engineer", "Principal AI Researcher",
    "Staff Product Designer", "DevOps Specialist", "Security Analyst", "VP Engineering",
]

SAMPLE_COMPANIES = [
    "Acme Dynamics", "CyberPulse Labs", "Synthetix Corp", "NovaTech Systems",
    "Apex Global", "Vanguard AI", "OmniData Solutions", "BlueSky Networks",
]

SAMPLE_CITIES = [
    "San Francisco", "London", "Tokyo", "Berlin", "New York", "Singapore",
    "Toronto", "Sydney", "Zurich", "Amsterdam",
]

SAMPLE_STATUSES = ["active", "pending", "completed", "suspended", "archived"]


@dataclass
class MockDataConfig:
    """Configuration options for synthetic mock data generation."""

    rows_per_entity: int = 5
    seed: int = 42
    include_nulls: bool = False
    null_ratio: float = 0.1
    default_format: str = "sql"  # 'sql', 'json', 'csv'
    custom_row_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class MockDataset:
    """Container for generated synthetic mock data across entities."""

    entities_data: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    generation_order: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return raw python dictionary representation."""
        return self.entities_data

    def to_json(self, indent: int = 2) -> str:
        """Format dataset as standard formatted JSON string."""
        return json.dumps(self.entities_data, indent=indent, default=str)

    def to_sql(self, dialect: str = "generic") -> str:
        """Format dataset as SQL INSERT statements."""
        statements: List[str] = []
        statements.append("-- Generated synthetic mock data by Schema Illustrator Studio")
        statements.append("-- Order respect foreign-key dependency hierarchy")
        statements.append("")

        for entity_name in self.generation_order:
            rows = self.entities_data.get(entity_name, [])
            if not rows:
                continue

            statements.append(f"-- Entity: {entity_name} ({len(rows)} rows)")
            columns = list(rows[0].keys())
            quoted_cols = [f'"{col}"' for col in columns]
            col_list_str = ", ".join(quoted_cols)

            for row in rows:
                val_strs: List[str] = []
                for col in columns:
                    val = row.get(col)
                    val_strs.append(_format_sql_value(val))
                row_str = f"INSERT INTO \"{entity_name}\" ({col_list_str}) VALUES ({', '.join(val_strs)});"
                statements.append(row_str)
            statements.append("")

        return "\n".join(statements)

    def to_csv_dict(self) -> Dict[str, str]:
        """Export each entity table as a CSV string dictionary."""
        result: Dict[str, str] = {}
        for entity_name, rows in self.entities_data.items():
            if not rows:
                result[entity_name] = ""
                continue
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for r in rows:
                # Format non-primitive types safely
                cleaned = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in r.items()}
                writer.writerow(cleaned)
            result[entity_name] = out.getvalue()
        return result


def _format_sql_value(val: Any) -> str:
    """Safely format a python value as an SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        escaped = json.dumps(val).replace("'", "''")
        return f"'{escaped}'"
    # String / Datetime / UUID
    s = str(val).replace("'", "''")
    return f"'{s}'"


def _topological_sort_entities(schema: SchemaAST) -> List[str]:
    """Compute topological ordering of entities based on foreign keys."""
    # Build graph: target_entity is parent of source_entity
    # in-degree: number of dependencies an entity has
    entities = [e.name for e in schema.entities.values() if not e.is_enum and not e.is_union]
    adj: Dict[str, Set[str]] = {e: set() for e in entities}
    in_degree: Dict[str, int] = {e: 0 for e in entities}

    # Gather dependencies from relationships and foreign keys
    for e in schema.entities.values():
        if e.name not in in_degree:
            continue
        for fk in e.foreign_keys():
            target = fk.target_entity
            if target and target in adj and target != e.name:
                if e.name not in adj[target]:
                    adj[target].add(e.name)
                    in_degree[e.name] += 1

    for rel in schema.relationships:
        src = rel.source_entity
        tgt = rel.target_entity
        if src in in_degree and tgt in adj and src != tgt:
            if src not in adj[tgt]:
                adj[tgt].add(src)
                in_degree[src] += 1

    # Kahn's algorithm
    queue = [e for e in entities if in_degree[e] == 0]
    ordered: List[str] = []

    while queue:
        curr = queue.pop(0)
        ordered.append(curr)
        for child in sorted(adj.get(curr, [])):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # Any remaining (due to circular references) get appended
    for e in entities:
        if e not in ordered:
            ordered.append(e)

    return ordered


def _synthesize_field_value(
    field: FieldAST,
    row_idx: int,
    rng: random.Random,
    generated_pks: Dict[str, Dict[str, List[Any]]],
) -> Any:
    """Generate a realistic mock value for a given field based on type and semantics."""
    fname = field.name.lower()
    dtype = field.type

    # 1. Foreign Key resolution
    if field.is_foreign_key and field.target_entity:
        target_ent = field.target_entity
        target_fld = field.target_field or "id"
        target_vals = generated_pks.get(target_ent, {}).get(target_fld, [])
        if target_vals:
            # Pick from available parent PKs
            return rng.choice(target_vals)

    # 2. Check if field has explicit enum constraints
    enum_vals = field.enum_values
    if enum_vals:
        return rng.choice(enum_vals)

    for c in field.constraints:
        if c.type == ConstraintType.ENUM_VALUES and "values" in c.parameters:
            return rng.choice(c.parameters["values"])

    # 3. Primary key special handling
    if field.is_primary_key:
        if dtype == DataType.UUID or "uuid" in fname:
            return f"550e8400-e29b-41d4-a716-{row_idx + 1:012d}"
        if dtype in (DataType.INTEGER, DataType.BIGINT):
            return row_idx + 1
        return f"pk_{row_idx + 1}"

    # 4. Semantic Heuristics by Name
    if "email" in fname:
        first = rng.choice(SAMPLE_FIRST_NAMES).lower()
        last = rng.choice(SAMPLE_LAST_NAMES).lower()
        domain = rng.choice(SAMPLE_DOMAINS)
        return f"{first}.{last}{row_idx + 1}@{domain}"

    if fname in ("username", "user_name", "handle", "login"):
        first = rng.choice(SAMPLE_FIRST_NAMES).lower()
        return f"{first}_{row_idx + 10}"

    if fname in ("name", "full_name", "display_name", "user"):
        return f"{rng.choice(SAMPLE_FIRST_NAMES)} {rng.choice(SAMPLE_LAST_NAMES)}"

    if fname in ("first_name", "firstname", "given_name"):
        return rng.choice(SAMPLE_FIRST_NAMES)

    if fname in ("last_name", "lastname", "surname", "family_name"):
        return rng.choice(SAMPLE_LAST_NAMES)

    if fname in ("title", "job_title", "role", "position"):
        return rng.choice(SAMPLE_TITLES)

    if fname in ("company", "organization", "org_name"):
        return rng.choice(SAMPLE_COMPANIES)

    if fname in ("city", "location", "town"):
        return rng.choice(SAMPLE_CITIES)

    if fname in ("status", "state"):
        return rng.choice(SAMPLE_STATUSES)

    if fname in ("url", "website", "link", "homepage"):
        return f"https://{rng.choice(SAMPLE_DOMAINS)}/{fname}/{row_idx + 1}"

    if "avatar" in fname or "image" in fname or "photo" in fname:
        return f"https://images.example.com/avatars/{row_idx + 1}.jpg"

    if fname in ("description", "bio", "about", "summary", "notes"):
        return f"Synthetic profile record {row_idx + 1} generated for demonstration purposes."

    if any(k in fname for k in ("price", "amount", "cost", "total", "balance", "fee", "rate")):
        return round(rng.uniform(10.0, 500.0), 2)

    if fname in ("quantity", "count", "inventory", "stock", "views", "clicks"):
        return rng.randint(1, 100)

    # 5. Type-Driven Fallback
    if dtype == DataType.UUID or "uuid" in fname:
        return f"a1b2c3d4-e5f6-7890-abcd-{row_idx + 1:012d}"

    if dtype == DataType.BOOLEAN or fname.startswith(("is_", "has_", "can_")):
        return rng.choice([True, False])

    if dtype in (DataType.INTEGER, DataType.BIGINT):
        return (row_idx + 1) * 10

    if dtype in (DataType.FLOAT, DataType.DECIMAL):
        return round(rng.uniform(1.0, 99.0), 2)

    if dtype in (DataType.DATETIME, DataType.DATE, DataType.TIME) or "at" in fname or "date" in fname:
        day = (row_idx % 28) + 1
        return f"2026-03-{day:02d}T12:00:00Z"

    if dtype == DataType.JSON:
        return {"id": row_idx + 1, "status": "ok", "tags": ["mock", "demo"]}

    if dtype == DataType.ARRAY:
        return ["tag_1", "tag_2"]

    # String fallback
    return f"{field.name}_{row_idx + 1}"


def generate_mock_data(
    schema: SchemaAST,
    config: Optional[MockDataConfig] = None,
) -> MockDataset:
    """Synthesize a complete relational mock dataset from a SchemaAST."""
    cfg = config or MockDataConfig()
    rng = random.Random(cfg.seed)

    ordered_entity_names = _topological_sort_entities(schema)
    entity_map = {e.name: e for e in schema.entities.values()}

    dataset = MockDataset(generation_order=ordered_entity_names)
    generated_pks: Dict[str, Dict[str, List[Any]]] = {}

    for ent_name in ordered_entity_names:
        ent = entity_map.get(ent_name)
        if not ent:
            continue

        num_rows = cfg.custom_row_counts.get(ent_name, cfg.rows_per_entity)
        rows: List[Dict[str, Any]] = []
        generated_pks[ent_name] = {}

        # Pre-initialize PK lists for this entity
        for pk in ent.primary_keys():
            generated_pks[ent_name][pk.name] = []

        for r_idx in range(num_rows):
            row: Dict[str, Any] = {}
            for field in ent.fields:
                # Handle nullability
                if cfg.include_nulls and field.is_nullable and not field.is_primary_key:
                    if rng.random() < cfg.null_ratio:
                        row[field.name] = None
                        continue

                val = _synthesize_field_value(field, r_idx, rng, generated_pks)
                row[field.name] = val

                if field.is_primary_key:
                    generated_pks[ent_name][field.name].append(val)

            rows.append(row)

        dataset.entities_data[ent_name] = rows

    return dataset
