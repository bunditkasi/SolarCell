from http.server import BaseHTTPRequestHandler

from solar_dashboard import build_live_report_payload, refresh_cache, report_to_html


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = report_to_html(build_live_report_payload(refresh_cache()))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
