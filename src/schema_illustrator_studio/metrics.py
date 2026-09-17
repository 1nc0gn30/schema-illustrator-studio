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
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from schema_illustrator_studio.models import DataType, EntityAST, SchemaAST


@dataclass
class SchemaMetrics:
    """Comprehensive quality metrics and insights for a SchemaAST."""

    total_entities: int = 0
    total_fields: int = 0
    total_relationships: int = 0
    avg_fields_per_entity: float = 0.0
    max_fields_in_entity: Tuple[str, int] = ("", 0)

    orphan_entities: List[str] = field(default_factory=list)
    circular_dependencies: List[List[str]] = field(default_factory=list)
    max_dependency_depth: int = 0
    deepest_dependency_chain: List[str] = field(default_factory=list)

    tables_without_primary_key: List[str] = field(default_factory=list)
    fields_without_description: int = 0
    documentation_coverage: float = 0.0

    naming_convention_issues: List[Dict[str, Any]] = field(default_factory=list)
    normalization_warnings: List[Dict[str, Any]] = field(default_factory=list)
    quality_score: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_entities": self.total_entities,
            "total_fields": self.total_fields,
            "total_relationships": self.total_relationships,
            "avg_fields_per_entity": round(self.avg_fields_per_entity, 2),
            "max_fields_in_entity": {
                "entity": self.max_fields_in_entity[0],
                "count": self.max_fields_in_entity[1],
            },
            "orphan_entities": self.orphan_entities,
            "circular_dependencies": self.circular_dependencies,
            "max_dependency_depth": self.max_dependency_depth,
            "deepest_dependency_chain": self.deepest_dependency_chain,
            "tables_without_primary_key": self.tables_without_primary_key,
            "fields_without_description": self.fields_without_description,
            "documentation_coverage": round(self.documentation_coverage, 1),
            "naming_convention_issues": self.naming_convention_issues,
            "normalization_warnings": self.normalization_warnings,
            "quality_score": round(self.quality_score, 1),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert metrics to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def summary_markdown(self) -> str:
        """Generate human-readable Markdown summary report."""
        lines: List[str] = []
        score_emoji = "🟢" if self.quality_score >= 85 else ("🟡" if self.quality_score >= 65 else "🔴")

        lines.append(f"## {score_emoji} Schema Quality Audit Report (Score: {self.quality_score:.1f}/100)")
        lines.append("")
        lines.append("### 📊 Architecture Overview")
        lines.append(f"- **Total Entities**: `{self.total_entities}`")
        lines.append(f"- **Total Fields**: `{self.total_fields}` (Avg: `{self.avg_fields_per_entity:.1f}`/entity)")
        lines.append(f"- **Total Relationships**: `{self.total_relationships}`")
        lines.append(f"- **Documentation Coverage**: `{self.documentation_coverage:.1f}%` ({self.fields_without_description} undocumented fields)")
        lines.append(f"- **Max Dependency Depth**: `{self.max_dependency_depth}`")
        if self.deepest_dependency_chain:
            lines.append(f"  - Chain: `{' -> '.join(self.deepest_dependency_chain)}`")
        lines.append("")

        # Warnings / Action Items
        lines.append("### 🔍 Diagnostics & Health Checks")

        # Primary keys
        if self.tables_without_primary_key:
            lines.append(f"- ⚠️ **Entities Missing Primary Key** ({len(self.tables_without_primary_key)}):")
            for t in self.tables_without_primary_key:
                lines.append(f"  - `{t}`")
        else:
            lines.append("- ✅ **All entities have valid Primary Keys**")

        # Circular dependencies
        if self.circular_dependencies:
            lines.append(f"- ⚠️ **Circular Dependencies Detected** ({len(self.circular_dependencies)} cycles):")
            for cycle in self.circular_dependencies:
                lines.append(f"  - `{' -> '.join(cycle)}`")
        else:
            lines.append("- ✅ **No circular dependencies detected (DAG verified)**")

        # Orphan entities
        if self.orphan_entities:
            lines.append(f"- ℹ️ **Orphan Entities** (0 incoming/outgoing relations, {len(self.orphan_entities)}):")
            for o in self.orphan_entities:
                lines.append(f"  - `{o}`")

        # Naming issues
        if self.naming_convention_issues:
            lines.append(f"- ⚠️ **Naming Inconsistencies** ({len(self.naming_convention_issues)}):")
            for issue in self.naming_convention_issues[:5]:
                lines.append(f"  - `{issue['entity']}.{issue['field']}`: {issue['message']}")
            if len(self.naming_convention_issues) > 5:
                lines.append(f"  - *...and {len(self.naming_convention_issues) - 5} more.*")

        # Normalization
        if self.normalization_warnings:
            lines.append(f"- 💡 **Normalization Recommendations** ({len(self.normalization_warnings)}):")
            for norm in self.normalization_warnings[:5]:
                lines.append(f"  - `{norm['entity']}`: {norm['message']}")
            if len(self.normalization_warnings) > 5:
                lines.append(f"  - *...and {len(self.normalization_warnings) - 5} more.*")

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
        all_fields = [f for e in all_entities for f in e.fields]
        m.total_fields = len(all_fields)
        m.total_relationships = len(self.ast.relationships)

        if m.total_entities > 0:
            m.avg_fields_per_entity = m.total_fields / m.total_entities

        # Max fields
        max_ent = max(all_entities, key=lambda e: len(e.fields), default=None)
        if max_ent:
            m.max_fields_in_entity = (max_ent.name, len(max_ent.fields))

        # Documentation coverage
        documented_fields = sum(1 for f in all_fields if f.description.strip())
        m.fields_without_description = m.total_fields - documented_fields
        if m.total_fields > 0:
            m.documentation_coverage = (documented_fields / m.total_fields) * 100.0
        else:
            m.documentation_coverage = 100.0

        # Primary Key checks
        for ent in entities:
            if not ent.primary_keys():
                m.tables_without_primary_key.append(ent.name)

        # Graph Building
        adj: Dict[str, Set[str]] = collections.defaultdict(set)
        in_degree: Dict[str, int] = {e.name: 0 for e in all_entities}
        out_degree: Dict[str, int] = {e.name: 0 for e in all_entities}

        for rel in self.ast.relationships:
            if rel.source_entity in in_degree and rel.target_entity in in_degree:
                adj[rel.source_entity].add(rel.target_entity)
                out_degree[rel.source_entity] += 1
                in_degree[rel.target_entity] += 1

        # Also inspect direct field target_entity references
        for ent in all_entities:
            for f in ent.fields:
                if f.target_entity and f.target_entity in in_degree:
                    if f.target_entity not in adj[ent.name]:
                        adj[ent.name].add(f.target_entity)
                        out_degree[ent.name] += 1
                        in_degree[f.target_entity] += 1

        # Orphan entities (excluding standalone enums/unions if count is small)
        for ent in entities:
            if in_degree.get(ent.name, 0) == 0 and out_degree.get(ent.name, 0) == 0:
                m.orphan_entities.append(ent.name)

        # Circular Dependency & Cycle Detection (DFS)
        m.circular_dependencies = self._find_cycles(adj)

        # Dependency Depth & Deepest Chain
        m.max_dependency_depth, m.deepest_dependency_chain = self._calculate_longest_chain(adj)

        # Naming convention analysis
        m.naming_convention_issues = self._check_naming_conventions(all_entities)

        # Normalization heuristics
        m.normalization_warnings = self._check_normalization(entities)

        # Calculate Quality Score
        m.quality_score = self._compute_quality_score(m)

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
                    # Found cycle
                    idx = rec_stack.index(neighbor)
                    cycle = rec_stack[idx:] + [neighbor]
                    # Check duplicate
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
            # Check field naming casing within entity
            has_camel = False
            has_snake = False

            for f in ent.fields:
                name = f.name
                if "_" in name and not name.startswith("_"):
                    has_snake = True
                elif any(c.isupper() for c in name[1:]):
                    has_camel = True

                # Check reserved keywords
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
            # 1. Check repeated field prefixes (e.g. billing_address_street, billing_address_city)
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

            # 2. Too many columns (> 20)
            if len(ent.fields) > 20:
                warnings.append({
                    "entity": ent.name,
                    "message": f"Entity has {len(ent.fields)} fields (high column cardinality). Consider decomposing into related sub-entities.",
                })

            # 3. Unstructured JSON/ARRAY fields without relationship
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

        # Missing PK penalty: -15 per table without PK (up to 40 pts)
        pk_penalty = min(40.0, len(m.tables_without_primary_key) * 15.0)
        score -= pk_penalty

        # Circular dependencies penalty: -20 per cycle (up to 30 pts)
        cycle_penalty = min(30.0, len(m.circular_dependencies) * 20.0)
        score -= cycle_penalty

        # Low documentation coverage penalty: up to 20 pts
        doc_penalty = ((100.0 - m.documentation_coverage) / 100.0) * 20.0
        score -= doc_penalty

        # Naming inconsistencies: -2 per issue (up to 10 pts)
        naming_penalty = min(10.0, len(m.naming_convention_issues) * 2.0)
        score -= naming_penalty

        # Orphan entities penalty: -3 per orphan (up to 15 pts)
        orphan_penalty = min(15.0, len(m.orphan_entities) * 3.0)
        score -= orphan_penalty

        return max(0.0, min(100.0, score))


def analyze_schema(ast: SchemaAST) -> SchemaMetrics:
    """Analyze a SchemaAST and return quality metrics."""
    analyzer = SchemaAnalyzer(ast)
    return analyzer.analyze()
