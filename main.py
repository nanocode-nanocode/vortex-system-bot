#!/usr/bin/env python3
"""VØRTΞX System Bot — Health endpoint for cloud platforms."""
import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        data = json.dumps({"status": "ok", "service": "vortex-system-bot"}).encode()
        self.wfile.write(data)
    def log_message(self, *a):
        pass

port = int(os.environ.get("PORT", 8080))
print(f"🌐 Health endpoint on :{port}")
HTTPServer(("", port), HealthHandler).serve_forever()
