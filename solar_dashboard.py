import csv
import io
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from solar_fetch import COMMON_FIELDS, fetch_all


STATIC_DIR = Path(__file__).parent / "static"


def _num(value):
    return value if isinstance(value, (int, float)) else 0


def _status_bucket(status):
    text = str(status or "").lower()
    if text == "health_state_3":
        return "normal"
    if text == "health_state_1":
        return "offline"
    if text == "health_state_2":
        return "faulty"
    if "fault" in text or "alarm" in text or text in {"2"}:
        return "faulty"
    if "offline" in text or "disconnect" in text or text in {"0"}:
        return "offline"
    if "normal" in text or text in {"1"}:
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


def build_report(sites):
    source_rows = []
    health_rows = []
    for source in sorted({site.get("source") or "unknown" for site in sites}):
        rows = [site for site in sites if (site.get("source") or "unknown") == source]
        status_counts = {"normal": 0, "faulty": 0, "offline": 0, "unknown": 0}
        collector_status = "ok"
        for site in rows:
            status_counts[_status_bucket(site.get("status"))] += 1
            next_status = site.get("collector_status") or "ok"
            if next_status == "failed":
                collector_status = "failed"
            elif next_status == "degraded" and collector_status != "failed":
                collector_status = "degraded"
        source_rows.append(
            {
                "source": source,
                "site_count": len(rows),
                "capacity_kw": round(sum(_num(site.get("capacity_kw")) for site in rows), 3),
                "current_power_kw": round(sum(_num(site.get("current_power_kw")) for site in rows), 3),
                "today_energy_kwh": round(sum(_num(site.get("today_energy_kwh")) for site in rows), 3),
                "month_energy_kwh": round(sum(_num(site.get("month_energy_kwh")) for site in rows), 3),
                "lifetime_energy_kwh": round(sum(_num(site.get("lifetime_energy_kwh")) for site in rows), 3),
                "normal_count": status_counts["normal"],
                "faulty_count": status_counts["faulty"],
                "offline_count": status_counts["offline"],
                "unknown_count": status_counts["unknown"],
            }
        )
        health_rows.append(
            {
                "source": source,
                "collector_status": collector_status,
                "normal_count": status_counts["normal"],
                "offline_count": status_counts["offline"],
                "faulty_count": status_counts["faulty"],
                "unknown_count": status_counts["unknown"],
            }
        )
    exception_rows = [
        site
        for site in sites
        if _status_bucket(site.get("status")) in {"faulty", "offline", "unknown"}
    ]
    performance_rows = []
    for site in sites:
        capacity = _num(site.get("capacity_kw"))
        today_energy = _num(site.get("today_energy_kwh"))
        current_power = _num(site.get("current_power_kw"))
        performance_rows.append(
            {
                "source": site.get("source") or "unknown",
                "site_id": site.get("site_id") or "",
                "site_name": site.get("site_name") or "",
                "status": site.get("status") or "",
                "capacity_kw": site.get("capacity_kw"),
                "current_power_kw": site.get("current_power_kw"),
                "today_energy_kwh": site.get("today_energy_kwh"),
                "yield_per_kwp": round(today_energy / capacity, 3) if capacity else None,
                "current_load_percent": round((current_power / capacity) * 100, 2) if capacity else None,
            }
        )
    performance_rows.sort(
        key=lambda row: (
            row["yield_per_kwp"] is not None,
            row["yield_per_kwp"] or 0,
            row["today_energy_kwh"] or 0,
        ),
        reverse=True,
    )
    return {
        "source_rows": source_rows,
        "exception_rows": exception_rows,
        "performance_rows": performance_rows,
        "health_rows": health_rows,
    }


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


def _now_utc():
    return datetime.now(timezone.utc)


def _empty_cache():
    return {
        "sites": [],
        "summary": summarize_sites([]),
        "errors": [],
        "last_refresh_at": None,
        "next_refresh_at": None,
        "refresh_schedule": [],
    }


DASHBOARD_CACHE = _empty_cache()


def current_cache():
    return DASHBOARD_CACHE


def refresh_cache(fetcher=fetch_all, now_provider=_now_utc):
    global DASHBOARD_CACHE
    now = now_provider()
    try:
        sites = fetcher()
        DASHBOARD_CACHE = {
            "sites": sites,
            "summary": summarize_sites(sites),
            "errors": [],
            "last_refresh_at": now.isoformat(),
            "next_refresh_at": None,
            "refresh_schedule": [],
        }
    except Exception as exc:
        DASHBOARD_CACHE = {
            **DASHBOARD_CACHE,
            "errors": [str(exc)],
            "next_refresh_at": None,
            "refresh_schedule": [],
        }
    return DASHBOARD_CACHE


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/sites":
            return self._json(refresh_cache())
        if parsed.path == "/api/export.csv":
            return self._send(200, sites_to_csv(refresh_cache()["sites"]), "text/csv; charset=utf-8")
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
