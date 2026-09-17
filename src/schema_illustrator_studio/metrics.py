"""Schema quality metrics and architectural analysis engine.

Evaluates schema depth, complexity, circular dependencies, orphan tables,
missing primary keys, documentation coverage, naming convention consistency,
normalization heuristics, and computes a composite Quality Score (0-100)
using 100% Python standard library.
"""

from __future__ import annotations

import collections
import json
import re
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from schema_illustrator_studio.models import DataType, EntityAST, SchemaAST


class SchemaMetrics(dict):
    """Comprehensive quality metrics and insights for a SchemaAST.

    Inherits from dict for 100% native JSON serialization while providing
    full attribute-style and key-style access.
    """

    def __init__(self, **kwargs: Any) -> None:
        defaults: Dict[str, Any] = {
            "total_entities": 0,
            "entity_count": 0,
            "total_fields": 0,
            "field_count": 0,
            "total_relationships": 0,
            "relationship_count": 0,
            "avg_fields_per_entity": 0.0,
            "max_fields_in_entity": ("", 0),
            "primary_key_count": 0,
            "foreign_key_count": 0,
            "unique_constraint_count": 0,
            "enum_count": 0,
            "union_count": 0,
            "max_depth": 0,
            "max_dependency_depth": 0,
            "deepest_dependency_chain": [],
            "orphan_entities": [],
            "circular_dependencies": [],
            "tables_without_primary_key": [],
            "fields_without_description": 0,
            "documentation_coverage": 100.0,
            "naming_convention_issues": [],
            "normalization_warnings": [],
            "normalization_score": 100.0,
            "complexity_score": 0.0,
            "complexity_grade": "A",
            "density": 0.0,
            "quality_score": 100.0,
            "suggestions": [],
        }
        defaults.update(kwargs)
        super().__init__(defaults)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'SchemaMetrics' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return dict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert metrics to formatted JSON."""
        return json.dumps(self, indent=indent)

    def summary_markdown(self) -> str:
        """Generate human-readable Markdown summary report."""
        lines: List[str] = []
        score = self.get("quality_score", 100.0)
        grade = self.get("complexity_grade", "A")
        score_emoji = "🟢" if score >= 85 else ("🟡" if score >= 65 else "🔴")

        lines.append(f"## {score_emoji} Schema Quality Audit Report (Score: {score:.1f}/100 - Grade: {grade})")
        lines.append("")
        lines.append("### 📊 Architecture Overview")
        lines.append(f"- **Total Entities**: `{self.get('total_entities', 0)}`")
        lines.append(f"- **Total Fields**: `{self.get('total_fields', 0)}` (Avg: `{self.get('avg_fields_per_entity', 0.0):.1f}`/entity)")
        lines.append(f"- **Total Relationships**: `{self.get('total_relationships', 0)}`")
        lines.append(f"- **Documentation Coverage**: `{self.get('documentation_coverage', 100.0):.1f}%` ({self.get('fields_without_description', 0)} undocumented fields)")
        lines.append(f"- **Max Dependency Depth**: `{self.get('max_dependency_depth', 0)}`")
        chain = self.get("deepest_dependency_chain", [])
        if chain:
            lines.append(f"  - Chain: `{' -> '.join(chain)}`")
        lines.append("")

        lines.append("### 🔍 Diagnostics & Health Checks")

        no_pks = self.get("tables_without_primary_key", [])
        if no_pks:
            lines.append(f"- ⚠️ **Entities Missing Primary Key** ({len(no_pks)}):")
            for t in no_pks:
                lines.append(f"  - `{t}`")
        else:
            lines.append("- ✅ **All entities have valid Primary Keys**")

        circ = self.get("circular_dependencies", [])
        if circ:
            lines.append(f"- ⚠️ **Circular Dependencies Detected** ({len(circ)} cycles):")
            for cycle in circ:
                lines.append(f"  - `{' -> '.join(cycle)}`")
        else:
            lines.append("- ✅ **No circular dependencies detected (DAG verified)**")

        orphans = self.get("orphan_entities", [])
        if orphans:
            lines.append(f"- ℹ️ **Orphan Entities** (0 incoming/outgoing relations, {len(orphans)}):")
            for o in orphans:
                lines.append(f"  - `{o}`")

        naming = self.get("naming_convention_issues", [])
        if naming:
            lines.append(f"- ⚠️ **Naming Inconsistencies** ({len(naming)}):")
            for issue in naming[:5]:
                lines.append(f"  - `{issue['entity']}.{issue['field']}`: {issue['message']}")
            if len(naming) > 5:
                lines.append(f"  - *...and {len(naming) - 5} more.*")

        norms = self.get("normalization_warnings", [])
        if norms:
            lines.append(f"- 💡 **Normalization Recommendations** ({len(norms)}):")
            for norm in norms[:5]:
                lines.append(f"  - `{norm['entity']}`: {norm['message']}")
            if len(norms) > 5:
                lines.append(f"  - *...and {len(norms) - 5} more.*")

        return "\n".join(lines)


class SchemaAnalyzer:
    """Performs deep static analysis on SchemaAST."""

    def __init__(self, ast: SchemaAST) -> None:
        self.ast = ast

    def analyze(self) -> SchemaMetrics:
        """Run all quality checks and return SchemaMetrics."""
        m = SchemaMetrics()

        entities = [e for e in self.ast.entities.values() if not e.is_enum and not e.is_union]
        all_entities = list(self.ast.entities.values())

        m.total_entities = len(all_entities)
        m.entity_count = m.total_entities
        all_fields = [f for e in all_entities for f in e.fields]
        m.total_fields = len(all_fields)
        m.field_count = m.total_fields
        m.total_relationships = len(self.ast.relationships)
        m.relationship_count = m.total_relationships

        m.enum_count = sum(1 for e in all_entities if e.is_enum)
        m.union_count = sum(1 for e in all_entities if e.is_union)
        m.primary_key_count = sum(len(e.primary_keys()) for e in all_entities)
        m.foreign_key_count = sum(len(e.foreign_keys()) for e in all_entities)
        m.unique_constraint_count = sum(len(e.unique_fields()) for e in all_entities)

        if m.total_entities > 0:
            m.avg_fields_per_entity = round(m.total_fields / m.total_entities, 2)

        max_ent = max(all_entities, key=lambda e: len(e.fields), default=None)
        if max_ent:
            m.max_fields_in_entity = (max_ent.name, len(max_ent.fields))

        documented_fields = sum(1 for f in all_fields if f.description.strip())
        m.fields_without_description = m.total_fields - documented_fields
        if m.total_fields > 0:
            m.documentation_coverage = round((documented_fields / m.total_fields) * 100.0, 1)
        else:
            m.documentation_coverage = 100.0

        for ent in entities:
            if not ent.primary_keys():
                m.tables_without_primary_key.append(ent.name)

        adj: Dict[str, Set[str]] = collections.defaultdict(set)
        in_degree: Dict[str, int] = {e.name: 0 for e in all_entities}
        out_degree: Dict[str, int] = {e.name: 0 for e in all_entities}

        for rel in self.ast.relationships:
            if rel.source_entity in in_degree and rel.target_entity in in_degree:
                adj[rel.source_entity].add(rel.target_entity)
                out_degree[rel.source_entity] += 1
                in_degree[rel.target_entity] += 1

        for ent in all_entities:
            for f in ent.fields:
                if f.target_entity and f.target_entity in in_degree:
                    if f.target_entity not in adj[ent.name]:
                        adj[ent.name].add(f.target_entity)
                        out_degree[ent.name] += 1
                        in_degree[f.target_entity] += 1

        for ent in entities:
            if in_degree.get(ent.name, 0) == 0 and out_degree.get(ent.name, 0) == 0:
                m.orphan_entities.append(ent.name)

        m.circular_dependencies = self._find_cycles(adj)
        m.max_dependency_depth, m.deepest_dependency_chain = self._calculate_longest_chain(adj)
        m.max_depth = m.max_dependency_depth
        m.naming_convention_issues = self._check_naming_conventions(all_entities)
        m.normalization_warnings = self._check_normalization(entities)

        # Graph density
        n = m.total_entities
        if n > 1:
            m.density = round(m.total_relationships / (n * (n - 1)), 2)
        else:
            m.density = 0.0

        # Normalization Score (0-100)
        norm_deductions = len(m.normalization_warnings) * 5.0 + len(m.tables_without_primary_key) * 10.0
        m.normalization_score = round(max(0.0, min(100.0, 100.0 - norm_deductions)), 1)

        # Complexity Score (0-100)
        comp_score = (m.total_entities * 3.0) + (m.total_fields * 0.8) + (m.total_relationships * 5.0) + (m.max_dependency_depth * 8.0)
        m.complexity_score = round(min(100.0, comp_score), 1)

        # Complexity Grade
        if m.complexity_score < 30:
            m.complexity_grade = "A"
        elif m.complexity_score < 60:
            m.complexity_grade = "B"
        elif m.complexity_score < 85:
            m.complexity_grade = "C"
        else:
            m.complexity_grade = "D"

        # Build suggestions
        suggestions: List[str] = []
        if m.tables_without_primary_key:
            suggestions.append(f"Add primary keys to {len(m.tables_without_primary_key)} tables: {', '.join(m.tables_without_primary_key[:3])}")
        if m.circular_dependencies:
            suggestions.append(f"Break {len(m.circular_dependencies)} circular dependency cycles")
        if m.orphan_entities:
            suggestions.append(f"Review {len(m.orphan_entities)} orphan entities: {', '.join(m.orphan_entities[:3])}")
        if m.documentation_coverage < 80:
            suggestions.append(f"Improve field documentation coverage (currently {m.documentation_coverage:.1f}%)")
        for norm in m.normalization_warnings[:3]:
            suggestions.append(f"{norm['entity']}: {norm['message']}")
        if not suggestions:
            suggestions.append("Schema follows relational and architectural best practices.")
        m.suggestions = suggestions

        m.quality_score = round(self._compute_quality_score(m), 1)

        return m

    def _find_cycles(self, adj: Dict[str, Set[str]]) -> List[List[str]]:
        """Detect all simple cycles in directed graph using DFS."""
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)

            for neighbor in sorted(adj.get(node, set())):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    idx = rec_stack.index(neighbor)
                    cycle = rec_stack[idx:] + [neighbor]
                    if cycle not in cycles and len(cycle) > 1:
                        cycles.append(cycle)

            rec_stack.pop()

        for node in list(self.ast.entities.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    def _calculate_longest_chain(self, adj: Dict[str, Set[str]]) -> Tuple[int, List[str]]:
        """Find the longest acyclic path in the dependency graph."""
        memo: Dict[str, Tuple[int, List[str]]] = {}
        visiting: Set[str] = set()

        def dfs(node: str) -> Tuple[int, List[str]]:
            if node in memo:
                return memo[node]
            if node in visiting:
                return (0, [node])

            visiting.add(node)
            max_len = 0
            best_chain: List[str] = [node]

            for neighbor in adj.get(node, set()):
                if neighbor != node and neighbor not in visiting:
                    sub_len, sub_chain = dfs(neighbor)
                    if sub_len + 1 > max_len:
                        max_len = sub_len + 1
                        best_chain = [node] + sub_chain

            visiting.remove(node)
            memo[node] = (max_len, best_chain)
            return memo[node]

        longest = 0
        longest_chain: List[str] = []

        for node in self.ast.entities.keys():
            length, chain = dfs(node)
            if length > longest:
                longest = length
                longest_chain = chain

        return longest, longest_chain

    def _check_naming_conventions(self, entities: List[EntityAST]) -> List[Dict[str, Any]]:
        """Check for field naming consistency and casing styles."""
        issues: List[Dict[str, Any]] = []

        for ent in entities:
            has_camel = False
            has_snake = False

            for f in ent.fields:
                name = f.name
                if "_" in name and not name.startswith("_"):
                    has_snake = True
                elif any(c.isupper() for c in name[1:]):
                    has_camel = True

                if name.lower() in ("select", "table", "order", "group", "by", "where", "from", "user", "index"):
                    issues.append({
                        "entity": ent.name,
                        "field": name,
                        "message": f"Field name '{name}' is an SQL reserved keyword. Consider quoting or renaming.",
                    })

            if has_camel and has_snake:
                issues.append({
                    "entity": ent.name,
                    "field": "*",
                    "message": "Entity mixes both snake_case and camelCase field naming conventions.",
                })

        return issues

    def _check_normalization(self, entities: List[EntityAST]) -> List[Dict[str, Any]]:
        """Detect potential normalization improvements (1NF, 2NF, 3NF)."""
        warnings: List[Dict[str, Any]] = []

        for ent in entities:
            prefixes: Dict[str, List[str]] = collections.defaultdict(list)
            for f in ent.fields:
                if "_" in f.name:
                    prefix = f.name.split("_")[0]
                    prefixes[prefix].append(f.name)

            for prefix, field_list in prefixes.items():
                if len(field_list) >= 3 and prefix not in ("is", "has", "created", "updated", "deleted"):
                    warnings.append({
                        "entity": ent.name,
                        "message": f"Repeated prefix '{prefix}_' across {len(field_list)} fields ({', '.join(field_list[:3])}...). Consider extracting into a separate '{prefix.title()}' entity.",
                    })

            if len(ent.fields) > 20:
                warnings.append({
                    "entity": ent.name,
                    "message": f"Entity has {len(ent.fields)} fields (high column cardinality). Consider decomposing into related sub-entities.",
                })

            for f in ent.fields:
                if f.type in (DataType.JSON, DataType.OBJECT) and not f.target_entity:
                    warnings.append({
                        "entity": ent.name,
                        "message": f"Field '{f.name}' uses generic JSON type. For relational queries, consider typing with a structured model.",
                    })

        return warnings

    def _compute_quality_score(self, m: SchemaMetrics) -> float:
        """Compute composite 0-100 quality score."""
        score = 100.0

        pk_penalty = min(40.0, len(m.tables_without_primary_key) * 15.0)
        score -= pk_penalty

        cycle_penalty = min(30.0, len(m.circular_dependencies) * 20.0)
        score -= cycle_penalty

        doc_penalty = ((100.0 - m.documentation_coverage) / 100.0) * 20.0
        score -= doc_penalty

        naming_penalty = min(10.0, len(m.naming_convention_issues) * 2.0)
        score -= naming_penalty

        orphan_penalty = min(15.0, len(m.orphan_entities) * 3.0)
        score -= orphan_penalty

        return max(0.0, min(100.0, score))


def analyze_schema(ast: SchemaAST) -> SchemaMetrics:
    """Analyze a SchemaAST and return quality metrics."""
    analyzer = SchemaAnalyzer(ast)
    return analyzer.analyze()


def calculate_metrics(ast: SchemaAST) -> SchemaMetrics:
    """Alias for analyze_schema."""
    return analyze_schema(ast)
