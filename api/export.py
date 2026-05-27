from http.server import BaseHTTPRequestHandler

from solar_dashboard import refresh_cache, sites_to_csv


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cache = refresh_cache()
        body = sites_to_csv(cache["sites"])
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=solar-sites.csv")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
