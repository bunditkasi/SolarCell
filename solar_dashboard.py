import csv
import html
import io
import json
from calendar import monthrange
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from solar_fetch import COMMON_FIELDS, fetch_all, fetch_monthly_energy_rows


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
    monthly_rows = []
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
        month_energy = site.get("month_energy_kwh")
        if month_energy not in (None, ""):
            monthly_rows.append(
                {
                    "month": site.get("month") or "current",
                    "source": site.get("source") or "unknown",
                    "site_id": site.get("site_id") or "",
                    "site_name": site.get("site_name") or "",
                    "energy_kwh": month_energy,
                    "capacity_kw": site.get("capacity_kw"),
                    "yield_per_kwp": round(_num(month_energy) / capacity, 3) if capacity else None,
                    "coverage": site.get("monthly_coverage") or "current_month",
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
        "monthly_rows": sorted(
            monthly_rows,
            key=lambda row: (str(row.get("month") or ""), str(row.get("source") or ""), str(row.get("site_name") or "")),
            reverse=True,
        ),
    }


REPORT_CSV_FIELDS = {
    "summary": [
        "source",
        "site_count",
        "capacity_kw",
        "current_power_kw",
        "today_energy_kwh",
        "month_energy_kwh",
        "lifetime_energy_kwh",
        "normal_count",
        "offline_count",
        "faulty_count",
        "unknown_count",
    ],
    "health": [
        "source",
        "collector_status",
        "normal_count",
        "offline_count",
        "faulty_count",
        "unknown_count",
    ],
    "performance": [
        "source",
        "status",
        "site_id",
        "site_name",
        "capacity_kw",
        "current_power_kw",
        "today_energy_kwh",
        "yield_per_kwp",
        "current_load_percent",
    ],
    "exceptions": [
        "source",
        "status",
        "site_id",
        "site_name",
        "capacity_kw",
        "current_power_kw",
        "today_energy_kwh",
        "last_sync",
    ],
    "monthly": [
        "month",
        "source",
        "site_id",
        "site_name",
        "energy_kwh",
        "capacity_kw",
        "yield_per_kwp",
        "coverage",
    ],
}


REPORT_ROW_KEYS = {
    "summary": "source_rows",
    "health": "health_rows",
    "performance": "performance_rows",
    "exceptions": "exception_rows",
    "monthly": "monthly_rows",
}


def build_report_payload(cache, monthly_rows=None):
    report = build_report(cache.get("sites") or [])
    if monthly_rows is not None:
        current_rows = [
            row
            for row in report.get("monthly_rows", [])
            if row.get("source") != "atmoce" or row.get("coverage") != "current_month"
        ]
        report["monthly_rows"] = sorted(
            list(monthly_rows) + current_rows,
            key=lambda row: (
                row.get("month") == "current",
                str(row.get("month") or ""),
                str(row.get("source") or ""),
                str(row.get("site_name") or ""),
            ),
        )
    return {
        "summary": cache.get("summary") or summarize_sites(cache.get("sites") or []),
        "report": report,
        "errors": cache.get("errors") or [],
        "last_refresh_at": cache.get("last_refresh_at"),
    }


def _month_key(value):
    text = str(value or "")
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    return None


def _month_range(start_month, end_month):
    start_year, start_num = (int(part) for part in start_month.split("-"))
    end_year, end_num = (int(part) for part in end_month.split("-"))
    months = []
    year, month = start_year, start_num
    while (year, month) <= (end_year, end_num):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def build_monthly_kwh_table(sites, monthly_rows, today=None):
    today = today or _now_utc()
    current_month = today.strftime("%Y-%m")
    site_map = {}
    values_by_site = {}

    for site in sites or []:
        key = (
            site.get("source") or "unknown",
            site.get("site_id") or "",
            site.get("site_name") or "",
        )
        site_map[key] = {
            "source": key[0],
            "site_id": key[1],
            "site_name": key[2],
            "capacity_kw": site.get("capacity_kw"),
        }

    historical_months = set()
    for row in monthly_rows or []:
        month = _month_key(row.get("month"))
        if not month:
            continue
        key = (
            row.get("source") or "unknown",
            row.get("site_id") or "",
            row.get("site_name") or "",
        )
        site_map.setdefault(
            key,
            {
                "source": key[0],
                "site_id": key[1],
                "site_name": key[2],
                "capacity_kw": row.get("capacity_kw"),
            },
        )
        values_by_site.setdefault(key, {})[month] = row.get("energy_kwh")
        historical_months.add(month)

    start_month = min(historical_months) if historical_months else current_month
    months = _month_range(start_month, current_month)
    last_day = monthrange(today.year, today.month)[1]
    current_status = "On process" if today.day < last_day else "On process"

    rows = []
    def sort_key(item):
        has_value = any(month != current_month and values_by_site.get(item, {}).get(month) not in (None, "") for month in months)
        return (item[0], not has_value, item[2], item[1])

    for key in sorted(site_map, key=sort_key):
        values = {}
        for month in months:
            if month == current_month:
                values[month] = current_status
            else:
                values[month] = values_by_site.get(key, {}).get(month, "N/A")
        rows.append({**site_map[key], "values": values})

    return {
        "months": months,
        "current_month": current_month,
        "rows": rows,
    }


def build_live_monthly_kwh_payload(cache):
    monthly_rows = fetch_monthly_energy_rows()
    return {
        "summary": cache.get("summary") or summarize_sites(cache.get("sites") or []),
        "monthly_kwh": build_monthly_kwh_table(cache.get("sites") or [], monthly_rows, today=_now_utc()),
        "errors": cache.get("errors") or [],
        "last_refresh_at": cache.get("last_refresh_at"),
    }


def build_live_report_payload(cache):
    monthly_rows = fetch_monthly_energy_rows()
    return build_report_payload(cache, monthly_rows=monthly_rows if monthly_rows else None)


def report_to_csv(report, kind):
    if kind not in REPORT_ROW_KEYS:
        raise ValueError(f"Unknown report kind: {kind}")
    fields = REPORT_CSV_FIELDS[kind]
    rows = report.get(REPORT_ROW_KEYS[kind]) or []
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return handle.getvalue()


def _html_rows(rows, fields):
    output = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(field) if row.get(field) is not None else ''))}</td>"
            for field in fields
        )
        output.append(f"<tr>{cells}</tr>")
    if not output:
        output.append(f"<tr><td colspan=\"{len(fields)}\">No records</td></tr>")
    return "".join(output)


