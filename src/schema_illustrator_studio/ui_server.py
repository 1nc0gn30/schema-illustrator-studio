"""Pure Python Threading HTTP Server serving Schema Illustrator Studio Web UI and REST API.

Provides local-first Web UI hosting and endpoints for schema parsing, transpilation,
ERD SVG rendering, Mermaid diagram generation, and complexity telemetry with zero
third-party runtime dependencies.
"""

from __future__ import annotations

import json
import mimetypes
import os
import platform
import sys
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict, Optional, Tuple, Union

from schema_illustrator_studio.compat import is_termux, is_windows, safe_normalize_path, safe_read_text
from schema_illustrator_studio.models import SchemaAST

# Sample Schemas for Studio UI
SAMPLE_SCHEMAS: Dict[str, Dict[str, str]] = {
    "ecommerce": {
        "name": "E-Commerce Platform",
        "format": "sql",
        "description": "Relational schema for products, categories, users, orders, and order items.",
        "schema": """CREATE TABLE users (
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
);""",
    },
    "auth": {
        "name": "User Auth & RBAC",
        "format": "json-schema",
        "description": "JSON Schema definition for users, roles, sessions, and MFA security.",
        "schema": json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "AuthAndSecuritySchema",
                "$defs": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "format": "uuid"},
                            "username": {"type": "string", "minLength": 3},
                            "email": {"type": "string", "format": "email"},
                            "is_mfa_enabled": {"type": "boolean", "default": False},
                            "role_id": {"type": "string", "$ref": "#/$defs/Role"},
                        },
                        "required": ["id", "username", "email"],
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
                            "token": {"type": "string"},
                            "user_id": {"type": "string", "$ref": "#/$defs/User"},
                            "expires_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["token", "user_id"],
                    },
                },
            },
            indent=2,
        ),
    },
    "social": {
        "name": "Social Network Graph",
        "format": "graphql",
        "description": "GraphQL SDL schema representing Users, Profiles, Posts, and Comments.",
        "schema": """type Profile {
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
}""",
    },
    "saas": {
        "name": "SaaS Subscriptions & Invoicing",
        "format": "typescript",
        "description": "TypeScript domain model for Organizations, Subscription Plans, Members, and Invoices.",
        "schema": """export interface Organization {
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
}""",
    },
}

