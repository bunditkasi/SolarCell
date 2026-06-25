from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from solar_dashboard import build_live_report_payload, refresh_cache, report_to_csv


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        kind = parse_qs(urlparse(self.path).query).get("kind", ["summary"])[0]
        try:
            body = report_to_csv(build_live_report_payload(refresh_cache())["report"], kind)
        except ValueError as exc:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=solar-report-{kind}.csv")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
