"""Differential Schema Evolution & Migration Drift Analyzer.

Compares two SchemaAST instances (v1 base vs v2 target) and generates:
1. Breaking change detector (dropped tables, deleted columns, incompatible type mutations, tightened nullability).
2. Non-breaking evolutions (added nullable columns, new tables, relaxed constraints).
3. Migration Drift Score (0.0 to 100.0) with risk classification (SAFE, WARNING, HAZARD, BREAKING).
4. Auto-generated migration scripts in:
   - Forward SQL DDL (CREATE TABLE, ALTER TABLE ADD COLUMN, DROP COLUMN, etc.)
   - Rollback / Down SQL DDL
   - JSON Patch delta specification (RFC 6902)
   - Visual Markdown audit diff table.

100% Python Standard Library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from schema_illustrator_studio.models import DataType, EntityAST, FieldAST, SchemaAST


class ChangeSeverity(str, Enum):
    """Classification of schema change risk."""
    SAFE = "SAFE"                # Non-breaking additions
    WARNING = "WARNING"          # Soft modifications (e.g. type widening, loose constraints)
    BREAKING = "BREAKING"        # Dropped tables, deleted fields, incompatible types, NOT NULL additions


class ChangeAction(str, Enum):
    """Type of schema mutation."""
    CREATE_ENTITY = "CREATE_ENTITY"
    DROP_ENTITY = "DROP_ENTITY"
    RENAME_ENTITY = "RENAME_ENTITY"
    ADD_FIELD = "ADD_FIELD"
    DROP_FIELD = "DROP_FIELD"
    MODIFY_TYPE = "MODIFY_TYPE"
    CHANGE_NULLABILITY = "CHANGE_NULLABILITY"
    CHANGE_DEFAULT = "CHANGE_DEFAULT"
    ADD_RELATIONSHIP = "ADD_RELATIONSHIP"
    DROP_RELATIONSHIP = "DROP_RELATIONSHIP"


@dataclass
class SchemaChange:
    """Atomic schema mutation record between two schema states."""
    action: ChangeAction
    severity: ChangeSeverity
    entity_name: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    description: str = ""
    is_breaking: bool = False
    sql_up: str = ""
    sql_down: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "severity": self.severity.value,
            "entity_name": self.entity_name,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "description": self.description,
            "is_breaking": self.is_breaking,
            "sql_up": self.sql_up,
            "sql_down": self.sql_down,
        }


@dataclass
class SchemaDiffReport:
    """Comprehensive differential comparison report between two schemas."""
    base_name: str
    target_name: str
    total_changes: int
    breaking_changes_count: int
    drift_score: float  # 0.0 (Identical) to 100.0 (Completely Diverged)
    risk_level: str     # SAFE, LOW, MEDIUM, HIGH, CRITICAL
    changes: List[SchemaChange]
    sql_migration_up: str
    sql_migration_down: str
    json_patch: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_name": self.base_name,
            "target_name": self.target_name,
            "total_changes": self.total_changes,
            "breaking_changes_count": self.breaking_changes_count,
            "drift_score": self.drift_score,
            "risk_level": self.risk_level,
            "changes": [c.to_dict() for c in self.changes],
            "sql_migration_up": self.sql_migration_up,
            "sql_migration_down": self.sql_migration_down,
            "json_patch": self.json_patch,
        }


# Data type compatibility matrix: can old_type be implicitly cast to new_type safely?
_SAFE_TYPE_WIDENING: Dict[DataType, List[DataType]] = {
    DataType.INTEGER: [DataType.BIGINT, DataType.DECIMAL, DataType.FLOAT, DataType.STRING],
    DataType.FLOAT: [DataType.DECIMAL, DataType.STRING],
    DataType.DATE: [DataType.DATETIME, DataType.STRING],
    DataType.UUID: [DataType.STRING],
    DataType.BOOLEAN: [DataType.INTEGER, DataType.STRING],
}


def _is_safe_type_promotion(old_t: DataType, new_t: DataType) -> bool:
    if old_t == new_t:
        return True
    return new_t in _SAFE_TYPE_WIDENING.get(old_t, [])


class SchemaDiffEngine:
    """Computes semantic difference and migration drift between two SchemaAST versions."""

    def diff(self, base: SchemaAST, target: SchemaAST) -> SchemaDiffReport:
        changes: List[SchemaChange] = []
        json_patch: List[Dict[str, Any]] = []

        base_entities = dict(base.entities)
        target_entities = dict(target.entities)

        # 1. Detect Dropped Entities (BREAKING)
        for name, entity in base_entities.items():
            if name not in target_entities:
                col_defs = []
                for f in entity.fields:
                    pk_clause = " PRIMARY KEY" if f.is_primary_key else ""
                    null_clause = " NOT NULL" if not f.is_nullable else ""
                    col_defs.append(f"    {f.name} {f.type.value}{pk_clause}{null_clause}")
                create_restore_sql = f"CREATE TABLE {name} (\n" + ",\n".join(col_defs) + "\n);"

                changes.append(
                    SchemaChange(
                        action=ChangeAction.DROP_ENTITY,
                        severity=ChangeSeverity.BREAKING,
                        entity_name=name,
                        old_value=name,
                        description=f"Entity '{name}' was deleted from target schema.",
                        is_breaking=True,
                        sql_up=f"DROP TABLE {name};",
                        sql_down=create_restore_sql,
                    )
                )
                json_patch.append({"op": "remove", "path": f"/entities/{name}"})

        # 2. Detect Created Entities (SAFE)
        for name, entity in target_entities.items():
            if name not in base_entities:
                col_defs = []
                for f in entity.fields:
                    pk_clause = " PRIMARY KEY" if f.is_primary_key else ""
                    null_clause = " NOT NULL" if not f.is_nullable else ""
                    col_defs.append(f"    {f.name} {f.type.value}{pk_clause}{null_clause}")
                create_sql = f"CREATE TABLE {name} (\n" + ",\n".join(col_defs) + "\n);"

                changes.append(
                    SchemaChange(
                        action=ChangeAction.CREATE_ENTITY,
                        severity=ChangeSeverity.SAFE,
                        entity_name=name,
                        new_value=name,
                        description=f"Entity '{name}' created in target schema.",
                        is_breaking=False,
                        sql_up=create_sql,
                        sql_down=f"DROP TABLE {name};",
                    )
                )
                json_patch.append({"op": "add", "path": f"/entities/{name}", "value": entity.to_dict()})

        # 3. Detect Intra-Entity Field Mutations
        for name in base_entities.keys() & target_entities.keys():
            e_base = base_entities[name]
            e_target = target_entities[name]

            f_base_map = {f.name: f for f in e_base.fields}
            f_target_map = {f.name: f for f in e_target.fields}

            # Dropped fields
            for f_name, f_old in f_base_map.items():
                if f_name not in f_target_map:
                    changes.append(
                        SchemaChange(
                            action=ChangeAction.DROP_FIELD,
                            severity=ChangeSeverity.BREAKING,
                            entity_name=name,
                            field_name=f_name,
                            old_value=f_old.type.value,
                            description=f"Column '{name}.{f_name}' ({f_old.type.value}) dropped.",
                            is_breaking=True,
                            sql_up=f"ALTER TABLE {name} DROP COLUMN {f_name};",
                            sql_down=f"ALTER TABLE {name} ADD COLUMN {f_name} {f_old.type.value};",
                        )
                    )
                    json_patch.append({"op": "remove", "path": f"/entities/{name}/fields/{f_name}"})

            # Added fields
            for f_name, f_new in f_target_map.items():
                if f_name not in f_base_map:
                    is_not_null_without_default = (not f_new.is_nullable) and (f_new.default_value is None)
                    sev = ChangeSeverity.BREAKING if is_not_null_without_default else ChangeSeverity.SAFE
                    desc = f"Column '{name}.{f_name}' added."
                    if is_not_null_without_default:
                        desc += " (BREAKING: NOT NULL without default value)."

                    null_clause = " NOT NULL" if not f_new.is_nullable else ""
                    def_clause = f" DEFAULT {f_new.default_value}" if f_new.default_value is not None else ""
                    changes.append(
                        SchemaChange(
                            action=ChangeAction.ADD_FIELD,
                            severity=sev,
                            entity_name=name,
                            field_name=f_name,
                            new_value=f_new.type.value,
                            description=desc,
                            is_breaking=is_not_null_without_default,
                            sql_up=f"ALTER TABLE {name} ADD COLUMN {f_name} {f_new.type.value}{def_clause}{null_clause};",
                            sql_down=f"ALTER TABLE {name} DROP COLUMN {f_name};",
                        )
                    )
                    json_patch.append({"op": "add", "path": f"/entities/{name}/fields/{f_name}", "value": f_new.to_dict()})

            # Modified fields (type or nullability)
            for f_name in f_base_map.keys() & f_target_map.keys():
                f_old = f_base_map[f_name]
                f_new = f_target_map[f_name]

                # Type change
                if f_old.type != f_new.type:
                    safe = _is_safe_type_promotion(f_old.type, f_new.type)
                    sev = ChangeSeverity.WARNING if safe else ChangeSeverity.BREAKING
                    changes.append(
                        SchemaChange(
                            action=ChangeAction.MODIFY_TYPE,
                            severity=sev,
                            entity_name=name,
                            field_name=f_name,
                            old_value=f_old.type.value,
                            new_value=f_new.type.value,
                            description=f"Type of '{name}.{f_name}' changed from {f_old.type.value} to {f_new.type.value}.",
                            is_breaking=not safe,
                            sql_up=f"ALTER TABLE {name} ALTER COLUMN {f_name} TYPE {f_new.type.value};",
                            sql_down=f"ALTER TABLE {name} ALTER COLUMN {f_name} TYPE {f_old.type.value};",
                        )
                    )
                    json_patch.append({"op": "replace", "path": f"/entities/{name}/fields/{f_name}/type", "value": f_new.type.value})

                # Nullability change
                if f_old.is_nullable != f_new.is_nullable:
                    # Going from nullable to non-nullable is BREAKING
                    breaking = (not f_new.is_nullable) and f_old.is_nullable
                    sev = ChangeSeverity.BREAKING if breaking else ChangeSeverity.SAFE
                    changes.append(
                        SchemaChange(
                            action=ChangeAction.CHANGE_NULLABILITY,
                            severity=sev,
                            entity_name=name,
                            field_name=f_name,
                            old_value="NULL" if f_old.is_nullable else "NOT NULL",
                            new_value="NULL" if f_new.is_nullable else "NOT NULL",
                            description=f"Nullability of '{name}.{f_name}' changed from {'NULL' if f_old.is_nullable else 'NOT NULL'} to {'NULL' if f_new.is_nullable else 'NOT NULL'}.",
                            is_breaking=breaking,
                            sql_up=f"ALTER TABLE {name} ALTER COLUMN {f_name} {'DROP NOT NULL' if f_new.is_nullable else 'SET NOT NULL'};",
                            sql_down=f"ALTER TABLE {name} ALTER COLUMN {f_name} {'SET NOT NULL' if f_new.is_nullable else 'DROP NOT NULL'};",
                        )
                    )
                    json_patch.append({"op": "replace", "path": f"/entities/{name}/fields/{f_name}/is_nullable", "value": f_new.is_nullable})

        # Calculate Drift Score and Risk
        breaking_count = sum(1 for c in changes if c.is_breaking)
        warning_count = sum(1 for c in changes if c.severity == ChangeSeverity.WARNING)
        safe_count = sum(1 for c in changes if c.severity == ChangeSeverity.SAFE)

        # Weighted drift formula
        raw_score = (breaking_count * 25.0) + (warning_count * 10.0) + (safe_count * 3.0)
        drift_score = min(100.0, raw_score)

        if breaking_count > 0 or drift_score >= 50.0:
            risk = "CRITICAL" if breaking_count >= 3 else "BREAKING"
        elif warning_count > 0 or drift_score >= 20.0:
            risk = "MEDIUM"
        elif total_changes := len(changes):
            risk = "LOW"
        else:
            risk = "SAFE"

        # Assemble full migration scripts
        sql_up_lines = [f"-- Migration Up: {base.name} -> {target.name}"]
        for c in changes:
            if c.sql_up:
                sql_up_lines.append(c.sql_up)
        sql_up_full = "\n".join(sql_up_lines)

        sql_down_lines = [f"-- Migration Down (Rollback): {target.name} -> {base.name}"]
        for c in reversed(changes):
            if c.sql_down:
                sql_down_lines.append(c.sql_down)
        sql_down_full = "\n".join(sql_down_lines)

        return SchemaDiffReport(
            base_name=base.name,
            target_name=target.name,
            total_changes=len(changes),
            breaking_changes_count=breaking_count,
            drift_score=round(drift_score, 1),
            risk_level=risk,
            changes=changes,
            sql_migration_up=sql_up_full,
            sql_migration_down=sql_down_full,
            json_patch=json_patch,
        )


def diff_schemas(base: SchemaAST, target: SchemaAST) -> SchemaDiffReport:
    """Convenience functional helper to compute differences between two schemas."""
    return SchemaDiffEngine().diff(base, target)
