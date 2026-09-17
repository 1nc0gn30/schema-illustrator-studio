"""Integration tests for Google Schema Studio UI Server and REST API."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request
import pytest

from schema_illustrator_studio.ui_server import start_server


def get_free_port() -> int:
    """Find an available TCP port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """Start UI server on a background thread for testing."""
    port = get_free_port()
    host = "127.0.0.1"
    server = start_server(host=host, port=port, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = f"http://{host}:{port}"
    yield base_url

    server.shutdown()
    server.server_close()


def test_get_root_ui(live_server):
    """Test GET / returns studio HTML."""
    req = urllib.request.Request(f"{live_server}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "Google Schema Studio" in content or "<html" in content


def test_get_samples_api(live_server):
    """Test GET /api/samples returns sample schemas."""
    req = urllib.request.Request(f"{live_server}/api/samples")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "ecommerce" in data
        assert "auth" in data


def test_get_stats_api(live_server):
    """Test GET /api/stats returns server health and diagnostic metadata."""
    req = urllib.request.Request(f"{live_server}/api/stats")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "healthy"
        assert "version" in data


def test_post_parse_api(live_server, sample_sql_schema):
    """Test POST /api/parse."""
    payload = json.dumps({"schema": sample_sql_schema, "format": "sql"}).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/parse",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("success") is True
        assert data.get("entity_count") > 0


def test_post_transpile_api(live_server, sample_sql_schema):
    """Test POST /api/transpile."""
    for target in ["typescript", "pydantic", "sql", "graphql", "json-schema"]:
        payload = json.dumps({"schema": sample_sql_schema, "target": target}).encode("utf-8")
        req = urllib.request.Request(
            f"{live_server}/api/transpile",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("success") is True
            assert len(data.get("code", "")) > 0


def test_post_erd_api(live_server, sample_sql_schema):
    """Test POST /api/erd for SVG generation."""
    payload = json.dumps({"schema": sample_sql_schema, "theme": "light"}).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/erd",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("success") is True
        assert "<svg" in data.get("svg", "")


def test_post_erd_raw_api(live_server, sample_sql_schema):
    """Test POST /api/erd?raw=1 returns raw image/svg+xml."""
    payload = json.dumps({"schema": sample_sql_schema}).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/erd?raw=1",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "image/svg+xml" in content_type
        body = resp.read().decode("utf-8")
        assert "<svg" in body


def test_post_mermaid_api(live_server, sample_sql_schema):
    """Test POST /api/mermaid."""
    payload = json.dumps({"schema": sample_sql_schema}).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/mermaid",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("success") is True
        assert "erDiagram" in data.get("mermaid", "")


def test_post_metrics_api(live_server, sample_sql_schema):
    """Test POST /api/metrics."""
    payload = json.dumps({"schema": sample_sql_schema}).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/metrics",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("success") is True
        assert "metrics" in data


def test_cors_options(live_server):
    """Test OPTIONS method for CORS pre-flight."""
    req = urllib.request.Request(f"{live_server}/api/parse", method="OPTIONS")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


def test_invalid_request_handling(live_server):
    """Test error handling for bad JSON and missing fields."""
    # Bad JSON
    req = urllib.request.Request(
        f"{live_server}/api/parse",
        data=b"not a valid json string",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 400

    # 404 Endpoint
    req_404 = urllib.request.Request(f"{live_server}/api/unknown_endpoint_xyz")
    with pytest.raises(urllib.error.HTTPError) as exc_info404:
        urllib.request.urlopen(req_404)
    assert exc_info404.value.code == 404