# Embedded Fallback UI HTML in case public/index.html is missing
EMBEDDED_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Schema Illustrator Studio (Embedded Mode)</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8f9fa; color: #202124; padding: 30px; margin: 0; }
    .card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(60,64,67,0.15); max-width: 800px; margin: 0 auto; }
    h1 { color: #1a73e8; font-size: 24px; margin-top: 0; }
    textarea { width: 100%; height: 200px; font-family: monospace; padding: 12px; border: 1px solid #dadce0; border-radius: 8px; box-sizing: border-box; }
    button { background: #1a73e8; color: white; border: none; padding: 10px 20px; border-radius: 20px; font-weight: 500; cursor: pointer; margin-top: 12px; }
    button:hover { background: #1557b0; }
    pre { background: #f1f3f4; padding: 16px; border-radius: 8px; overflow-x: auto; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Schema Illustrator Studio (Embedded UI)</h1>
    <p>Universal Schema Illustrator, Transpiler & Diagram Engine</p>
    <textarea id="src" placeholder="Paste SQL DDL, JSON Schema, TypeScript, or GraphQL here...">CREATE TABLE users (id UUID PRIMARY KEY, name VARCHAR(100));</textarea>
    <br/>
    <button onclick="parse()">Parse Schema</button>
    <button onclick="transpile()">Transpile to Pydantic</button>
    <button onclick="metrics()">Calculate Metrics</button>
    <pre id="out">Output will appear here...</pre>
  </div>
  <script>
    async function parse() {
      const res = await fetch('/api/parse', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({schema: src}) });
      document.getElementById('out').textContent = JSON.stringify(await res.json(), null, 2);
    }
    async function transpile() {
      const src = document.getElementById('src').value;
      const res = await fetch('/api/transpile', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({schema: src, target: 'pydantic'}) });
      const data = await res.json();
      document.getElementById('out').textContent = data.code || JSON.stringify(data, null, 2);
    }
    async function metrics() {
      const src = document.getElementById('src').value;
      const res = await fetch('/api/metrics', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({schema: src}) });
      document.getElementById('out').textContent = JSON.stringify(await res.json(), null, 2);
    }
  </script>
</body>
</html>"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for responsive Studio UI and API requests."""

    daemon_threads = True
    allow_reuse_address = True


class StudioRequestHandler(BaseHTTPRequestHandler):
    """Request handler for Schema Illustrator Studio UI and REST APIs."""

    server_version = "SchemaStudioServer/0.1.0"

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests for UI assets, samples, and diagnostics."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/samples":
            self._send_json(SAMPLE_SCHEMAS)
            return

        if path in ("/api/stats", "/api/diagnostics", "/api/health"):
            stats_data = {
                "status": "healthy",
                "version": "0.1.0",
                "service": "schema-illustrator-studio",
                "platform": platform.platform(),
                "python_version": sys.version.split()[0],
                "supported_parsers": ["json-schema", "openapi", "sql", "typescript", "graphql"],
                "supported_transpilers": ["typescript", "pydantic", "sql", "graphql", "json-schema", "mermaid"],
            }
            self._send_json(stats_data)
            return

        # Serve static UI files
        self._serve_static_file(path)

    def do_POST(self) -> None:
        """Handle POST API requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self._send_json({"success": False, "error": "Empty request body"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            body_bytes = self.rfile.read(content_length)
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            self._send_json({"success": False, "error": f"Invalid JSON payload: {e}"}, status=HTTPStatus.BAD_REQUEST)
            return

        schema_text = req_data.get("schema", "")
        format_hint = req_data.get("format", "auto")

        if not schema_text:
            self._send_json({"success": False, "error": "Missing 'schema' in request payload"}, status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/diff":
            target_text = req_data.get("target_schema", "")
            if not target_text:
                self._send_json({"success": False, "error": "Missing 'target_schema' for /api/diff"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                from schema_illustrator_studio.diff_engine import diff_schemas
                ast_base = self._parse_ast(schema_text, format_hint)
                ast_target = self._parse_ast(target_text, req_data.get("target_format", "auto"))
                report = diff_schemas(ast_base, ast_target)
                self._send_json({"success": True, "diff": report.to_dict()})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/parse":
            self._handle_parse(schema_text, format_hint)
        elif path == "/api/transpile":
            target = req_data.get("target", "typescript")
            self._handle_transpile(schema_text, format_hint, target)
        elif path == "/api/erd":
            theme = req_data.get("theme", "light")
            self._handle_erd(schema_text, format_hint, theme, parsed_url)
        elif path == "/api/mermaid":
            self._handle_mermaid(schema_text, format_hint)
        elif path == "/api/metrics":
            self._handle_metrics(schema_text, format_hint)
        elif path == "/api/mock":
            self._handle_mock(schema_text, format_hint, req_data)
        else:
            self._send_json({"success": False, "error": f"Endpoint not found: {path}"}, status=HTTPStatus.NOT_FOUND)

    def _parse_ast(self, schema_text: str, format_hint: str) -> SchemaAST:
        """Helper to invoke schema parser."""
        try:
            from schema_illustrator_studio.parsers.unified import parse_schema

            fmt = None if format_hint in ("auto", "", None) else format_hint
            return parse_schema(schema_text, format_hint=fmt)
        except Exception as e:
            # Try top-level parse_schema if available
            try:
                from schema_illustrator_studio import parse_schema

                fmt = None if format_hint in ("auto", "", None) else format_hint
                return parse_schema(schema_text, format_hint=fmt)
            except Exception:
                raise e

    def _handle_parse(self, schema_text: str, format_hint: str) -> None:
        """Handle /api/parse."""
        try:
            ast = self._parse_ast(schema_text, format_hint)
            self._send_json(
                {
                    "success": True,
                    "ast": ast.to_dict(),
                    "entity_count": len(ast.entities),
                    "relationship_count": len(ast.relationships),
                }
            )
        except Exception as err:
            self._send_json({"success": False, "error": str(err)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_transpile(self, schema_text: str, format_hint: str, target: str) -> None:
        """Handle /api/transpile."""
        try:
            ast = self._parse_ast(schema_text, format_hint)
            code = self._transpile_ast(ast, target)
            self._send_json({"success": True, "target": target, "code": code})
        except Exception as err:
            self._send_json({"success": False, "error": str(err)}, status=HTTPStatus.BAD_REQUEST)

    def _transpile_ast(self, ast: SchemaAST, target: str) -> str:
        """Transpile AST to requested language/format."""
        from schema_illustrator_studio.transpilers import transpile
        return transpile(ast, target)

    def _handle_erd(self, schema_text: str, format_hint: str, theme: str, parsed_url: urllib.parse.ParseResult) -> None:
        """Handle /api/erd."""
        try:
            ast = self._parse_ast(schema_text, format_hint)
            try:
                from schema_illustrator_studio.diagram_engine import generate_erd_svg

                svg_content = generate_erd_svg(ast, theme=theme)
            except Exception:
                from schema_illustrator_studio import export_erd_svg

                svg_content = export_erd_svg(ast)

            # Check if client requested raw SVG
            query_params = urllib.parse.parse_qs(parsed_url.query)
            accept_header = self.headers.get("Accept", "")
            if "raw" in query_params or "image/svg+xml" in accept_header:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(svg_content.encode("utf-8"))
            else:
                self._send_json({"success": True, "svg": svg_content, "entity_count": len(ast.entities)})
        except Exception as err:
            self._send_json({"success": False, "error": str(err)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_mermaid(self, schema_text: str, format_hint: str) -> None:
        """Handle /api/mermaid."""
        try:
            ast = self._parse_ast(schema_text, format_hint)
            try:
                from schema_illustrator_studio.diagram_engine import generate_mermaid_erd

                mermaid_code = generate_mermaid_erd(ast)
            except Exception:
                from schema_illustrator_studio import export_mermaid_erd

                mermaid_code = export_mermaid_erd(ast)
            self._send_json({"success": True, "mermaid": mermaid_code})
        except Exception as err:
            self._send_json({"success": False, "error": str(err)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_metrics(self, schema_text: str, format_hint: str) -> None:
        """Handle /api/metrics."""
        try:
            ast = self._parse_ast(schema_text, format_hint)
            try:
                from schema_illustrator_studio.metrics import analyze_schema_metrics

                metrics_res = analyze_schema_metrics(ast)
                if hasattr(metrics_res, "to_dict"):
                    m_data = metrics_res.to_dict()
                elif isinstance(metrics_res, dict):
                    m_data = metrics_res
                else:
                    m_data = {
                        "entity_count": len(ast.entities),
                        "relationship_count": len(ast.relationships),
                        "total_fields": sum(len(e.fields) for e in ast.entities.values()),
                    }
            except Exception:
                from schema_illustrator_studio import analyze_schema_metrics

                metrics_res = analyze_schema_metrics(ast)
                m_data = metrics_res.to_dict() if hasattr(metrics_res, "to_dict") else metrics_res
            self._send_json({"success": True, "metrics": m_data})
        except Exception as err:
            self._send_json({"success": False, "error": str(err)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_mock(self, schema_text: str, format_hint: str, req_data: Dict[str, Any]) -> None:
        """Handle /api/mock for synthetic mock data generation."""
        try:
            from schema_illustrator_studio.mock_generator import MockDataConfig, generate_mock_data

            ast = self._parse_ast(schema_text, format_hint)
            rows = int(req_data.get("rows", 5))
            seed = int(req_data.get("seed", 42))
            include_nulls = bool(req_data.get("include_nulls", False))
            out_format = str(req_data.get("output_format", "sql")).lower()

            config = MockDataConfig(rows_per_entity=rows, seed=seed, include_nulls=include_nulls)
            dataset = generate_mock_data(ast, config=config)

            if out_format == "json":
                self._send_json({"success": True, "format": "json", "data": dataset.to_dict(), "entities": dataset.generation_order})
            elif out_format == "csv":
                self._send_json({"success": True, "format": "csv", "csv_tables": dataset.to_csv_dict(), "entities": dataset.generation_order})
            else:
                self._send_json({"success": True, "format": "sql", "sql": dataset.to_sql(), "entities": dataset.generation_order})
        except Exception as err:
            self._send_json({"success": False, "error": str(err)}, status=HTTPStatus.BAD_REQUEST)

    def _serve_static_file(self, req_path: str) -> None:
        """Serve public directory static files or embedded fallback UI."""
        if req_path in ("/", "", "/index.html"):
            req_path = "/index.html"

        # Search for public directory in various locations
        possible_roots = [
            Path.cwd() / "public",
            Path(__file__).resolve().parent.parent.parent / "public",
            Path(__file__).resolve().parent / "public",
        ]

        found_file: Optional[Path] = None
        for root in possible_roots:
            candidate = safe_normalize_path(root / req_path.lstrip("/"))
            if candidate.exists() and candidate.is_file():
                found_file = candidate
                break

        if found_file:
            content_type, _ = mimetypes.guess_type(str(found_file))
            if not content_type:
                content_type = "application/octet-stream"
            if content_type.startswith("text/") or content_type in ("application/javascript", "application/json", "image/svg+xml"):
                content_type += "; charset=utf-8"

            try:
                data_bytes = found_file.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(data_bytes)
                return
            except Exception:
                pass

        # If index.html was requested and not found on disk, serve embedded UI
        if req_path == "/index.html":
            html_bytes = EMBEDDED_FALLBACK_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        self._send_json({"error": "File not found", "path": req_path}, status=HTTPStatus.NOT_FOUND)

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        """Send a JSON HTTP response."""
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(json_bytes)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json_bytes)

    def _send_cors_headers(self) -> None:
        """Send permissive CORS headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept")

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP request console logging unless debugging."""
        if os.environ.get("SCHEMA_STUDIO_DEBUG"):
            super().log_message(format, *args)


def start_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
    quiet: bool = False,
) -> ThreadedHTTPServer:
    """Instantiate and start the Schema Studio Web UI HTTP Server."""
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, StudioRequestHandler)

    url = f"http://{host}:{port}/"
    if not quiet:
        print(f"🚀 Schema Illustrator Studio UI Server running at: {url}")
        print(f"   API Endpoints:")
        print(f"   - POST {url}api/parse")
        print(f"   - POST {url}api/transpile")
        print(f"   - POST {url}api/erd")
        print(f"   - POST {url}api/mermaid")
        print(f"   - POST {url}api/metrics")
        print(f"   - GET  {url}api/samples")
        print(f"   - GET  {url}api/stats")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    return httpd


def run_standalone(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Run server blocking until KeyboardInterrupt."""
    server = start_server(host=host, port=port, open_browser=open_browser)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Schema Illustrator Studio UI Server...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8765))
    run_standalone(host=host, port=port, open_browser=True)
