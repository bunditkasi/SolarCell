import json
from http.server import BaseHTTPRequestHandler

from solar_dashboard import build_live_report_payload, refresh_cache


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = build_live_report_payload(refresh_cache())
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