def _report_table(rows, fields, headings=None):
    headings = headings or fields
    header = "".join(f"<th>{html.escape(str(label))}</th>" for label in headings)
    return f"<table><thead><tr>{header}</tr></thead><tbody>{_html_rows(rows, fields)}</tbody></table>"


def report_to_html(payload):
    summary = payload.get("summary") or {}
    report = payload.get("report") or {}
    generated_at = payload.get("last_refresh_at") or ""
    source_fields = REPORT_CSV_FIELDS["summary"]
    health_fields = REPORT_CSV_FIELDS["health"]
    performance_fields = REPORT_CSV_FIELDS["performance"]
    monthly_fields = REPORT_CSV_FIELDS["monthly"]
    exception_fields = REPORT_CSV_FIELDS["exceptions"]
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Solar Operations Report</title>
    <style>
      body {{ font-family: Arial, sans-serif; color: #1f2933; margin: 24px; }}
      header {{ border-bottom: 2px solid #111827; margin-bottom: 18px; padding-bottom: 12px; }}
      h1 {{ font-size: 24px; margin: 0 0 6px; }}
      h2 {{ font-size: 16px; margin: 22px 0 8px; }}
      .meta, .kpi label {{ color: #667482; font-size: 12px; }}
      .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0; }}
      .kpi {{ border: 1px solid #dfe5ec; padding: 10px; }}
      .kpi strong {{ display: block; font-size: 18px; margin-top: 4px; }}
      table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 14px; }}
      th, td {{ border: 1px solid #dfe5ec; padding: 6px; text-align: left; vertical-align: top; }}
      th {{ background: #f8fafc; }}
      @media print {{ body {{ margin: 12mm; }} .page-break {{ break-before: page; }} }}
    </style>
  </head>
  <body>
    <header>
      <h1>Solar Operations Report</h1>
      <div class="meta">Generated from dashboard data: {html.escape(str(generated_at))}</div>
    </header>
    <section class="kpis">
      <div class="kpi"><label>Total Sites</label><strong>{summary.get('site_count', 0)}</strong></div>
      <div class="kpi"><label>Current Power kW</label><strong>{summary.get('current_power_kw', 0)}</strong></div>
      <div class="kpi"><label>Today kWh</label><strong>{summary.get('today_energy_kwh', 0)}</strong></div>
      <div class="kpi"><label>Total Capacity kWp</label><strong>{summary.get('total_capacity_kw', 0)}</strong></div>
    </section>
    <h2>Source Summary</h2>
    {_report_table(report.get('source_rows') or [], source_fields)}
    <h2>Source Health</h2>
    {_report_table(report.get('health_rows') or [], health_fields)}
    <h2 class="page-break">Site Performance</h2>
    {_report_table((report.get('performance_rows') or [])[:100], performance_fields)}
    <h2 class="page-break">Monthly kWh</h2>
    {_report_table((report.get('monthly_rows') or [])[:200], monthly_fields)}
    <h2 class="page-break">Exception Report</h2>
    {_report_table(report.get('exception_rows') or [], exception_fields)}
  </body>
</html>"""


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
        if parsed.path == "/api/reports":
            return self._json(build_live_report_payload(refresh_cache()))
        if parsed.path == "/api/monthly-kwh":
            return self._json(build_live_monthly_kwh_payload(refresh_cache()))
        if parsed.path == "/api/report.html":
            return self._send(200, report_to_html(build_live_report_payload(refresh_cache())), "text/html; charset=utf-8")
        if parsed.path == "/api/report.csv":
            kind = parse_qs(parsed.query).get("kind", ["summary"])[0]
            try:
                body = report_to_csv(build_live_report_payload(refresh_cache())["report"], kind)
            except ValueError as exc:
                return self._send(400, str(exc), "text/plain; charset=utf-8")
            return self._send(200, body, "text/csv; charset=utf-8")
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
