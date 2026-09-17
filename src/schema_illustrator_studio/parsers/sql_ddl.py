"""SQL DDL schema parser converting SQL table definitions into unified SchemaAST.

Supports PostgreSQL, SQLite, MySQL, and standard ANSI SQL dialects including
CREATE TABLE, ALTER TABLE, CREATE TYPE AS ENUM, COMMENT ON, foreign keys,
composite keys, and inline constraints using 100% Python standard library.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

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


class SQLDDLParser:
    """Parser for SQL DDL scripts."""

    def __init__(self, ddl_text: str) -> None:
        self.raw_text = ddl_text
        self.ast = SchemaAST(name="SQL_Schema")

    def parse(self) -> SchemaAST:
        """Parse the SQL DDL text into SchemaAST."""
        cleaned_text = self._strip_comments(self.raw_text)
        statements = self._split_statements(cleaned_text)

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            normalized = re.sub(r"\s+", " ", stmt)
            upper_prefix = normalized[:30].upper()

            if upper_prefix.startswith("CREATE TYPE") and "ENUM" in upper_prefix:
                self._parse_create_type_enum(stmt)
            elif upper_prefix.startswith("CREATE TABLE") or "CREATE TABLE" in upper_prefix:
                self._parse_create_table(stmt)
            elif upper_prefix.startswith("ALTER TABLE"):
                self._parse_alter_table(stmt)
            elif upper_prefix.startswith("COMMENT ON"):
                self._parse_comment(stmt)

        if not self.ast.entities and self.raw_text.strip():
            from schema_illustrator_studio.parsers.unified import SchemaParseError

            raise SchemaParseError("No valid SQL CREATE TABLE or CREATE TYPE statements found in input.")

        # Infer relationships
        self.ast.infer_relationships()
        return self.ast

    def _strip_comments(self, sql: str) -> str:
        """Strip SQL block and line comments."""
        # Block comments /* ... */
        sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
        # Line comments -- ...
        lines = []
        for line in sql.splitlines():
            in_quote = False
            quote_char = ""
            clean_line = []
            i = 0
            while i < len(line):
                c = line[i]
                if c in ("'", '"', "`"):
                    if not in_quote:
                        in_quote = True
                        quote_char = c
                    elif quote_char == c:
                        in_quote = False
                if not in_quote and i + 1 < len(line) and line[i : i + 2] == "--":
                    break
                clean_line.append(c)
                i += 1
            lines.append("".join(clean_line))
        return "\n".join(lines)

    def _split_statements(self, sql: str) -> List[str]:
        """Split SQL into individual statements by semicolon, ignoring semicolons in quotes/parentheses."""
        statements: List[str] = []
        curr: List[str] = []
        in_single_quote = False
        in_double_quote = False
        paren_depth = 0

        for char in sql:
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif char == "(" and not in_single_quote and not in_double_quote:
                paren_depth += 1
            elif char == ")" and not in_single_quote and not in_double_quote:
                paren_depth = max(0, paren_depth - 1)
            elif char == ";" and not in_single_quote and not in_double_quote and paren_depth == 0:
                stmt = "".join(curr).strip()
                if stmt:
                    statements.append(stmt)
                curr = []
                continue
            curr.append(char)

        if curr:
            stmt = "".join(curr).strip()
            if stmt:
                statements.append(stmt)

        return statements

    def _clean_identifier(self, identifier: str) -> str:
        """Strip quotes, backticks, and schema prefixes from an SQL identifier."""
        identifier = identifier.strip().strip(";").strip()
        identifier = re.sub(r'^["`\[]|["`\]]$', "", identifier)
        if "." in identifier:
            parts = identifier.split(".")
            identifier = parts[-1]
            identifier = re.sub(r'^["`\[]|["`\]]$', "", identifier)
        return identifier

    def _parse_create_type_enum(self, stmt: str) -> None:
        """Parse CREATE TYPE name AS ENUM ('val1', 'val2', ...)."""
        match = re.search(
            r"CREATE\s+TYPE\s+([\w\.\"`]+)\s+AS\s+ENUM\s*\(([\s\S]*?)\)",
            stmt,
            re.IGNORECASE,
        )
        if not match:
            return
        name = self._clean_identifier(match.group(1))
        values_str = match.group(2)
        raw_values = re.findall(r"'([^']*)'", values_str)

        entity = EntityAST(name=name, is_enum=True)
        for val in raw_values:
            entity.fields.append(
                FieldAST(
                    name=val,
                    type=DataType.STRING,
                    raw_type="ENUM_VAL",
                    default_value=val,
                    is_nullable=False,
                )
            )
        self.ast.add_entity(entity)

    def _parse_create_table(self, stmt: str) -> None:
        """Parse CREATE TABLE statement."""
        match = re.search(
            r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([\w\.\"`\[\]]+)\s*\(([\s\S]*)\)",
            stmt,
            re.IGNORECASE,
        )
        if not match:
            return

        table_name = self._clean_identifier(match.group(1))
        body = match.group(2).strip()

        entity = EntityAST(name=table_name)

        items = self._split_top_level_commas(body)

        for item in items:
            item = item.strip()
            if not item:
                continue
            upper_item = re.sub(r"\s+", " ", item.upper())

            if upper_item.startswith("CONSTRAINT") or upper_item.startswith("PRIMARY KEY") or upper_item.startswith("FOREIGN KEY") or upper_item.startswith("UNIQUE") or upper_item.startswith("CHECK"):
                self._parse_table_constraint(entity, item)
            else:
                field_ast = self._parse_column_def(table_name, item)
                if field_ast:
                    entity.add_field(field_ast)

        self.ast.add_entity(entity)

    def _split_top_level_commas(self, text: str) -> List[str]:
        """Split string by comma only when not inside parentheses or quotes."""
        parts: List[str] = []
        curr: List[str] = []
        paren_depth = 0
        in_single_quote = False
        in_double_quote = False

        for char in text:
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif char == "(" and not in_single_quote and not in_double_quote:
                paren_depth += 1
            elif char == ")" and not in_single_quote and not in_double_quote:
                paren_depth = max(0, paren_depth - 1)
            elif char == "," and paren_depth == 0 and not in_single_quote and not in_double_quote:
                parts.append("".join(curr))
                curr = []
                continue
            curr.append(char)

        if curr:
            parts.append("".join(curr))

        return parts

    def _parse_column_def(self, table_name: str, col_def: str) -> Optional[FieldAST]:
        """Parse a single column definition line."""
        tokens = col_def.strip().split()
        if len(tokens) < 2:
            return None

        raw_name = tokens[0]
        col_name = self._clean_identifier(raw_name)

        rest = " ".join(tokens[1:]).strip()

        type_match = re.match(r"^([\w]+(?:\s+WITH(?:OUT)?\s+TIME\s+ZONE|\s+PRECISION)?(?:\s*\([^)]*\))?(?:\[\])?)", rest, re.IGNORECASE)
        if not type_match:
            raw_type_str = tokens[1]
            clause_str = " ".join(tokens[2:])
        else:
            raw_type_str = type_match.group(1).strip()
            clause_str = rest[len(raw_type_str) :].strip()

        data_type, is_array = self._map_sql_type(raw_type_str)

        field_ast = FieldAST(
            name=col_name,
            type=data_type,
            raw_type=raw_type_str,
            is_nullable=True,
            is_array=is_array,
        )

        upper_clauses = f" {clause_str.upper()} "

        # PRIMARY KEY
        if " PRIMARY KEY" in upper_clauses:
            field_ast.is_primary_key = True
            field_ast.is_nullable = False

        # NOT NULL vs NULL
        if " NOT NULL" in upper_clauses:
            field_ast.is_nullable = False
        elif " NULL" in upper_clauses and " NOT NULL" not in upper_clauses:
            field_ast.is_nullable = True

        # UNIQUE
        if " UNIQUE" in upper_clauses:
            field_ast.is_unique = True

        # AUTO_INCREMENT / SERIAL
        if "AUTO_INCREMENT" in upper_clauses or "SERIAL" in raw_type_str.upper() or "IDENTITY" in upper_clauses:
            field_ast.metadata["auto_increment"] = True

        # DEFAULT
        def_match = re.search(r"DEFAULT\s+([^,\s\)]+|'[^']*'|\([^\)]*\))", clause_str, re.IGNORECASE)
        if def_match:
            default_raw = def_match.group(1).strip("'")
            field_ast.default_value = default_raw
            field_ast.constraints.append(
                Constraint(type=ConstraintType.DEFAULT, expression=default_raw)
            )

        # INLINE REFERENCES target_table(target_col)
        ref_match = re.search(
            r"REFERENCES\s+([\w\.\"`\[\]]+)(?:\s*\(([\w\.\"`\[\]]+)\))?(?:\s+ON\s+DELETE\s+([A-Z\s]+))?",
            clause_str,
            re.IGNORECASE,
        )
        if ref_match:
            target_table = self._clean_identifier(ref_match.group(1))
            target_col = self._clean_identifier(ref_match.group(2)) if ref_match.group(2) else "id"
            on_delete = ref_match.group(3).strip() if ref_match.group(3) else None

            field_ast.is_foreign_key = True
            field_ast.target_entity = target_table
            field_ast.target_field = target_col

            rel = RelationshipAST(
                name=f"{table_name}_{col_name}_{target_table}",
                source_entity=table_name,
                source_field=col_name,
                target_entity=target_table,
                target_field=target_col,
                relation_type=RelationshipType.ONE_TO_ONE if field_ast.is_unique else RelationshipType.MANY_TO_ONE,
                cardinality="1:1" if field_ast.is_unique else "N:1",
                on_delete=on_delete,
            )
            self.ast.add_relationship(rel)

        return field_ast

    def _parse_table_constraint(self, entity: EntityAST, clause: str) -> None:
        """Parse table-level constraint definition."""
        norm = re.sub(r"\s+", " ", clause).strip()
        constraint_name: Optional[str] = None

        name_match = re.match(r"^CONSTRAINT\s+([\w\.\"`\[\]]+)\s+(.*)", norm, re.IGNORECASE)
        if name_match:
            constraint_name = self._clean_identifier(name_match.group(1))
            norm = name_match.group(2).strip()

        upper = norm.upper()

        # PRIMARY KEY (col1, col2, ...)
        pk_match = re.search(r"PRIMARY\s+KEY\s*\(([\s\S]*?)\)", norm, re.IGNORECASE)
        if pk_match:
            cols = [self._clean_identifier(c) for c in pk_match.group(1).split(",")]
            for col_name in cols:
                f = entity.get_field(col_name)
                if f:
                    f.is_primary_key = True
                    f.is_nullable = False
            entity.constraints.append(
                Constraint(
                    type=ConstraintType.PRIMARY_KEY,
                    name=constraint_name,
                    parameters={"columns": cols},
                )
            )
            return

        # FOREIGN KEY (col) REFERENCES target (target_col)
        fk_match = re.search(
            r"FOREIGN\s+KEY\s*\(([\s\S]*?)\)\s*REFERENCES\s+([\w\.\"`\[\]]+)\s*(?:\(([\s\S]*?)\))?(?:\s+ON\s+DELETE\s+([A-Za-z\s]+))?",
            norm,
            re.IGNORECASE,
        )
        if fk_match:
            src_cols = [self._clean_identifier(c) for c in fk_match.group(1).split(",")]
            target_table = self._clean_identifier(fk_match.group(2))
            tgt_cols_raw = fk_match.group(3)
            tgt_cols = [self._clean_identifier(c) for c in tgt_cols_raw.split(",")] if tgt_cols_raw else ["id"]
            on_delete = fk_match.group(4).strip() if fk_match.group(4) else None

            for i, src_col in enumerate(src_cols):
                tgt_col = tgt_cols[i] if i < len(tgt_cols) else tgt_cols[0]
                f = entity.get_field(src_col)
                if f:
                    f.is_foreign_key = True
                    f.target_entity = target_table
                    f.target_field = tgt_col

                rel = RelationshipAST(
                    name=constraint_name or f"{entity.name}_{src_col}_{target_table}",
                    source_entity=entity.name,
                    source_field=src_col,
                    target_entity=target_table,
                    target_field=tgt_col,
                    relation_type=RelationshipType.ONE_TO_ONE if (f and f.is_unique) else RelationshipType.MANY_TO_ONE,
                    cardinality="1:1" if (f and f.is_unique) else "N:1",
                    on_delete=on_delete,
                )
                self.ast.add_relationship(rel)

            entity.constraints.append(
                Constraint(
                    type=ConstraintType.FOREIGN_KEY,
                    name=constraint_name,
                    parameters={
                        "source_columns": src_cols,
                        "target_entity": target_table,
                        "target_columns": tgt_cols,
                        "on_delete": on_delete,
                    },
                )
            )
            return

        # UNIQUE (col1, col2)
        uq_match = re.search(r"UNIQUE\s*\(([\s\S]*?)\)", norm, re.IGNORECASE)
        if uq_match:
            cols = [self._clean_identifier(c) for c in uq_match.group(1).split(",")]
            for col_name in cols:
                f = entity.get_field(col_name)
                if f and len(cols) == 1:
                    f.is_unique = True
            entity.constraints.append(
                Constraint(
                    type=ConstraintType.UNIQUE,
                    name=constraint_name,
                    parameters={"columns": cols},
                )
            )
            return

        # CHECK (...)
        check_match = re.search(r"CHECK\s*\(([\s\S]*)\)", norm, re.IGNORECASE)
        if check_match:
            expr = check_match.group(1).strip()
            entity.constraints.append(
                Constraint(
                    type=ConstraintType.CHECK,
                    name=constraint_name,
                    expression=expr,
                )
            )

    def _parse_alter_table(self, stmt: str) -> None:
        """Parse ALTER TABLE statements that add foreign keys or constraints."""
        match = re.search(
            r"ALTER\s+TABLE\s+([\w\.\"`\[\]]+)\s+ADD(?:\s+CONSTRAINT\s+([\w\.\"`\[\]]+))?\s+FOREIGN\s+KEY\s*\(([\s\S]*?)\)\s*REFERENCES\s+([\w\.\"`\[\]]+)\s*(?:\(([\s\S]*?)\))?(?:\s+ON\s+DELETE\s+([A-Za-z\s]+))?",
            stmt,
            re.IGNORECASE,
        )
        if match:
            table_name = self._clean_identifier(match.group(1))
            constraint_name = self._clean_identifier(match.group(2)) if match.group(2) else ""
            src_col = self._clean_identifier(match.group(3))
            target_table = self._clean_identifier(match.group(4))
            tgt_col = self._clean_identifier(match.group(5)) if match.group(5) else "id"
            on_delete = match.group(6).strip() if match.group(6) else None

            entity = self.ast.get_entity(table_name)
            if entity:
                f = entity.get_field(src_col)
                if f:
                    f.is_foreign_key = True
                    f.target_entity = target_table
                    f.target_field = tgt_col

            rel = RelationshipAST(
                name=constraint_name or f"{table_name}_{src_col}_{target_table}",
                source_entity=table_name,
                source_field=src_col,
                target_entity=target_table,
                target_field=tgt_col,
                relation_type=RelationshipType.MANY_TO_ONE,
                cardinality="N:1",
                on_delete=on_delete,
            )
            self.ast.add_relationship(rel)

    def _parse_comment(self, stmt: str) -> None:
        """Parse COMMENT ON TABLE / COLUMN statements."""
        tbl_match = re.search(
            r"COMMENT\s+ON\s+TABLE\s+([\w\.\"`\[\]]+)\s+IS\s+'([^']*)'",
            stmt,
            re.IGNORECASE,
        )
        if tbl_match:
            table_name = self._clean_identifier(tbl_match.group(1))
            comment = tbl_match.group(2)
            entity = self.ast.get_entity(table_name)
            if entity:
                entity.description = comment
            return

        col_match = re.search(
            r"COMMENT\s+ON\s+COLUMN\s+([\w\.\"`\[\]]+)\.([\w\.\"`\[\]]+)\s+IS\s+'([^']*)'",
            stmt,
            re.IGNORECASE,
        )
        if col_match:
            table_name = self._clean_identifier(col_match.group(1))
            col_name = self._clean_identifier(col_match.group(2))
            comment = col_match.group(3)
            entity = self.ast.get_entity(table_name)
            if entity:
                f = entity.get_field(col_name)
                if f:
                    f.description = comment

    def _map_sql_type(self, raw_type: str) -> Tuple[DataType, bool]:
        """Map SQL type string to canonical DataType and is_array flag."""
        t = raw_type.upper().strip()
        is_array = t.endswith("[]") or "ARRAY" in t
        if is_array:
            t = t.replace("[]", "").replace("ARRAY", "").strip()

        base = re.sub(r"\s*\(.*?\)", "", t).strip()

        if base in ("VARCHAR", "CHAR", "TEXT", "NVARCHAR", "NCHAR", "CITEXT", "CHARACTER VARYING", "STRING", "MEDIUMTEXT", "LONGTEXT"):
            return (DataType.ARRAY if is_array else DataType.STRING), is_array
        if base in ("INT", "INTEGER", "SMALLINT", "TINYINT", "MEDIUMINT", "SERIAL", "SMALLSERIAL"):
            return (DataType.ARRAY if is_array else DataType.INTEGER), is_array
        if base in ("BIGINT", "BIGSERIAL", "INT8"):
            return (DataType.ARRAY if is_array else DataType.BIGINT), is_array
        if base in ("FLOAT", "DOUBLE", "REAL", "DOUBLE PRECISION", "FLOAT4", "FLOAT8"):
            return (DataType.ARRAY if is_array else DataType.FLOAT), is_array
        if base in ("DECIMAL", "NUMERIC", "MONEY", "NUMBER"):
            return (DataType.ARRAY if is_array else DataType.DECIMAL), is_array
        if base in ("BOOLEAN", "BOOL", "BIT"):
            return (DataType.ARRAY if is_array else DataType.BOOLEAN), is_array
        if "TIMESTAMP" in base or base in ("DATETIME",):
            return (DataType.ARRAY if is_array else DataType.DATETIME), is_array
        if base == "DATE":
            return (DataType.ARRAY if is_array else DataType.DATE), is_array
        if base in ("TIME", "TIMETZ"):
            return (DataType.ARRAY if is_array else DataType.TIME), is_array
        if base in ("UUID", "GUID"):
            return (DataType.ARRAY if is_array else DataType.UUID), is_array
        if base in ("JSON", "JSONB"):
            return DataType.JSON, False
        if base in ("BYTEA", "BLOB", "BINARY", "VARBINARY"):
            return DataType.BYTES, False

        return (DataType.ARRAY if is_array else DataType.STRING), is_array
