"""Model Context Protocol (MCP) server over stdio for schema-illustrator-studio.

Implements JSON-RPC 2.0 MCP protocol specifications (version 2024-11-05)
for schema parsing, transpilation, diagram generation, complexity metrics,
sample templates, and system diagnostics with zero third-party dependencies.
"""

from __future__ import annotations

import io
import json
import os
import platform
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, TextIO, Tuple, Union

from schema_illustrator_studio import (
    SAMPLE_TEMPLATES,
    __version__,
    analyze_schema_metrics,
    export_erd_svg,
    export_mermaid_erd,
    get_sample_template,
    list_sample_templates,
    parse_schema,
    transpile_schema,
)
from schema_illustrator_studio.compat import is_termux, is_windows, safe_read_text
from schema_illustrator_studio.models import SchemaAST

MCP_PROTOCOL_VERSION = "2024-11-05"


class JSONRPCError(Exception):
    """Standard JSON-RPC 2.0 error."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


class MCPServer:
    """Model Context Protocol (MCP) Server instance."""

    def __init__(
        self,
        name: str = "schema-illustrator-studio",
        version: str = __version__,
        stdin: Optional[TextIO] = None,
        stdout: Optional[TextIO] = None,
        stderr: Optional[TextIO] = None,
    ) -> None:
        self.name = name
        self.version = version
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.is_initialized = False

        self._tools: Dict[str, Dict[str, Any]] = {}
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._prompts: Dict[str, Dict[str, Any]] = {}

        self._register_default_tools()
        self._register_default_resources()
        self._register_default_prompts()

    def log(self, message: str) -> None:
        """Log diagnostic information to stderr only."""
        if os.environ.get("SCHEMA_STUDIO_DEBUG"):
            self.stderr.write(f"[MCP-SERVER] {message}\n")
            self.stderr.flush()

    def _register_default_tools(self) -> None:
        """Register the 6 core schema tools."""
        self.register_tool(
            name="schema_parse",
            description="Ingest raw schema (JSON Schema, SQL DDL, TypeScript, GraphQL) and return structured AST representation with entities, fields, types, constraints, and relationships.",
            input_schema={
                "type": "object",
                "properties": {
                    "schema_content": {
                        "type": "string",
                        "description": "The raw schema definition string or filesystem path to a schema file.",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["auto", "json-schema", "sql", "ts", "graphql"],
                        "description": "Format of the schema. Defaults to 'auto' detection.",
                    },
                },
                "required": ["schema_content"],
            },
            handler=self._tool_schema_parse,
        )

        self.register_tool(
            name="schema_transpile",
            description="Convert schema from one format to target format (TypeScript, Pydantic, SQL, GraphQL, JSON Schema, OpenAPI).",
            input_schema={
                "type": "object",
                "properties": {
                    "schema_content": {
                        "type": "string",
                        "description": "The raw schema definition string or file path.",
                    },
                    "target_format": {
                        "type": "string",
                        "enum": [
                            "ts",
                            "typescript",
                            "pydantic",
                            "python",
                            "sql",
                            "graphql",
                            "json-schema",
                            "openapi",
                        ],
                        "description": "Target language or format to transpile to.",
                    },
                    "source_format": {
                        "type": "string",
                        "enum": ["auto", "json-schema", "sql", "ts", "graphql"],
                        "description": "Source format (optional, auto-detected if not provided).",
                    },
                },
                "required": ["schema_content", "target_format"],
            },
            handler=self._tool_schema_transpile,
        )

        self.register_tool(
            name="schema_export_erd",
            description="Generate an interactive SVG ERD diagram or Mermaid ER diagram from schema.",
            input_schema={
                "type": "object",
                "properties": {
                    "schema_content": {
                        "type": "string",
                        "description": "The raw schema definition string or file path.",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["auto", "json-schema", "sql", "ts", "graphql"],
                        "description": "Source schema format.",
                    },
                    "diagram_type": {
                        "type": "string",
                        "enum": ["svg", "mermaid", "ascii"],
                        "description": "Type of diagram: 'svg' (vector graphic), 'mermaid' (erDiagram markdown), or 'ascii' (terminal box diagram). Defaults to 'svg'.",
                    },
                    "theme": {
                        "type": "string",
                        "enum": ["material3-dark", "material3-light", "cyberpunk", "slate"],
                        "description": "Color theme for SVG diagram. Defaults to 'material3-dark'.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the diagram. Defaults to 'Entity Relationship Diagram'.",
                    },
                },
                "required": ["schema_content"],
            },
            handler=self._tool_schema_export_erd,
        )

        self.register_tool(
            name="schema_metrics",
            description="Analyze schema complexity, entity count, field count, depth, normalization score, and generate architectural recommendations.",
            input_schema={
                "type": "object",
                "properties": {
                    "schema_content": {
                        "type": "string",
                        "description": "The raw schema definition string or file path.",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["auto", "json-schema", "sql", "ts", "graphql"],
                        "description": "Source schema format.",
                    },
                },
                "required": ["schema_content"],
            },
            handler=self._tool_schema_metrics,
        )

        self.register_tool(
            name="schema_sample_templates",
            description="Return sample schema templates (E-Commerce, Auth/Users, Social Graph, SaaS Billing) in various formats.",
            input_schema={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "enum": ["all", "ecommerce", "auth_users", "social_graph", "saas_billing"],
                        "description": "Name of template or 'all' to list all available templates.",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["sql", "json-schema", "ts", "graphql"],
                        "description": "Format for template. Defaults to 'sql'.",
                    },
                },
            },
            handler=self._tool_schema_sample_templates,
        )

        self.register_tool(
            name="schema_diagnostics",
            description="System diagnostics, runtime capabilities, supported parser formats, transpiler targets, and platform environment report.",
            input_schema={
                "type": "object",
                "properties": {},
            },
            handler=self._tool_schema_diagnostics,
        )

    def _register_default_resources(self) -> None:
        """Register built-in schema template resources."""
        for name, data in SAMPLE_TEMPLATES.items():
            uri = f"schema://templates/{name}"
            self._resources[uri] = {
                "uri": uri,
                "name": data["name"],
                "description": data["description"],
                "mimeType": "application/sql",
                "content": data["sql"],
            }

    def _register_default_prompts(self) -> None:
        """Register default prompts for AI assistance."""
        self._prompts["architect_schema"] = {
            "name": "architect_schema",
            "description": "Design an enterprise-grade relational or document schema based on product requirements.",
            "arguments": [
                {
                    "name": "domain",
                    "description": "Business domain (e.g. Healthcare, Fintech, Marketplace, IoT)",
                    "required": True,
                },
                {"name": "requirements", "description": "Specific entities and requirements", "required": False},
            ],
        }
        self._prompts["review_schema_normalization"] = {
            "name": "review_schema_normalization",
            "description": "Review a schema for 1NF/2NF/3NF normalization, foreign key integrity, indexing, and anti-patterns.",
            "arguments": [
                {"name": "schema", "description": "Schema definition string or SQL DDL", "required": True},
            ],
        }

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """Register an MCP tool."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    # Tool Handlers
    def _tool_schema_parse(self, args: Dict[str, Any]) -> str:
        content = args.get("schema_content", "")
        fmt = args.get("format")
        if fmt == "auto":
            fmt = None

        ast = parse_schema(content, format_hint=fmt)
        return ast.to_json(indent=2)

    def _tool_schema_transpile(self, args: Dict[str, Any]) -> str:
        content = args.get("schema_content", "")
        target = args.get("target_format", "typescript")
        source_fmt = args.get("source_format")
        if source_fmt == "auto":
            source_fmt = None

        code = transpile_schema(content, target_format=target, source_format=source_fmt)
        return code

    def _tool_schema_export_erd(self, args: Dict[str, Any]) -> str:
        content = args.get("schema_content", "")
        fmt = args.get("format")
        if fmt == "auto":
            fmt = None
        diagram_type = args.get("diagram_type", "svg").lower()
        theme = args.get("theme", "material3-dark")
        title = args.get("title", "Entity Relationship Diagram")

        ast = parse_schema(content, format_hint=fmt)

        if diagram_type == "mermaid":
            return export_mermaid_erd(ast)
        elif diagram_type == "ascii":
            return self._render_ascii_erd(ast)
        else:
            return export_erd_svg(ast, title=title, theme=theme)

    def _render_ascii_erd(self, ast: SchemaAST) -> str:
        """Render a clean ASCII diagram for terminal/plain text display."""
        lines: List[str] = [f"┌─ {ast.name or 'Schema'} (ASCII ERD) " + "─" * 40]
        for ent_name, ent in ast.entities.items():
            badge = "[ENUM]" if ent.is_enum else ("[UNION]" if ent.is_union else "[TABLE]")
            lines.append(f"\n┌── {ent.name} {badge} " + "─" * (35 - len(ent.name) - len(badge)))
            for f in ent.fields:
                pk_marker = "🔑 PK" if f.is_primary_key else ("🔗 FK" if f.is_foreign_key or f.target_entity else "  ")
                opt_marker = "NULL" if f.is_nullable else "NOT NULL"
                lines.append(f"│  {pk_marker:<6} {f.name:<20} {f.display_type():<15} {opt_marker}")
            lines.append("└──" + "─" * 48)

        if ast.relationships:
            lines.append("\nRelationships:")
            for rel in ast.relationships:
                lines.append(
                    f"  {rel.source_entity}.{rel.source_field} ──({rel.cardinality})──> {rel.target_entity}.{rel.target_field or 'id'}"
                )
        return "\n".join(lines)

    def _tool_schema_metrics(self, args: Dict[str, Any]) -> str:
        content = args.get("schema_content", "")
        fmt = args.get("format")
        if fmt == "auto":
            fmt = None

        ast = parse_schema(content, format_hint=fmt)
        metrics = analyze_schema_metrics(ast)
        return json.dumps(metrics, indent=2)

    def _tool_schema_sample_templates(self, args: Dict[str, Any]) -> str:
        template_name = args.get("template_name", "all")
        fmt = args.get("format", "sql")

        if template_name in ("all", "", None):
            listing = list_sample_templates()
            return json.dumps(listing, indent=2)
        else:
            tmpl = get_sample_template(template_name, format_name=fmt)
            return tmpl

    def _tool_schema_diagnostics(self, args: Dict[str, Any]) -> str:
        diag = {
            "service": "schema-illustrator-studio",
            "version": self.version,
            "mcp_protocol_version": MCP_PROTOCOL_VERSION,
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "os_environment": {
                "is_windows": is_windows(),
                "is_termux": is_termux(),
                "terminal_encoding": getattr(sys.stdout, "encoding", "utf-8"),
            },
            "registered_tools_count": len(self._tools),
            "supported_parsers": ["json-schema", "openapi", "sql", "typescript", "graphql"],
            "supported_transpilers": [
                "typescript",
                "pydantic",
                "sql",
                "graphql",
                "json-schema",
                "openapi",
                "mermaid",
                "svg",
            ],
            "sample_templates": list(SAMPLE_TEMPLATES.keys()),
        }
        return json.dumps(diag, indent=2)

    # JSON-RPC Dispatcher
    def handle_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC 2.0 request and return the response."""
        if not isinstance(request_data, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: root must be object"},
            }

        jsonrpc_ver = request_data.get("jsonrpc")
        req_id = request_data.get("id")
        method = request_data.get("method")
        params = request_data.get("params", {})

        if jsonrpc_ver != "2.0" or not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: missing jsonrpc or method"},
            }

        self.log(f"Handling method: {method}")

        # Notification handling (methods without id)
        is_notification = "id" not in request_data or req_id is None

        try:
            result = self._dispatch_method(method, params)
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except JSONRPCError as e:
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": req_id, "error": e.to_dict()}
        except Exception as e:
            self.log(f"Internal error executing {method}: {e}\n{traceback.format_exc()}")
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                    "data": traceback.format_exc(),
                },
            }

    def _dispatch_method(self, method: str, params: Dict[str, Any]) -> Any:
        """Internal dispatch of MCP methods."""
        if method == "initialize":
            self.is_initialized = True
            return {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }

        if method in ("notifications/initialized", "initialized"):
            self.is_initialized = True
            return {}

        if method == "ping":
            return {}

        if method == "tools/list":
            tools_list = []
            for t in self._tools.values():
                tools_list.append(
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["inputSchema"],
                    }
                )
            return {"tools": tools_list}

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name or tool_name not in self._tools:
                raise JSONRPCError(-32602, f"Unknown tool: {tool_name}")

            tool_def = self._tools[tool_name]
            handler = tool_def["handler"]

            try:
                out = handler(arguments)
                text_response = str(out) if not isinstance(out, str) else out
                return {
                    "content": [{"type": "text", "text": text_response}],
                    "isError": False,
                }
            except Exception as err:
                self.log(f"Tool {tool_name} failed: {err}")
                return {
                    "content": [{"type": "text", "text": f"Error executing tool '{tool_name}': {str(err)}"}],
                    "isError": True,
                }

        if method == "resources/list":
            resources_list = [
                {
                    "uri": r["uri"],
                    "name": r["name"],
                    "description": r["description"],
                    "mimeType": r.get("mimeType", "text/plain"),
                }
                for r in self._resources.values()
            ]
            return {"resources": resources_list}

        if method == "resources/read":
            uri = params.get("uri")
            if not uri or uri not in self._resources:
                raise JSONRPCError(-32602, f"Resource not found: {uri}")
            r = self._resources[uri]
            return {
                "contents": [
                    {
                        "uri": r["uri"],
                        "mimeType": r.get("mimeType", "text/plain"),
                        "text": r.get("content", ""),
                    }
                ]
            }

        if method == "prompts/list":
            prompts_list = [
                {
                    "name": p["name"],
                    "description": p["description"],
                    "arguments": p.get("arguments", []),
                }
                for p in self._prompts.values()
            ]
            return {"prompts": prompts_list}

        if method == "prompts/get":
            p_name = params.get("name")
            if not p_name or p_name not in self._prompts:
                raise JSONRPCError(-32602, f"Prompt not found: {p_name}")
            p = self._prompts[p_name]
            args = params.get("arguments", {})
            return {
                "description": p["description"],
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Execute schema task for '{p_name}' with parameters: {json.dumps(args, indent=2)}",
                        },
                    }
                ],
            }

        raise JSONRPCError(-32601, f"Method not found: {method}")

    # Transport / Stream Loop
    def run_stdio_loop(self) -> None:
        """Run the MCP JSON-RPC server loop over stdin/stdout."""
        self.log(f"Starting {self.name} v{self.version} stdio loop...")

        while True:
            try:
                line = self.stdin.readline()
                if not line:
                    # End of file / stream closed
                    break

                line_str = line.strip()
                if not line_str:
                    continue

                # Support Content-Length header framing if client sends HTTP-style headers
                if line_str.lower().startswith("content-length:"):
                    parts = line_str.split(":", 1)
                    length = int(parts[1].strip())
                    # Consume following blank line if present
                    blank_line = self.stdin.readline()
                    if blank_line.strip():
                        # Not blank, could be another header
                        pass
                    payload_bytes = self.stdin.read(length)
                    raw_json = payload_bytes
                else:
                    raw_json = line_str

                try:
                    req_obj = json.loads(raw_json)
                except json.JSONDecodeError as err:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {str(err)}"},
                    }
                    self._send_response(err_resp)
                    continue

                response = self.handle_request(req_obj)
                if response is not None:
                    self._send_response(response)

            except KeyboardInterrupt:
                self.log("Server interrupted by user. Exiting.")
                break
            except Exception as e:
                self.log(f"Unexpected loop exception: {e}")

    def _send_response(self, response_dict: Dict[str, Any]) -> None:
        """Write JSON-RPC response to stdout and flush."""
        out_str = json.dumps(response_dict, separators=(",", ":"))
        self.stdout.write(out_str + "\n")
        self.stdout.flush()


def run_mcp_server(
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> None:
    """Run the MCP Server over stdio."""
    server = MCPServer(stdin=stdin, stdout=stdout, stderr=stderr)
    server.run_stdio_loop()


if __name__ == "__main__":
    run_mcp_server()
