#!/usr/bin/env python3
"""Schema Illustrator Studio Sovereign Server Launcher."""
import os
import sys
from pathlib import Path

# Add src to pythonpath
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from schema_illustrator_studio.ui_server import start_server

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Schema Illustrator Studio Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", "-p", type=int, default=8099, help="Port to listen on (default: 8099)")
    args = parser.parse_args()

    print(f"Starting Schema Illustrator Studio on {args.host}:{args.port}...")
    server = start_server(host=args.host, port=args.port, open_browser=False)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Schema Illustrator Studio Server...")
        server.server_close()
