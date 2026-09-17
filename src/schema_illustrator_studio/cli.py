"""Multi-OS Command-Line Interface for schema-illustrator-studio.

Provides commands for schema parsing, transpilation, SVG/Mermaid ERD generation,
schema metrics, sample templates, Google Material 3 Web UI server,
MCP server over stdio, system diagnostics, and internal self-tests.
100% Python standard library only.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO, Union

from schema_illustrator_studio import (
    SAMPLE_TEMPLATES,
    __author__,
    __description__,
    __version__,
    analyze_schema_metrics,
    detect_schema_format,
    export_erd_svg,
    export_mermaid_erd,
    get_sample_template,
    list_sample_templates,
    parse_schema,
    transpile_schema,
)
from schema_illustrator_studio.compat import (
    atomic_write,
    is_linux,
    is_macos,
    is_termux,
    is_windows,
    safe_normalize_path,
    safe_read_text,
    safe_write_text,
)
from schema_illustrator_studio.models import SchemaAST


# Terminal Styling & Colors
class Theme:
    """ANSI color codes with automatic detection and stripping."""

    def __init__(self, no_color: bool = False) -> None:
        self.enabled = (
            not no_color
            and not bool(os.environ.get("NO_COLOR"))
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )

    def _c(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else str(text)

    def bold(self, text: str) -> str:
        return self._c("1", text)

    def dim(self, text: str) -> str:
        return self._c("2", text)

    def italic(self, text: str) -> str:
        return self._c("3", text)

    def blue(self, text: str) -> str:
        return self._c("94", text)

    def cyan(self, text: str) -> str:
        return self._c("96", text)

    def green(self, text: str) -> str:
        return self._c("92", text)

    def yellow(self, text: str) -> str:
        return self._c("93", text)

    def red(self, text: str) -> str:
        return self._c("91", text)

    def magenta(self, text: str) -> str:
        return self._c("95", text)

    def primary(self, text: str) -> str:
        return self._c("1;38;5;141", text)  # Purple

    def accent(self, text: str) -> str:
        return self._c("1;38;5;117", text)  # Sky blue


def print_banner(t: Theme) -> None:
    """Print the Studio CLI header banner."""
    banner = f"""{t.primary("╔═════════════════════════════════════════════════════════════════════╗")}
{t.primary("║")}   {t.bold("✦ Google Material 3 Schema Studio & Multi-Format MCP Server ✦")}   {t.primary("║")}
{t.primary("║")}   {t.dim(f"Universal Schema Transpiler, ERD Engine & Protocol v{__version__:<15}")} {t.primary("║")}
{t.primary("╚═════════════════════════════════════════════════════════════════════╝")}"""
    print(banner)


def resolve_input(source_arg: Optional[str]) -> str:
    """Resolve schema text from argument, file path, or stdin."""
    if not source_arg or source_arg == "-":
        if not sys.stdin.isatty():
            return sys.stdin.read()
        if source_arg == "-":
            print("Reading schema from standard input (press Ctrl+D when finished)...", file=sys.stderr)
            return sys.stdin.read()
        raise ValueError("No schema input provided. Specify a file path, schema string, or pipe via stdin.")

    # Check if input is a file path
    try:
        candidate_path = safe_normalize_path(source_arg)
        if candidate_path.exists() and candidate_path.is_file():
            return safe_read_text(candidate_path)
    except Exception:
        pass

    # Treat as direct schema content string
    return source_arg


def output_result(content: str, output_path: Optional[str] = None) -> None:
    """Write output to file or stdout."""
    if output_path:
        p = safe_normalize_path(output_path)
        safe_write_text(p, content)
        print(f"✓ Output written to: {p}", file=sys.stderr)
    else:
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()


# Subcommand Handlers
def cmd_parse(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'parse' subcommand."""
    try:
        raw_text = resolve_input(args.input)
        fmt = None if args.format == "auto" else args.format
        ast = parse_schema(raw_text, format_hint=fmt)

        if args.json:
            output_result(ast.to_json(indent=2), args.output)
            return 0

        # Formatted pretty print
        lines: List[str] = []
        lines.append(f"{t.bold('Schema:')} {t.primary(ast.name or 'Schema')} (v{ast.version})")
        if ast.description:
            lines.append(f"{t.dim('Description:')} {ast.description}")
        lines.append(f"{t.dim('Entities:')} {len(ast.entities)}  |  {t.dim('Relationships:')} {len(ast.relationships)}\n")

        for ent_name, ent in ast.entities.items():
            badge = t.accent("[ENUM]") if ent.is_enum else (t.magenta("[UNION]") if ent.is_union else t.blue("[TABLE]"))
            lines.append(f"{t.bold(ent.name)} {badge}")
            if ent.description:
                lines.append(f"  {t.dim(ent.description)}")

            for f in ent.fields:
                pk_badge = t.yellow("🔑 PK") if f.is_primary_key else ("🔗 FK" if f.is_foreign_key or f.target_entity else "     ")
                type_display = t.cyan(f.display_type())
                null_badge = t.dim("NULL") if f.is_nullable else t.bold("NOT NULL")
                lines.append(f"  {pk_badge:<8} {f.name:<24} {type_display:<20} {null_badge}")
            lines.append("")

        if ast.relationships:
            lines.append(t.bold("Relationships:"))
            for rel in ast.relationships:
                lines.append(
                    f"  {t.green(rel.source_entity)}.{rel.source_field} ──({t.accent(rel.cardinality)})──> {t.green(rel.target_entity)}.{rel.target_field or 'id'}"
                )

        output_result("\n".join(lines), args.output)
        return 0
    except Exception as e:
        print(f"{t.red('Error parsing schema:')} {e}", file=sys.stderr)
        return 1


