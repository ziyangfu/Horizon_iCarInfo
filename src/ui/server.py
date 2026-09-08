"""Lightweight, zero-dependency HTTP server for the Horizon_iCarInfo Dashboard.

Serves static UI assets and provides REST API endpoints for accessing
structured chassis intelligence digests and whitelist configurations.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, unquote, urlparse

from src.ui.parser import list_all_reports, parse_summary_markdown

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = BASE_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SUMMARIES_DIR = DATA_DIR / "summaries"
WHITELIST_FILE = DATA_DIR / "vmc_whitelist.json"


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving dashboard static files and JSON APIs."""

    def __init__(self, *args, **kwargs):
        # Serve static assets from src/ui/static
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # API routing
        if path.startswith("/api/"):
            self.handle_api(path, parsed_url.query)
            return

        # Single-Page-App fallback / static root
        if path in ("", "/"):
            self.serve_file(STATIC_DIR / "index.html", "text/html")
            return

        # Direct file requests in /static or root
        super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/whitelist":
            self.handle_save_whitelist()
            return

        self.send_json({"code": 404, "message": "API endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def handle_save_whitelist(self) -> None:
        """Handle updating the data/vmc_whitelist.json file."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_json({"code": 400, "message": "Empty request body"}, status=HTTPStatus.BAD_REQUEST)
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            # Validation
            if not isinstance(data, dict):
                self.send_json({"code": 400, "message": "Root element must be a JSON object"}, status=HTTPStatus.BAD_REQUEST)
                return

            if "topics" not in data or "suppliers" not in data:
                self.send_json({"code": 400, "message": "Missing required keys: topics or suppliers"}, status=HTTPStatus.BAD_REQUEST)
                return

            # Create backup if file exists
            if WHITELIST_FILE.exists():
                backup_file = WHITELIST_FILE.with_suffix(".json.bak")
                try:
                    backup_file.write_text(WHITELIST_FILE.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception as e:
                    sys.stderr.write(f"[Horizon Dashboard] Backup warning: {e}\n")

            # Write updated JSON
            with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.send_json({
                "code": 0,
                "message": "白名单配置保存成功，系统热重载生效！",
                "stats": {
                    "p0_topics_count": len(data.get("topics", {}).get("p0_core", [])),
                    "p1_topics_count": len(data.get("topics", {}).get("p1_strongly_related", [])),
                    "p0_suppliers_count": len(data.get("suppliers", {}).get("p0_tier1_core", [])),
                    "p1_suppliers_count": len(data.get("suppliers", {}).get("p1_tier1_oem_advanced", [])),
                }
            })
        except json.JSONDecodeError as e:
            self.send_json({"code": 400, "message": f"Invalid JSON format: {e}"}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            self.send_json({"code": 500, "message": f"Failed to save whitelist: {e}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


    def handle_api(self, path: str, query_string: str) -> None:
        """Route and execute REST API requests."""
        if path == "/api/reports":
            reports = list_all_reports(SUMMARIES_DIR)
            self.send_json({"code": 0, "data": reports})
            return

        if path.startswith("/api/reports/"):
            filename = unquote(path[len("/api/reports/"):]).strip()
            # Security check: prevent directory traversal
            if "/" in filename or "\\" in filename or ".." in filename:
                self.send_json({"code": 400, "message": "Invalid filename"}, status=HTTPStatus.BAD_REQUEST)
                return

            report_path = SUMMARIES_DIR / filename
            if not report_path.exists() or not report_path.is_file():
                self.send_json({"code": 404, "message": "Report not found"}, status=HTTPStatus.NOT_FOUND)
                return

            try:
                content = report_path.read_text(encoding="utf-8")
                parsed_data = parse_summary_markdown(content, filename)
                self.send_json({"code": 0, "data": parsed_data})
            except Exception as e:
                self.send_json({"code": 500, "message": f"Parse error: {e}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if path == "/api/whitelist":
            if not WHITELIST_FILE.exists():
                self.send_json({"code": 0, "data": {"topics": {}, "suppliers": {}, "total_topics": 0, "total_suppliers": 0}})
                return

            try:
                with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Summarize counts for dashboard presentation
                topics = data.get("topics", {})
                suppliers = data.get("suppliers", {})
                categories = data.get("recommended_categories", [])

                summary = {
                    "raw_config": data,
                    "topics": topics,
                    "suppliers": suppliers,
                    "categories": categories,
                    "noise_words": data.get("noise_reduction", {}).get("negative_keywords", []),
                    "stats": {
                        "p0_topics_count": len(topics.get("p0_core", [])),
                        "p1_topics_count": len(topics.get("p1_strongly_related", [])),
                        "p2_topics_count": len(topics.get("p2_methods_tools", [])),
                        "p3_topics_count": len(topics.get("p3_general_control", [])),
                        "p0_suppliers_count": len(suppliers.get("p0_tier1_core", [])),
                        "p1_suppliers_count": len(suppliers.get("p1_tier1_oem_advanced", [])),
                        "p2_suppliers_count": len(suppliers.get("p2_tier2_specialized", [])),
                        "p3_suppliers_count": len(suppliers.get("p3_oem_brands", [])),
                    }
                }
                self.send_json({"code": 0, "data": summary})
            except Exception as e:
                self.send_json({"code": 500, "message": f"Failed to load whitelist: {e}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if path == "/api/health":
            self.send_json({"code": 0, "status": "ok", "app": "Horizon_iCarInfo Dashboard"})
            return

        self.send_json({"code": 404, "message": "API endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def serve_file(self, file_path: Path, content_type: str) -> None:
        """Helper to serve raw files with specified content type."""
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        try:
            content = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

    def send_json(self, data: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        """Send JSON response with appropriate headers and UTF-8 encoding."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Clean log output to avoid terminal flooding."""
        # Only log non-200 or custom status to keep terminal clean
        if args and str(args[1]) != "200":
            sys.stderr.write(f"[Horizon Dashboard] {self.address_string()} - {format % args}\n")


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start the Dashboard HTTP Server."""
    server_address = (host, port)
    try:
        httpd = ThreadingHTTPServer(server_address, DashboardRequestHandler)
    except OSError as e:
        if "Address already in use" in str(e):
            # Try next port
            port += 1
            server_address = (host, port)
            httpd = ThreadingHTTPServer(server_address, DashboardRequestHandler)
        else:
            raise

    print("\n" + "=" * 60)
    print("🌅 Horizon_iCarInfo · 智能汽车底盘前瞻情报指挥舱")
    print("=" * 60)
    print(f"🚀 Web UI 服务已就绪: http://{host}:{port}")
    print(f"📁 情报归档目录: {SUMMARIES_DIR}")
    print(f"⚙️ 知识白名单: {WHITELIST_FILE}")
    print("💡 按 Ctrl+C 可停止看板服务 (完全不影响原有终端命令)")
    print("=" * 60 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Horizon Dashboard] 看板服务已平稳关闭。")
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Horizon_iCarInfo Pluggable Web UI Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
