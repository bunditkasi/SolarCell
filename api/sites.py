import json
from http.server import BaseHTTPRequestHandler

from solar_dashboard import cache_needs_refresh, current_cache, refresh_cache


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cache = current_cache()
        if cache_needs_refresh(cache):
            cache = refresh_cache()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(cache, ensure_ascii=False).encode("utf-8"))