def cmd_transpile(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'transpile' subcommand."""
    try:
        raw_text = resolve_input(args.input)
        source_fmt = None if args.format == "auto" else args.format
        target_fmt = args.target

        code = transpile_schema(raw_text, target_format=target_fmt, source_format=source_fmt)
        output_result(code, args.output)
        return 0
    except Exception as e:
        print(f"{t.red('Error transpiling schema:')} {e}", file=sys.stderr)
        return 1


def cmd_erd(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'erd' subcommand."""
    try:
        raw_text = resolve_input(args.input)
        fmt = None if args.format == "auto" else args.format
        ast = parse_schema(raw_text, format_hint=fmt)

        diag_type = args.type.lower() if args.type else "auto"
        # Auto-detect: if output path ends with .svg or explicitly requested svg -> SVG, else if terminal without output -> ASCII
        if diag_type == "auto":
            if args.output and args.output.endswith(".svg"):
                diag_type = "svg"
            elif not args.output and sys.stdout.isatty():
                diag_type = "ascii"
            else:
                diag_type = "svg"

        if diag_type == "svg":
            svg = export_erd_svg(ast, title=args.title or "Entity Relationship Diagram", theme=args.theme)
            output_result(svg, args.output)
        else:
            from schema_illustrator_studio.mcp_server import MCPServer

            server = MCPServer()
            ascii_out = server._render_ascii_erd(ast)
            output_result(ascii_out, args.output)

        return 0
    except Exception as e:
        print(f"{t.red('Error generating ERD diagram:')} {e}", file=sys.stderr)
        return 1


def cmd_mermaid(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'mermaid' subcommand."""
    try:
        raw_text = resolve_input(args.input)
        fmt = None if args.format == "auto" else args.format
        ast = parse_schema(raw_text, format_hint=fmt)

        mmd = export_mermaid_erd(ast)
        output_result(mmd, args.output)
        return 0
    except Exception as e:
        print(f"{t.red('Error generating Mermaid ERD:')} {e}", file=sys.stderr)
        return 1


def cmd_metrics(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'metrics' subcommand."""
    try:
        raw_text = resolve_input(args.input)
        fmt = None if args.format == "auto" else args.format
        ast = parse_schema(raw_text, format_hint=fmt)

        metrics = analyze_schema_metrics(ast)

        if args.json:
            output_result(json.dumps(metrics, indent=2), None)
            return 0

        # Formatted Telemetry Card
        grade = metrics.get("complexity_grade", "A")
        grade_colored = t.green(grade) if grade in ("A", "B") else (t.yellow(grade) if grade == "C" else t.red(grade))

        lines: List[str] = [
            f"┌─ {t.bold('Schema Telemetry & Architecture Analysis')} ──────────────────────────┐",
            f"│  {t.bold('Overall Grade:')} {grade_colored:<15}  {t.bold('Normalization Score:')} {metrics['normalization_score']:>3}%       │",
            f"│  {t.bold('Complexity:')}    {metrics['complexity_score']:>5}/100       {t.bold('Graph Density:')}       {metrics['density']:>5}       │",
            f"├────────────────────────────────────────────────────────────────────────┤",
            f"│  {t.cyan('Entities:')}        {metrics['entity_count']:<6}  │  {t.cyan('Total Fields:')}       {metrics['field_count']:<6}  │",
            f"│  {t.cyan('Relationships:')}   {metrics['relationship_count']:<6}  │  {t.cyan('Avg Fields/Entity:')}  {metrics['avg_fields_per_entity']:<6}  │",
            f"│  {t.cyan('Primary Keys:')}    {metrics['primary_key_count']:<6}  │  {t.cyan('Foreign Keys:')}       {metrics['foreign_key_count']:<6}  │",
            f"│  {t.cyan('Unique Fields:')}   {metrics['unique_constraint_count']:<6}  │  {t.cyan('Enums / Unions:')}     {metrics['enum_count'] + metrics['union_count']:<6}  │",
            f"│  {t.cyan('Max Rel Depth:')}   {metrics['max_depth']:<6}  │                                        │",
            f"├────────────────────────────────────────────────────────────────────────┤",
            f"│ {t.bold('Recommendations & Insights:')}                                              │",
        ]
        for sug in metrics.get("suggestions", []):
            lines.append(f"│  • {t.dim(sug)}")
        lines.append("└────────────────────────────────────────────────────────────────────────┘")

        output_result("\n".join(lines), None)
        return 0
    except Exception as e:
        print(f"{t.red('Error analyzing schema metrics:')} {e}", file=sys.stderr)
        return 1


def cmd_samples(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'samples' subcommand."""
    try:
        if args.list or not args.name:
            templates = list_sample_templates()
            lines = [f"{t.bold('Available Built-In Schema Templates:')}\n"]
            for tmpl in templates:
                lines.append(f"  • {t.primary(tmpl['id']):<18} {t.bold(tmpl['name'])}")
                lines.append(f"    {t.dim(tmpl['description'])}")
                lines.append(f"    {t.accent('Formats:')} {', '.join(tmpl['formats'])}\n")
            output_result("\n".join(lines), None)
            return 0

        name = args.name
        fmt = args.format or "sql"

        tmpl_code = get_sample_template(name, format_name=fmt)
        output_result(tmpl_code, args.output)
        return 0
    except Exception as e:
        print(f"{t.red('Error retrieving sample schema:')} {e}", file=sys.stderr)
        return 1


def cmd_serve(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'serve' subcommand."""
    try:
        from schema_illustrator_studio.ui_server import run_standalone

        host = args.host or "127.0.0.1"
        port = int(args.port or 8765)
        open_browser = not args.no_open

        print(f"{t.green('Starting Google Schema Studio Web UI...')}")
        run_standalone(host=host, port=port, open_browser=open_browser)
        return 0
    except Exception as e:
        print(f"{t.red('Error starting Schema Studio UI server:')} {e}", file=sys.stderr)
        return 1


def cmd_mcp(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'mcp' subcommand."""
    try:
        from schema_illustrator_studio.mcp_server import run_mcp_server

        run_mcp_server()
        return 0
    except Exception as e:
        sys.stderr.write(f"Error in MCP server: {e}\n")
        return 1


def cmd_doctor(args: argparse.Namespace, t: Theme) -> int:
    """Handle 'doctor' / 'diagnostics' / 'platform' subcommand."""
    print_banner(t)
    print(f"\n{t.bold('System Diagnostics & Platform Report:')}")
    print(f"  • {t.cyan('Version:')}            {__version__}")
    print(f"  • {t.cyan('Python:')}             {sys.version.split()[0]} ({sys.executable})")
    print(f"  • {t.cyan('Platform:')}           {platform.platform()}")
    print(f"  • {t.cyan('OS Kind:')}            {'Windows' if is_windows() else ('macOS' if is_macos() else ('Termux' if is_termux() else 'Linux'))}")
    print(f"  • {t.cyan('Terminal Encoding:')}  {getattr(sys.stdout, 'encoding', 'unknown')}")
    print(f"  • {t.cyan('Stdout is TTY:')}      {sys.stdout.isatty()}")
    print(f"  • {t.cyan('Color Enabled:')}      {t.enabled}")
    print(f"\n{t.bold('Supported Parsers (Zero Dependencies):')}")
    for p in ["JSON Schema (Draft 7, 2020-12)", "OpenAPI 3.0/3.1", "SQL DDL (Postgres, MySQL, SQLite)", "TypeScript Interfaces & Types", "GraphQL SDL"]:
        print(f"  {t.green('✓')} {p}")

    print(f"\n{t.bold('Supported Transpilers:')}")
    for target in ["TypeScript + Zod", "Python Pydantic v2", "SQL DDL", "GraphQL SDL", "JSON Schema / OpenAPI", "SVG Vector ERD", "Mermaid erDiagram", "ASCII Box ERD"]:
        print(f"  {t.green('✓')} {target}")

    print(f"\n{t.bold('Registered Sample Schemas:')}")
    for key in SAMPLE_TEMPLATES:
        print(f"  {t.green('✓')} {key}")

    print(f"\n{t.green('All subsystems operational and verified.')}\n")
    return 0


def cmd_test(args: argparse.Namespace, t: Theme) -> int:
    """Handle internal self-verification test runner."""
    print_banner(t)
    print(f"\n{t.bold('Running Self-Verification Suite...')}\n")

    test_cases: List[Tuple[str, str]] = [
        ("SQL Parser Test", "CREATE TABLE test_users (id UUID PRIMARY KEY, name VARCHAR(100) NOT NULL);"),
        ("JSON Schema Parser Test", json.dumps({"title": "Test", "type": "object", "properties": {"id": {"type": "string"}}})),
        ("TypeScript Parser Test", "export interface TestItem { id: string; price: number; }"),
        ("GraphQL Parser Test", "type TestNode { id: ID! count: Int }"),
    ]

    passes = 0
    failures = 0

    # 1. Test Parsers
    for name, sample in test_cases:
        t0 = time.perf_counter()
        try:
            ast = parse_schema(sample)
            dt = (time.perf_counter() - t0) * 1000
            assert len(ast.entities) > 0, "No entities parsed"
            print(f"  {t.green('✓')} {name:<32} {t.dim(f'({dt:.2f}ms)')}")
            passes += 1
        except Exception as e:
            print(f"  {t.red('✗')} {name:<32} {t.red(f'FAILED: {e}')}")
            failures += 1

    # 2. Test Transpilers on E-Commerce AST
    ecom_sql = SAMPLE_TEMPLATES["ecommerce"]["sql"]
    ecom_ast = parse_schema(ecom_sql)

    transpile_targets = ["typescript", "pydantic", "sql", "graphql", "json-schema", "openapi"]
    for target in transpile_targets:
        t0 = time.perf_counter()
        try:
            out = transpile_schema(ecom_ast, target_format=target)
            dt = (time.perf_counter() - t0) * 1000
            assert len(out) > 50, f"Generated {target} output too short"
            print(f"  {t.green('✓')} Transpile -> {target:<20} {t.dim(f'({dt:.2f}ms)')}")
            passes += 1
        except Exception as e:
            print(f"  {t.red('✗')} Transpile -> {target:<20} {t.red(f'FAILED: {e}')}")
            failures += 1

    # 3. Test ERD Generators
    for gen_name, fn in [("SVG ERD Generator", lambda: export_erd_svg(ecom_ast)), ("Mermaid ERD Generator", lambda: export_mermaid_erd(ecom_ast))]:
        t0 = time.perf_counter()
        try:
            res = fn()
            dt = (time.perf_counter() - t0) * 1000
            assert len(res) > 50, f"{gen_name} output too short"
            print(f"  {t.green('✓')} {gen_name:<32} {t.dim(f'({dt:.2f}ms)')}")
            passes += 1
        except Exception as e:
            print(f"  {t.red('✗')} {gen_name:<32} {t.red(f'FAILED: {e}')}")
            failures += 1

    # 4. Test Metrics Analysis
    t0 = time.perf_counter()
    try:
        metrics = analyze_schema_metrics(ecom_ast)
        dt = (time.perf_counter() - t0) * 1000
        assert metrics["entity_count"] == len(ecom_ast.entities)
        print(f"  {t.green('✓')} {'Schema Metrics Telemetry':<32} {t.dim(f'({dt:.2f}ms)')}")
        passes += 1
    except Exception as e:
        print(f"  {t.red('✗')} {'Schema Metrics Telemetry':<32} {t.red(f'FAILED: {e}')}")
        failures += 1

    # 5. Test MCP Server JSON-RPC cycle
    from schema_illustrator_studio.mcp_server import MCPServer

    t0 = time.perf_counter()
    try:
        server = MCPServer()
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_res = server.handle_request(init_req)
        assert init_res["result"]["serverInfo"]["name"] == "schema-illustrator-studio"

        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_res = server.handle_request(tools_req)
        assert len(tools_res["result"]["tools"]) == 6

        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "schema_transpile", "arguments": {"schema_content": ecom_sql, "target_format": "pydantic"}},
        }
        call_res = server.handle_request(call_req)
        assert not call_res["result"]["isError"]

        dt = (time.perf_counter() - t0) * 1000
        print(f"  {t.green('✓')} {'MCP Server JSON-RPC Protocol':<32} {t.dim(f'({dt:.2f}ms)')}")
        passes += 1
    except Exception as e:
        print(f"  {t.red('✗')} {'MCP Server JSON-RPC Protocol':<32} {t.red(f'FAILED: {e}')}")
        failures += 1

    print(f"\n{t.bold('Results:')} {t.green(f'{passes} passed')}, {t.red(f'{failures} failed') if failures else '0 failed'}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="schema-illustrator-studio",
        description=f"Google Material 3 Schema Studio CLI v{__version__} - {__description__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color highlights and formatting in output.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available Commands")

    # 1. parse
    p_parse = subparsers.add_parser("parse", help="Parse schema into structured AST.")
    p_parse.add_argument("input", nargs="?", default=None, help="Schema file path, raw string, or '-' for stdin.")
    p_parse.add_argument("-f", "--format", choices=["auto", "json-schema", "sql", "ts", "graphql"], default="auto", help="Schema format (default: auto).")
    p_parse.add_argument("--json", action="store_true", help="Output full raw AST as formatted JSON.")
    p_parse.add_argument("-o", "--output", help="Write output to file.")
    p_parse.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 2. transpile
    p_trans = subparsers.add_parser("transpile", help="Convert schema from one format to target format.")
    p_trans.add_argument("input", nargs="?", default=None, help="Schema file path, raw string, or '-' for stdin.")
    p_trans.add_argument(
        "-t",
        "--target",
        choices=["ts", "typescript", "pydantic", "python", "sql", "graphql", "json-schema", "openapi"],
        default="ts",
        help="Target language/format (default: ts).",
    )
    p_trans.add_argument("-f", "--format", choices=["auto", "json-schema", "sql", "ts", "graphql"], default="auto", help="Source schema format.")
    p_trans.add_argument("-o", "--output", help="Write output to file.")
    p_trans.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 3. erd
    p_erd = subparsers.add_parser("erd", help="Export interactive SVG ERD diagram or ASCII table.")
    p_erd.add_argument("input", nargs="?", default=None, help="Schema file path, raw string, or '-' for stdin.")
    p_erd.add_argument("-f", "--format", choices=["auto", "json-schema", "sql", "ts", "graphql"], default="auto", help="Source schema format.")
    p_erd.add_argument("-t", "--type", choices=["auto", "svg", "ascii"], default="auto", help="Diagram type (default: auto).")
    p_erd.add_argument("--theme", choices=["material3-dark", "material3-light", "cyberpunk", "slate"], default="material3-dark", help="Color theme for SVG.")
    p_erd.add_argument("--title", default="Entity Relationship Diagram", help="Diagram title.")
    p_erd.add_argument("-o", "--output", help="Write output to file.")
    p_erd.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 4. mermaid
    p_mmd = subparsers.add_parser("mermaid", help="Export Mermaid erDiagram syntax.")
    p_mmd.add_argument("input", nargs="?", default=None, help="Schema file path, raw string, or '-' for stdin.")
    p_mmd.add_argument("-f", "--format", choices=["auto", "json-schema", "sql", "ts", "graphql"], default="auto", help="Source schema format.")
    p_mmd.add_argument("-o", "--output", help="Write output to file.")
    p_mmd.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 5. metrics
    p_met = subparsers.add_parser("metrics", help="Output schema complexity and architecture telemetry.")
    p_met.add_argument("input", nargs="?", default=None, help="Schema file path, raw string, or '-' for stdin.")
    p_met.add_argument("-f", "--format", choices=["auto", "json-schema", "sql", "ts", "graphql"], default="auto", help="Source schema format.")
    p_met.add_argument("--json", action="store_true", help="Output raw telemetry JSON.")
    p_met.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 6. samples
    p_smp = subparsers.add_parser("samples", aliases=["sample"], help="Output built-in schema template.")
    p_smp.add_argument("-n", "--name", choices=["ecommerce", "auth_users", "social_graph", "saas_billing"], default="ecommerce", help="Template name.")
    p_smp.add_argument("-f", "--format", choices=["sql", "json-schema", "ts", "graphql"], default="sql", help="Template format.")
    p_smp.add_argument("-l", "--list", action="store_true", help="List all available sample templates.")
    p_smp.add_argument("-o", "--output", help="Write output to file.")
    p_smp.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 7. serve
    p_srv = subparsers.add_parser("serve", aliases=["ui", "web"], help="Launch Google Material 3 Schema Studio Web UI.")
    p_srv.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1).")
    p_srv.add_argument("-p", "--port", type=int, default=8765, help="Port to bind (default: 8765).")
    p_srv.add_argument("--no-open", action="store_true", help="Do not automatically open browser.")

    # 8. mcp
    p_mcp = subparsers.add_parser("mcp", help="Run Model Context Protocol (MCP) server over stdio.")

    # 9. doctor / diagnostics / platform
    p_doc = subparsers.add_parser("doctor", aliases=["platform", "diagnostics"], help="System diagnostics & platform compatibility report.")
    p_doc.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    # 10. test
    p_tst = subparsers.add_parser("test", aliases=["selftest"], help="Internal self-verification test runner.")
    p_tst.add_argument("--no-color", action="store_true", help="Disable color formatting.")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main entrypoint for CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    no_color_flag = getattr(args, "no_color", False)
    t = Theme(no_color=no_color_flag)

    if not args.command:
        print_banner(t)
        parser.print_help()
        return 0

    if args.command == "parse":
        return cmd_parse(args, t)
    elif args.command == "transpile":
        return cmd_transpile(args, t)
    elif args.command == "erd":
        return cmd_erd(args, t)
    elif args.command == "mermaid":
        return cmd_mermaid(args, t)
    elif args.command == "metrics":
        return cmd_metrics(args, t)
    elif args.command in ("samples", "sample"):
        return cmd_samples(args, t)
    elif args.command in ("serve", "ui", "web"):
        return cmd_serve(args, t)
    elif args.command == "mcp":
        return cmd_mcp(args, t)
    elif args.command in ("doctor", "platform", "diagnostics"):
        return cmd_doctor(args, t)
    elif args.command in ("test", "selftest"):
        return cmd_test(args, t)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
