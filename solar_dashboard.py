import csv
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from solar_fetch import COMMON_FIELDS, fetch_all


STATIC_DIR = Path(__file__).parent / "static"


def _num(value):
    return value if isinstance(value, (int, float)) else 0


def _status_bucket(status):
    text = str(status or "").lower()
    if "fault" in text or "alarm" in text or text in {"2"}:
        return "faulty"
    if "offline" in text or "disconnect" in text or text in {"0"}:
        return "offline"
    if "normal" in text or "health_state_3" in text or text in {"1"}:
        return "normal"
    return "unknown"


def summarize_sites(sites):
    status_counts = {"normal": 0, "faulty": 0, "offline": 0, "unknown": 0}
    source_health = {}
    for site in sites:
        status_counts[_status_bucket(site.get("status"))] += 1
        source = site.get("source") or "unknown"
        current = source_health.get(source)
        next_status = site.get("collector_status") or "ok"
        if current == "failed" or next_status == "failed":
            source_health[source] = "failed"
        elif current == "degraded" or next_status == "degraded":
            source_health[source] = "degraded"
        else:
            source_health[source] = "ok"
    return {
        "site_count": len(sites),
        "current_power_kw": round(sum(_num(site.get("current_power_kw")) for site in sites), 3),
        "today_energy_kwh": round(sum(_num(site.get("today_energy_kwh")) for site in sites), 3),
        "total_capacity_kw": round(sum(_num(site.get("capacity_kw")) for site in sites), 3),
        "lifetime_energy_kwh": round(sum(_num(site.get("lifetime_energy_kwh")) for site in sites), 3),
        "status_counts": status_counts,
        "source_health": source_health,
    }


def filter_sites(sites, source="all", status="all", query="", country=""):
    query = (query or "").strip().lower()
    country = (country or "").strip().lower()
    filtered = []
    for site in sites:
        if source != "all" and site.get("source") != source:
            continue
        if status != "all" and _status_bucket(site.get("status")) != status:
            continue
        if country and country not in str(site.get("country") or "").lower():
            continue
        haystack = " ".join(str(site.get(key) or "") for key in ("site_name", "site_id")).lower()
        if query and query not in haystack:
            continue
        filtered.append(site)
    return filtered


def sites_to_csv(sites):
    fields = list(COMMON_FIELDS)
    for extra in ("last_sync", "collector_status"):
        if extra not in fields:
            fields.append(extra)
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for site in sites:
        writer.writerow({field: site.get(field) for field in fields})
    return handle.getvalue()


DASHBOARD_CACHE = {"sites": [], "summary": summarize_sites([]), "errors": []}


def current_cache():
    return DASHBOARD_CACHE


def refresh_cache(fetcher=fetch_all):
    global DASHBOARD_CACHE
    try:
        sites = fetcher()
        DASHBOARD_CACHE = {"sites": sites, "summary": summarize_sites(sites), "errors": []}
    except Exception as exc:
        DASHBOARD_CACHE = {"sites": [], "summary": summarize_sites([]), "errors": [str(exc)]}
    return DASHBOARD_CACHE


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/sites":
            return self._json(current_cache())
        if parsed.path == "/api/export.csv":
            return self._send(200, sites_to_csv(current_cache()["sites"]), "text/csv; charset=utf-8")
        if parsed.path in {"/", "/index.html"}:
            return self._static("index.html", "text/html; charset=utf-8")
        if parsed.path.startswith("/static/"):
            filename = parsed.path.replace("/static/", "", 1)
            content_type = "text/css; charset=utf-8" if filename.endswith(".css") else "application/javascript; charset=utf-8"
            return self._static(filename, content_type)
        self._send(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if urlparse(self.path).path != "/api/refresh":
            return self._send(404, "Not found", "text/plain; charset=utf-8")
        self._json(refresh_cache())

    def _static(self, filename, content_type):
        path = STATIC_DIR / filename
        if not path.exists():
            return self._send(404, "Not found", "text/plain; charset=utf-8")
        self._send(200, path.read_text(encoding="utf-8"), content_type)

    def _json(self, data):
        self._send(200, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")

    def _send(self, status, body, content_type):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(host="127.0.0.1", port=8000):
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Solar Operations dashboard running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
