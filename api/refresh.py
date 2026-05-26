import json
from http.server import BaseHTTPRequestHandler

from solar_dashboard import refresh_cache


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._refresh()

    def do_POST(self):
        self._refresh()

    def _refresh(self):
        cache = refresh_cache()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(cache, ensure_ascii=False).encode("utf-8"))
