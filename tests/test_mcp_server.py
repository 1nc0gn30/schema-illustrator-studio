"""Unit tests for Model Context Protocol (MCP) server over JSON-RPC 2.0."""

import json
import pytest

from schema_illustrator_studio.mcp_server import MCPServer


@pytest.fixture
def mcp_server():
    """Create an MCPServer instance for testing."""
    return MCPServer()


def test_mcp_initialize(mcp_server):
    """Test JSON-RPC initialize handshake."""
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }
    resp = mcp_server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "schema-illustrator-studio"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_tools_list(mcp_server):
    """Test tools/list returns registered schema tools."""
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]

    assert "schema_parse" in tool_names
    assert "schema_transpile" in tool_names
    assert "schema_export_erd" in tool_names
    assert "schema_metrics" in tool_names
    assert "schema_sample_templates" in tool_names
    assert "schema_diagnostics" in tool_names


def test_mcp_tool_schema_parse(mcp_server, sample_sql_schema):
    """Test tools/call for schema_parse."""
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "schema_parse",
            "arguments": {
                "schema_content": sample_sql_schema,
                "format": "sql",
            },
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    content_list = resp["result"]["content"]
    assert len(content_list) > 0
    text = content_list[0]["text"]
    data = json.loads(text)
    assert "entities" in data


def test_mcp_tool_schema_transpile(mcp_server, sample_sql_schema):
    """Test tools/call for schema_transpile."""
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "schema_transpile",
            "arguments": {
                "schema_content": sample_sql_schema,
                "target_format": "pydantic",
            },
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "BaseModel" in text or "class " in text


def test_mcp_tool_schema_export_erd_svg(mcp_server, sample_sql_schema):
    """Test tools/call for schema_export_erd as SVG."""
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "schema_export_erd",
            "arguments": {
                "schema_content": sample_sql_schema,
                "diagram_type": "svg",
            },
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "<svg" in text


def test_mcp_tool_schema_export_erd_mermaid(mcp_server, sample_sql_schema):
    """Test tools/call for schema_export_erd as Mermaid."""
    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "schema_export_erd",
            "arguments": {
                "schema_content": sample_sql_schema,
                "diagram_type": "mermaid",
            },
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "erDiagram" in text


def test_mcp_tool_schema_metrics(mcp_server, sample_sql_schema):
    """Test tools/call for schema_metrics."""
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "schema_metrics",
            "arguments": {
                "schema_content": sample_sql_schema,
            },
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    metrics_data = json.loads(text)
    assert "quality_score" in metrics_data or "entity_count" in metrics_data or "total_entities" in metrics_data


def test_mcp_tool_schema_sample_templates(mcp_server):
    """Test tools/call for schema_sample_templates."""
    req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "schema_sample_templates",
            "arguments": {
                "template_name": "ecommerce",
                "format": "sql",
            },
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "CREATE TABLE" in text or "ecommerce" in text.lower()


def test_mcp_tool_schema_diagnostics(mcp_server):
    """Test tools/call for schema_diagnostics."""
    req = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "schema_diagnostics",
            "arguments": {},
        },
    }
    resp = mcp_server.handle_request(req)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    diag = json.loads(text)
    assert diag["service"] == "schema-illustrator-studio"


def test_mcp_invalid_method(mcp_server):
    """Test unknown method returns method not found error."""
    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "non_existent_method_xyz",
        "params": {},
    }
    resp = mcp_server.handle_request(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601
