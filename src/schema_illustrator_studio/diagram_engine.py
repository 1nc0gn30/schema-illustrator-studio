"""High-fidelity Diagram Engine for schema visualization.

Generates standalone SVG ERD diagrams with card layouts, badges, and bezier connectors,
Mermaid erDiagram specifications, ASCII Unicode box-drawing tables, and Graphviz DOT
using 100% Python standard library.
"""

from __future__ import annotations

import html
import math
from typing import Any, Dict, List, Optional, Tuple

from schema_illustrator_studio.models import (
    DataType,
    EntityAST,
    FieldAST,
    RelationshipAST,
    RelationshipType,
    SchemaAST,
)


class DiagramEngine:
    """Multi-format diagram generator for SchemaAST."""

    def __init__(self, ast: SchemaAST) -> None:
        self.ast = ast

    # =========================================================================
    # 1. Standalone SVG ERD Generator
    # =========================================================================

    def generate_svg(
        self,
        theme: str = "dark",
        layout: str = "grid",
        max_columns: int = 3,
        card_width: int = 280,
    ) -> str:
        """Generate high-fidelity standalone SVG ERD diagram with cards and bezier curves."""
        is_dark = theme.lower() == "dark"

        colors = {
            "bg": "#0f172a" if is_dark else "#f8fafc",
            "grid": "#1e293b" if is_dark else "#e2e8f0",
            "card_bg": "#1e293b" if is_dark else "#ffffff",
            "card_border": "#334155" if is_dark else "#cbd5e1",
            "header_bg": "#334155" if is_dark else "#f1f5f9",
            "header_enum_bg": "#475569" if is_dark else "#e2e8f0",
            "text_primary": "#f8fafc" if is_dark else "#0f172a",
            "text_secondary": "#94a3b8" if is_dark else "#64748b",
            "text_muted": "#64748b" if is_dark else "#94a3b8",
            "badge_pk_bg": "rgba(245, 158, 11, 0.2)",
            "badge_pk_text": "#f59e0b",
            "badge_fk_bg": "rgba(56, 189, 248, 0.2)",
            "badge_fk_text": "#38bdf8",
            "badge_type_bg": "#0f172a" if is_dark else "#e2e8f0",
            "badge_type_text": "#cbd5e1" if is_dark else "#334155",
            "connector": "#60a5fa" if is_dark else "#2563eb",
            "connector_glow": "rgba(96, 165, 250, 0.2)" if is_dark else "rgba(37, 99, 235, 0.1)",
        }

        cards: Dict[str, Dict[str, Any]] = {}
        row_height_per_field = 28
        header_height = 42
        card_padding = 16
        col_gap = 80
        row_gap = 60
        start_x = 60
        start_y = 90

        col_heights = [start_y] * max_columns
        entity_list = list(self.ast.entities.values())

        for ent in entity_list:
            field_count = max(1, len(ent.fields))
            card_height = header_height + (field_count * row_height_per_field) + card_padding

            best_col = min(range(max_columns), key=lambda c: col_heights[c])
            x = start_x + (best_col * (card_width + col_gap))
            y = col_heights[best_col]

            col_heights[best_col] += card_height + row_gap

            cards[ent.name] = {
                "entity": ent,
                "x": x,
                "y": y,
                "width": card_width,
                "height": card_height,
                "field_anchors": {},
            }

            for f_idx, f in enumerate(ent.fields):
                field_y = y + header_height + (f_idx * row_height_per_field) + (row_height_per_field // 2)
                cards[ent.name]["field_anchors"][f.name] = field_y

        total_width = start_x * 2 + (max_columns * card_width) + ((max_columns - 1) * col_gap)
        total_height = max(col_heights) + 60

        svg_parts: List[str] = []
        svg_parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} {total_height}" width="{total_width}" height="{total_height}" style="background-color: {colors["bg"]}; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
        )

        svg_parts.append("<defs>")
        svg_parts.append(
            f"""  <filter id="card-shadow" x="-8%" y="-8%" width="120%" height="120%">
    <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="{0.4 if is_dark else 0.1}"/>
  </filter>
  <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
    <polygon points="0 0, 8 3, 0 6" fill="{colors['connector']}" />
  </marker>
  <marker id="dot" markerWidth="6" markerHeight="6" refX="3" refY="3">
    <circle cx="3" cy="3" r="2.5" fill="{colors['connector']}" />
  </marker>
  <pattern id="grid-pattern" width="24" height="24" patternUnits="userSpaceOnUse">
    <circle cx="12" cy="12" r="1" fill="{colors['grid']}" opacity="0.6"/>
  </pattern>"""
        )
        svg_parts.append("</defs>")

        svg_parts.append(f'<rect width="100%" height="100%" fill="url(#grid-pattern)" />')

        title_text = html.escape(self.ast.name or "Schema Architecture ERD")
        version_text = html.escape(f"v{self.ast.version} • {len(self.ast.entities)} Entities • {len(self.ast.relationships)} Relationships")
        svg_parts.append(
            f'<text x="{start_x}" y="42" font-size="20" font-weight="700" fill="{colors["text_primary"]}">{title_text}</text>'
        )
        svg_parts.append(
            f'<text x="{start_x}" y="62" font-size="12" font-weight="400" fill="{colors["text_secondary"]}">{version_text}</text>'
        )

        connector_svg = self._render_svg_connectors(cards, colors)
        svg_parts.extend(connector_svg)

        for card in cards.values():
            card_svg = self._render_svg_card(card, colors, header_height, row_height_per_field)
            svg_parts.extend(card_svg)

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def _render_svg_card(
        self,
        card: Dict[str, Any],
        colors: Dict[str, str],
        header_height: int,
        row_height: int,
    ) -> List[str]:
        """Render a single entity card in SVG."""
        ent: EntityAST = card["entity"]
        x, y, w, h = card["x"], card["y"], card["width"], card["height"]
        lines: List[str] = []

        lines.append(f'<g class="entity-card" transform="translate({x}, {y})">')
        lines.append(
            f'  <rect width="{w}" height="{h}" rx="8" ry="8" fill="{colors["card_bg"]}" stroke="{colors["card_border"]}" stroke-width="1.5" filter="url(#card-shadow)" />'
        )

        header_color = colors["header_enum_bg"] if ent.is_enum else colors["header_bg"]
        lines.append(
            f'  <path d="M 0,8 A 8,8 0 0,1 8,0 L {w - 8},0 A 8,8 0 0,1 {w},8 L {w},{header_height} L 0,{header_height} Z" fill="{header_color}" />'
        )
        lines.append(
            f'  <line x1="0" y1="{header_height}" x2="{w}" y2="{header_height}" stroke="{colors["card_border"]}" stroke-width="1" />'
        )

        stereotype = "«enum»" if ent.is_enum else ("«union»" if ent.is_union else "«entity»")
        lines.append(
            f'  <text x="12" y="18" font-size="10" font-weight="600" fill="{colors["text_muted"]}">{stereotype}</text>'
        )

        ent_name_esc = html.escape(ent.name)
        lines.append(
            f'  <text x="12" y="34" font-size="14" font-weight="700" fill="{colors["text_primary"]}">{ent_name_esc}</text>'
        )

        field_count_label = f"{len(ent.fields)} fields"
        lines.append(
            f'  <rect x="{w - 68}" y="12" width="56" height="18" rx="9" fill="{colors["badge_type_bg"]}" />'
        )
        lines.append(
            f'  <text x="{w - 40}" y="25" font-size="10" font-weight="500" fill="{colors["badge_type_text"]}" text-anchor="middle">{field_count_label}</text>'
        )

        for idx, f in enumerate(ent.fields):
            row_y = header_height + (idx * row_height)
            text_y = row_y + 19

            if idx % 2 == 1:
                lines.append(
                    f'  <rect x="1" y="{row_y}" width="{w - 2}" height="{row_height}" fill="{colors["grid"]}" opacity="0.2" />'
                )

            badge_x = 12
            if f.is_primary_key:
                lines.append(
                    f'  <rect x="{badge_x}" y="{row_y + 6}" width="22" height="16" rx="4" fill="{colors["badge_pk_bg"]}" />'
                )
                lines.append(
                    f'  <text x="{badge_x + 11}" y="{row_y + 18}" font-size="9" font-weight="700" fill="{colors["badge_pk_text"]}" text-anchor="middle">PK</text>'
                )
                badge_x += 26
            elif f.is_foreign_key or f.target_entity:
                lines.append(
                    f'  <rect x="{badge_x}" y="{row_y + 6}" width="22" height="16" rx="4" fill="{colors["badge_fk_bg"]}" />'
                )
                lines.append(
                    f'  <text x="{badge_x + 11}" y="{row_y + 18}" font-size="9" font-weight="700" fill="{colors["badge_fk_text"]}" text-anchor="middle">FK</text>'
                )
                badge_x += 26
            elif f.is_unique:
                lines.append(
                    f'  <text x="{badge_x}" y="{text_y}" font-size="11" fill="{colors["badge_pk_text"]}">✦</text>'
                )
                badge_x += 14
            else:
                lines.append(
                    f'  <circle cx="{badge_x + 4}" cy="{row_y + 14}" r="2.5" fill="{colors["text_muted"]}" />'
                )
                badge_x += 14

            name_color = colors["text_primary"] if (f.is_primary_key or not f.is_nullable) else colors["text_secondary"]
            f_name_esc = html.escape(f.name)
            if len(f_name_esc) > 16:
                f_name_esc = f_name_esc[:14] + "…"
            lines.append(
                f'  <text x="{badge_x}" y="{text_y}" font-size="12" font-weight="{"600" if f.is_primary_key else "400"}" fill="{name_color}">{f_name_esc}</text>'
            )

            type_label = f.display_type()
            if len(type_label) > 14:
                type_label = type_label[:12] + "…"
            type_label_esc = html.escape(type_label)
            pill_w = max(40, len(type_label) * 7 + 10)
            pill_x = w - pill_w - 10

            lines.append(
                f'  <rect x="{pill_x}" y="{row_y + 6}" width="{pill_w}" height="16" rx="4" fill="{colors["badge_type_bg"]}" />'
            )
            lines.append(
                f'  <text x="{pill_x + pill_w // 2}" y="{row_y + 18}" font-size="10" font-weight="500" fill="{colors["badge_type_text"]}" text-anchor="middle">{type_label_esc}</text>'
            )

        lines.append("</g>")
        return lines

    def _render_svg_connectors(
        self,
        cards: Dict[str, Dict[str, Any]],
        colors: Dict[str, str],
    ) -> List[str]:
        """Render smooth cubic bezier connector curves between related cards."""
        lines: List[str] = []

        for rel in self.ast.relationships:
            src_card = cards.get(rel.source_entity)
            tgt_card = cards.get(rel.target_entity)

            if not src_card or not tgt_card:
                continue

            src_x = src_card["x"]
            src_y = src_card["field_anchors"].get(rel.source_field, src_card["y"] + 40)
            tgt_x = tgt_card["x"]
            tgt_y = tgt_card["field_anchors"].get(rel.target_field, tgt_card["y"] + 40)

            if src_x < tgt_x:
                p1_x = src_x + src_card["width"]
                p1_y = src_y
                p2_x = tgt_x
                p2_y = tgt_y
                ctrl_offset = max(40, abs(p2_x - p1_x) * 0.4)
                c1_x, c1_y = p1_x + ctrl_offset, p1_y
                c2_x, c2_y = p2_x - ctrl_offset, p2_y
            elif src_x > tgt_x:
                p1_x = src_x
                p1_y = src_y
                p2_x = tgt_x + tgt_card["width"]
                p2_y = tgt_y
                ctrl_offset = max(40, abs(p1_x - p2_x) * 0.4)
                c1_x, c1_y = p1_x - ctrl_offset, p1_y
                c2_x, c2_y = p2_x + ctrl_offset, p2_y
            else:
                p1_x = src_x + src_card["width"]
                p1_y = src_y
                p2_x = tgt_x + tgt_card["width"]
                p2_y = tgt_y
                loop_offset = 60
                c1_x, c1_y = p1_x + loop_offset, p1_y
                c2_x, c2_y = p2_x + loop_offset, p2_y

            path_data = f"M {p1_x} {p1_y} C {c1_x} {c1_y}, {c2_x} {c2_y}, {p2_x} {p2_y}"

            lines.append(
                f'<path d="{path_data}" fill="none" stroke="{colors["connector_glow"]}" stroke-width="4" stroke-linecap="round" />'
            )
            lines.append(
                f'<path d="{path_data}" fill="none" stroke="{colors["connector"]}" stroke-width="1.8" marker-start="url(#dot)" marker-end="url(#arrowhead)" />'
            )

            mid_x = (p1_x + p2_x) / 2
            mid_y = (p1_y + p2_y) / 2
            card_label = rel.cardinality or "N:1"
            lines.append(
                f'<rect x="{mid_x - 14}" y="{mid_y - 9}" width="28" height="16" rx="4" fill="{colors["card_bg"]}" stroke="{colors["connector"]}" stroke-width="1" />'
            )
            lines.append(
                f'<text x="{mid_x}" y="{mid_y + 3}" font-size="9" font-weight="700" fill="{colors["connector"]}" text-anchor="middle">{card_label}</text>'
            )

        return lines

    # =========================================================================
    # 2. Mermaid erDiagram Generator
    # =========================================================================

    def generate_mermaid(self) -> str:
        """Generate Mermaid erDiagram string."""
        lines: List[str] = ["erDiagram"]

        for rel in self.ast.relationships:
            rel_symbol = self._map_mermaid_cardinality(rel.relation_type, rel.cardinality)
            label = rel.name or f"references"
            lines.append(f"    {rel.source_entity} {rel_symbol} {rel.target_entity} : \"{label}\"")

        if not self.ast.relationships:
            lines.append("    %% Entities without explicit relationships")

        for ent in self.ast.entities.values():
            if ent.is_enum or ent.is_union:
                continue

            lines.append(f"    {ent.name} {{")
            for f in ent.fields:
                f_type = self._map_mermaid_type(f.type)
                f_name = f.name
                f_key = "PK" if f.is_primary_key else ("FK" if (f.is_foreign_key or f.target_entity) else ("UK" if f.is_unique else ""))
                comment = f'"{f.description}"' if f.description else ""

                parts = [f"        {f_type}", f_name]
                if f_key:
                    parts.append(f_key)
                if comment:
                    parts.append(comment)
                lines.append(" ".join(parts))
            lines.append("    }")

        return "\n".join(lines).strip() + "\n"

    def _map_mermaid_cardinality(self, rel_type: RelationshipType, card_str: str) -> str:
        """Convert relationship type to Mermaid erDiagram connector."""
        if card_str in ("1:1", "ONE_TO_ONE"):
            return "||--||"
        if card_str in ("1:N", "ONE_TO_MANY"):
            return "||--o{"
        if card_str in ("N:1", "MANY_TO_ONE"):
            return "}o--||"
        if card_str in ("N:M", "MANY_TO_MANY"):
            return "}o--o{"
        return "}o--||"

    def _map_mermaid_type(self, dt: DataType) -> str:
        """Map DataType to Mermaid attribute type."""
        mapping = {
            DataType.STRING: "string",
            DataType.INTEGER: "int",
            DataType.BIGINT: "bigint",
            DataType.FLOAT: "float",
            DataType.DECIMAL: "decimal",
            DataType.BOOLEAN: "boolean",
            DataType.DATETIME: "datetime",
            DataType.DATE: "date",
            DataType.TIME: "time",
            DataType.UUID: "uuid",
            DataType.JSON: "json",
            DataType.OBJECT: "object",
            DataType.BYTES: "blob",
        }
        return mapping.get(dt, "string")

    # =========================================================================
    # 3. ASCII Box-Drawing ER Table Renderer
    # =========================================================================

    def generate_ascii(self, max_width: int = 80) -> str:
        """Generate formatted Unicode box-drawing ER tables."""
        output: List[str] = []

        header_title = f" SCHEMA ARCHITECTURE: {self.ast.name or 'Schema'} (v{self.ast.version}) "
        output.append("=" * max_width)
        output.append(header_title.center(max_width, "="))
        output.append("=" * max_width)
        output.append("")

        for ent in self.ast.entities.values():
            output.append(self._render_ascii_entity(ent, max_width))
            output.append("")

        if self.ast.relationships:
            output.append("┌" + "─" * (max_width - 2) + "┐")
            output.append("│" + " RELATIONSHIPS ".center(max_width - 2) + "│")
            output.append("├" + "─" * (max_width - 2) + "┤")
            for rel in self.ast.relationships:
                rel_line = f"  • {rel.source_entity}.{rel.source_field} ──[{rel.cardinality}]──> {rel.target_entity}.{rel.target_field or 'id'}"
                output.append("│" + rel_line.ljust(max_width - 2) + "│")
            output.append("└" + "─" * (max_width - 2) + "┘")

        return "\n".join(output)

    def _render_ascii_entity(self, ent: EntityAST, max_width: int) -> str:
        """Render a single Entity as an ASCII table."""
        w = min(max_width, 60)
        lines: List[str] = []

        lines.append("┌" + "─" * (w - 2) + "┐")

        stereotype = " [ENUM]" if ent.is_enum else (" [UNION]" if ent.is_union else "")
        title = f" {ent.name}{stereotype} "
        lines.append("│" + title.center(w - 2) + "│")
        lines.append("├" + "─" * (w - 2) + "┤")

        for f in ent.fields:
            key_tag = "PK" if f.is_primary_key else ("FK" if (f.is_foreign_key or f.target_entity) else ("UQ" if f.is_unique else "  "))
            req_tag = "*" if not f.is_nullable else " "
            f_type = f.display_type()

            col_left = f" {key_tag} {req_tag} {f.name}"
            col_right = f"{f_type} "

            space = w - 2 - len(col_left) - len(col_right)
            if space < 1:
                col_left = col_left[: w - len(col_right) - 5] + "…"
                space = 1

            row = col_left + (" " * space) + col_right
            lines.append("│" + row + "│")

        lines.append("└" + "─" * (w - 2) + "┘")
        return "\n".join(lines)

    # =========================================================================
    # 4. Graphviz DOT Generator
    # =========================================================================

    def generate_dot(self) -> str:
        """Generate Graphviz DOT format for schema visualizer tools."""
        lines: List[str] = [
            "digraph SchemaERD {",
            '  graph [rankdir="LR", bgcolor="#0f172a", fontname="Helvetica", nodesep="0.6", ranksep="0.8"];',
            '  node [shape="none", fontname="Helvetica"];',
            '  edge [color="#60a5fa", fontcolor="#94a3b8", fontsize="10", penwidth="1.5"];',
            "",
        ]

        for ent in self.ast.entities.values():
            lines.append(f'  "{ent.name}" [label=<')
            lines.append('    <table border="0" cellborder="1" cellspacing="0" cellpadding="6" bgcolor="#1e293b" color="#334155" style="rounded">')
            lines.append(f'      <tr><td bgcolor="#334155" align="center" colspan="3"><font color="#f8fafc"><b>{ent.name}</b></font></td></tr>')

            for f in ent.fields:
                key_label = "🔑 " if f.is_primary_key else ("🔗 " if (f.is_foreign_key or f.target_entity) else "")
                lines.append("      <tr>")
                lines.append(f'        <td align="left" port="{f.name}"><font color="#f8fafc">{key_label}{f.name}</font></td>')
                lines.append(f'        <td align="right"><font color="#94a3b8">{f.display_type()}</font></td>')
                lines.append("      </tr>")

            lines.append("    </table>")
            lines.append("  >];")

        lines.append("")

        for rel in self.ast.relationships:
            src_port = f':"{rel.source_field}"' if rel.source_field else ""
            tgt_port = f':"{rel.target_field}"' if rel.target_field else ""
            lines.append(
                f'  "{rel.source_entity}"{src_port} -> "{rel.target_entity}"{tgt_port} [label="{rel.cardinality}"];'
            )

        lines.append("}")
        return "\n".join(lines).strip() + "\n"


# Convenience functional wrappers
def generate_erd_svg(ast: SchemaAST, theme: str = "dark", **kwargs: Any) -> str:
    """Convenience helper to generate SVG ERD diagram from SchemaAST."""
    engine = DiagramEngine(ast)
    return engine.generate_svg(theme=theme, **kwargs)


def export_erd_svg(ast: SchemaAST, theme: str = "dark", **kwargs: Any) -> str:
    """Alias for generate_erd_svg."""
    return generate_erd_svg(ast, theme=theme, **kwargs)


def generate_mermaid_erd(ast: SchemaAST) -> str:
    """Convenience helper to generate Mermaid erDiagram from SchemaAST."""
    engine = DiagramEngine(ast)
    return engine.generate_mermaid()


def export_mermaid_erd(ast: SchemaAST) -> str:
    """Alias for generate_mermaid_erd."""
    return generate_mermaid_erd(ast)


def generate_ascii_erd(ast: SchemaAST, max_width: int = 80) -> str:
    """Convenience helper to generate ASCII ER diagram from SchemaAST."""
    engine = DiagramEngine(ast)
    return engine.generate_ascii(max_width=max_width)
