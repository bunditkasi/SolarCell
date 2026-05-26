# Solar Operations Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a local webapp MVP that combines Huawei and Atmoce solar data into a Huawei-inspired but distinct `Solar Operations` dashboard with filtering, refresh, source health, and CSV export.

**Architecture:** Use Python stdlib for the backend so the app can run on this Windows workspace without dependency setup. Split collector normalization from dashboard aggregation, expose JSON/CSV endpoints through a small HTTP server, and build a static HTML/CSS/JS frontend that consumes those endpoints.

**Tech Stack:** Python 3 stdlib (`http.server`, `urllib`, `unittest`), vanilla HTML/CSS/JavaScript, existing `solar_fetch.py` connector logic.

---

## File Structure

- `solar_fetch.py`: Keep as the collector/client module for Huawei and Atmoce; add `last_sync` and `collector_status` fields to normalized records.
- `solar_dashboard.py`: Create a focused backend module with summary calculation, filtering helpers, CSV serialization, and an HTTP server.
- `static/index.html`: Create the dashboard shell, top nav, KPI band, source health section, filters, and table.
- `static/styles.css`: Create the distinct MR.DIY internal operations visual system inspired by Huawei layout without copying proprietary colors/assets.
- `static/app.js`: Create frontend state, fetch/refresh behavior, filter behavior, table rendering, and CSV export trigger.
- `tests/test_solar_fetch.py`: Extend existing connector tests for `last_sync` and `collector_status`.
- `tests/test_solar_dashboard.py`: Create backend tests for summary calculations, filtering, and CSV output.
- `README.md`: Update run instructions for the local dashboard.
- `.gitignore`: Ensure secrets, runtime output, and caches are excluded.

## Task 1: Normalize Collector Metadata

**Files:**
- Modify: `solar_fetch.py`
- Modify: `tests/test_solar_fetch.py`

- [x] **Step 1: Add failing tests for `last_sync` and `collector_status`**

Add these assertions to the existing Atmoce normalization test in `tests/test_solar_fetch.py`:

```python
self.assertRegex(normalized["last_sync"], r"^\d{4}-\d{2}-\d{2}T")
self.assertEqual(normalized["collector_status"], "ok")
```

Add these assertions to the existing Huawei normalization test:

```python
self.assertRegex(normalized["last_sync"], r"^\d{4}-\d{2}-\d{2}T")
self.assertEqual(normalized["collector_status"], "ok")
```

- [x] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_solar_fetch
```

Expected: FAIL with `KeyError: 'last_sync'` or `KeyError: 'collector_status'`.

- [x] **Step 3: Implement metadata in `solar_fetch.py`**

Add this helper near `_round_or_none`:

```python
def _utc_now_iso():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
```

Add these keys to both `normalize_atmoce_station()` and `normalize_huawei_station()` return dictionaries:

```python
"last_sync": _utc_now_iso(),
"collector_status": "ok",
```

When Huawei KPI is rate-limited in `HuaweiClient.fetch_stations()`, pass degraded status into normalization by changing the final return to:

```python
status = "degraded" if not kpi_by_code and codes else "ok"
return [
    normalize_huawei_station(
        station,
        kpi_by_code.get(station.get("stationCode")),
        collector_status=status,
    )
    for station in stations
]
```

Update the Huawei normalizer signature:

```python
def normalize_huawei_station(station, kpi=None, collector_status="ok"):
```

Use `collector_status` in the returned dictionary.

- [x] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m unittest tests.test_solar_fetch
```

Expected: all tests pass.

- [x] **Step 5: Commit**

Run:

```powershell
git add solar_fetch.py tests/test_solar_fetch.py
git commit -m "feat: add collector metadata to solar records"
```

## Task 2: Add Dashboard Aggregation Module

**Files:**
- Create: `solar_dashboard.py`
- Create: `tests/test_solar_dashboard.py`

- [x] **Step 1: Write failing tests for summaries and filters**

Create `tests/test_solar_dashboard.py`:

```python
import csv
import io
import unittest

from solar_dashboard import filter_sites, summarize_sites, sites_to_csv


SITES = [
    {
        "source": "atmoce",
        "site_id": "A1",
        "site_name": "PKON",
        "status": "Normal",
        "country": "Thailand",
        "capacity_kw": 42.9,
        "current_power_kw": 30.0,
        "today_energy_kwh": 166.6,
        "month_energy_kwh": None,
        "lifetime_energy_kwh": 644.2,
        "collector_status": "ok",
    },
    {
        "source": "huawei",
        "site_id": "H1",
        "site_name": "PCKN Mr. DIY",
        "status": "health_state_3",
        "country": "Thailand",
        "capacity_kw": 30.5,
        "current_power_kw": 20.0,
        "today_energy_kwh": 92.4,
        "month_energy_kwh": 395.1,
        "lifetime_energy_kwh": 39246.6,
        "collector_status": "degraded",
    },
]


class DashboardAggregationTest(unittest.TestCase):
    def test_summarize_sites_totals_and_source_health(self):
        summary = summarize_sites(SITES)

        self.assertEqual(summary["site_count"], 2)
        self.assertEqual(summary["status_counts"]["normal"], 2)
        self.assertEqual(summary["status_counts"]["faulty"], 0)
        self.assertEqual(summary["status_counts"]["offline"], 0)
        self.assertEqual(summary["total_capacity_kw"], 73.4)
        self.assertEqual(summary["current_power_kw"], 50.0)
        self.assertEqual(summary["today_energy_kwh"], 259.0)
        self.assertEqual(summary["source_health"]["atmoce"], "ok")
        self.assertEqual(summary["source_health"]["huawei"], "degraded")

    def test_filter_sites_by_source_status_and_search(self):
        result = filter_sites(SITES, source="huawei", status="normal", query="pckn")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["site_id"], "H1")

    def test_sites_to_csv_contains_common_columns(self):
        text = sites_to_csv(SITES)
        rows = list(csv.DictReader(io.StringIO(text)))

        self.assertEqual(rows[0]["source"], "atmoce")
        self.assertEqual(rows[1]["site_name"], "PCKN Mr. DIY")


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_solar_dashboard
```

Expected: FAIL with `ModuleNotFoundError: No module named 'solar_dashboard'`.

- [x] **Step 3: Implement `solar_dashboard.py`**

Create `solar_dashboard.py`:

```python
import csv
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


class DashboardHandler(BaseHTTPRequestHandler):
    cache = {"sites": [], "summary": summarize_sites([]), "errors": []}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/sites":
            return self._json(self.cache)
        if parsed.path == "/api/export.csv":
            return self._send(200, sites_to_csv(self.cache["sites"]), "text/csv; charset=utf-8")
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
        try:
            sites = fetch_all()
            self.cache = {"sites": sites, "summary": summarize_sites(sites), "errors": []}
        except Exception as exc:
            self.cache = {"sites": [], "summary": summarize_sites([]), "errors": [str(exc)]}
        self._json(self.cache)

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
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m unittest tests.test_solar_dashboard
```

Expected: all tests pass.

- [x] **Step 5: Commit**

Run:

```powershell
git add solar_dashboard.py tests/test_solar_dashboard.py
git commit -m "feat: add dashboard aggregation backend"
```

## Task 3: Create Static Dashboard UI

**Files:**
- Create: `static/index.html`
- Create: `static/styles.css`
- Create: `static/app.js`

- [x] **Step 1: Create `static/index.html`**

Create:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Solar Operations</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">SO</span>
        <div>
          <strong>Solar Operations</strong>
          <span>MR.DIY energy monitoring</span>
        </div>
      </div>
      <nav class="nav">
        <a class="active">Dashboard</a>
        <a>Sites</a>
        <a>Reports</a>
        <a>Alerts</a>
        <a>Settings</a>
      </nav>
    </header>

    <main class="page">
      <section class="title-row">
        <div>
          <h1>Solar Operations</h1>
          <p>Unified Huawei and Atmoce site monitoring.</p>
        </div>
        <div class="actions">
          <button id="refreshButton" type="button">Refresh</button>
          <a class="button secondary" href="/api/export.csv">Export CSV</a>
        </div>
      </section>

      <section class="kpis" id="kpis"></section>

      <section class="health" id="sourceHealth"></section>

      <section class="toolbar">
        <input id="queryInput" type="search" placeholder="Site name or ID" />
        <select id="sourceFilter">
          <option value="all">All sources</option>
          <option value="huawei">Huawei</option>
          <option value="atmoce">Atmoce</option>
        </select>
        <select id="statusFilter">
          <option value="all">All status</option>
          <option value="normal">Normal</option>
          <option value="faulty">Faulty</option>
          <option value="offline">Offline</option>
          <option value="unknown">Unknown</option>
        </select>
        <input id="countryFilter" type="search" placeholder="Country/Region" />
      </section>

      <section class="table-shell">
        <div class="table-header">
          <h2>Sites</h2>
          <span id="rowCount">0 sites</span>
        </div>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Site Name</th>
                <th>Install/Grid Date</th>
                <th>Capacity kWp</th>
                <th>Battery kWh</th>
                <th>Current kW</th>
                <th>Today kWh</th>
                <th>Month kWh</th>
                <th>Lifetime kWh</th>
                <th>Last Sync</th>
              </tr>
            </thead>
            <tbody id="siteRows"></tbody>
          </table>
        </div>
      </section>

      <section class="empty" id="emptyState" hidden>No site data loaded. Press Refresh to fetch the latest data.</section>
      <section class="errors" id="errors" hidden></section>
    </main>

    <script src="/static/app.js"></script>
  </body>
</html>
```

- [x] **Step 2: Create `static/styles.css`**

Create:

```css
:root {
  --bg: #f5f7fa;
  --panel: #ffffff;
  --line: #dfe5ec;
  --text: #1f2933;
  --muted: #667482;
  --accent: #0f766e;
  --accent-2: #2563eb;
  --ok: #16803c;
  --warn: #b7791f;
  --bad: #c2410c;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Arial, "Segoe UI", sans-serif;
  color: var(--text);
  background: var(--bg);
}

.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #111827;
  color: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  border-radius: 6px;
  font-weight: 700;
}

.brand span:last-child {
  display: block;
  color: #b9c2cf;
  font-size: 12px;
  margin-top: 2px;
}

.nav {
  display: flex;
  gap: 6px;
}

.nav a {
  color: #cbd5e1;
  padding: 10px 12px;
  border-radius: 4px;
  font-size: 14px;
}

.nav .active {
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
}

.page {
  padding: 22px;
}

.title-row,
.table-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 24px;
}

h2 {
  font-size: 16px;
}

p,
.table-header span {
  color: var(--muted);
}

.actions,
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

button,
.button,
input,
select {
  height: 36px;
  border-radius: 4px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--text);
  padding: 0 12px;
  font-size: 14px;
}

button,
.button {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.secondary {
  background: #fff;
  color: var(--accent);
}

.kpis,
.health {
  display: grid;
  grid-template-columns: repeat(6, minmax(140px, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 14px;
}

.card label {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.card strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
}

.health {
  grid-template-columns: repeat(3, minmax(180px, 1fr));
}

.toolbar,
.table-shell,
.empty,
.errors {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  margin-top: 16px;
  padding: 14px;
}

.toolbar input {
  min-width: 220px;
}

.table-scroll {
  overflow-x: auto;
  margin-top: 12px;
}

table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  border-bottom: 1px solid var(--line);
  text-align: left;
  padding: 10px 8px;
  white-space: nowrap;
}

th {
  color: var(--muted);
  background: #f8fafc;
  font-weight: 600;
}

.badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef2f7;
  font-size: 12px;
  font-weight: 600;
}

.ok {
  color: var(--ok);
}

.degraded,
.unknown {
  color: var(--warn);
}

.failed,
.faulty,
.offline {
  color: var(--bad);
}

@media (max-width: 900px) {
  .topbar,
  .title-row {
    align-items: flex-start;
    flex-direction: column;
    height: auto;
    padding: 16px;
  }

  .kpis,
  .health {
    grid-template-columns: repeat(2, minmax(140px, 1fr));
  }
}
```

- [x] **Step 3: Create `static/app.js`**

Create:

```javascript
const state = {
  sites: [],
  summary: null,
  errors: [],
};

const elements = {
  kpis: document.querySelector("#kpis"),
  sourceHealth: document.querySelector("#sourceHealth"),
  rows: document.querySelector("#siteRows"),
  rowCount: document.querySelector("#rowCount"),
  empty: document.querySelector("#emptyState"),
  errors: document.querySelector("#errors"),
  refresh: document.querySelector("#refreshButton"),
  query: document.querySelector("#queryInput"),
  source: document.querySelector("#sourceFilter"),
  status: document.querySelector("#statusFilter"),
  country: document.querySelector("#countryFilter"),
};

function number(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function statusBucket(status) {
  const text = String(status || "").toLowerCase();
  if (text.includes("fault") || text.includes("alarm") || text === "2") return "faulty";
  if (text.includes("offline") || text.includes("disconnect") || text === "0") return "offline";
  if (text.includes("normal") || text.includes("health_state_3") || text === "1") return "normal";
  return "unknown";
}

function filteredSites() {
  const query = elements.query.value.trim().toLowerCase();
  const country = elements.country.value.trim().toLowerCase();
  return state.sites.filter((site) => {
    if (elements.source.value !== "all" && site.source !== elements.source.value) return false;
    if (elements.status.value !== "all" && statusBucket(site.status) !== elements.status.value) return false;
    if (country && !String(site.country || "").toLowerCase().includes(country)) return false;
    const haystack = `${site.site_name || ""} ${site.site_id || ""}`.toLowerCase();
    return !query || haystack.includes(query);
  });
}

function renderKpis(summary) {
  const items = [
    ["Current Power", `${number(summary.current_power_kw)} kW`],
    ["Yield Today", `${number(summary.today_energy_kwh)} kWh`],
    ["Total Yield", `${number(summary.lifetime_energy_kwh)} kWh`],
    ["Total Capacity", `${number(summary.total_capacity_kw)} kWp`],
    ["Normal Sites", number(summary.status_counts.normal, 0)],
    ["Offline/Faulty", number(summary.status_counts.offline + summary.status_counts.faulty, 0)],
  ];
  elements.kpis.innerHTML = items.map(([label, value]) => `<article class="card"><label>${label}</label><strong>${value}</strong></article>`).join("");
}

function renderHealth(summary) {
  const sources = ["huawei", "atmoce", "huawei_web"];
  elements.sourceHealth.innerHTML = sources
    .map((source) => {
      const status = summary.source_health[source] || "unknown";
      return `<article class="card"><label>${source.replace("_", " ").toUpperCase()}</label><strong class="${status}">${status}</strong></article>`;
    })
    .join("");
}

function renderTable() {
  const rows = filteredSites();
  elements.rowCount.textContent = `${rows.length} sites`;
  elements.empty.hidden = rows.length > 0;
  elements.rows.innerHTML = rows
    .map((site) => {
      const bucket = statusBucket(site.status);
      return `<tr>
        <td><span class="badge">${site.source || "--"}</span></td>
        <td class="${bucket}">${site.status || bucket}</td>
        <td>${site.site_name || "--"}</td>
        <td>${site.installed_date || "--"}</td>
        <td>${number(site.capacity_kw)}</td>
        <td>${number(site.battery_capacity_kwh)}</td>
        <td>${number(site.current_power_kw)}</td>
        <td>${number(site.today_energy_kwh)}</td>
        <td>${number(site.month_energy_kwh)}</td>
        <td>${number(site.lifetime_energy_kwh)}</td>
        <td>${site.last_sync || "--"}</td>
      </tr>`;
    })
    .join("");
}

function renderErrors(errors) {
  elements.errors.hidden = !errors.length;
  elements.errors.textContent = errors.join("\\n");
}

function render() {
  renderKpis(state.summary);
  renderHealth(state.summary);
  renderTable();
  renderErrors(state.errors);
}

async function loadData(refresh = false) {
  elements.refresh.disabled = true;
  const response = await fetch(refresh ? "/api/refresh" : "/api/sites", { method: refresh ? "POST" : "GET" });
  const data = await response.json();
  state.sites = data.sites || [];
  state.summary = data.summary || {
    current_power_kw: 0,
    today_energy_kwh: 0,
    lifetime_energy_kwh: 0,
    total_capacity_kw: 0,
    status_counts: { normal: 0, offline: 0, faulty: 0 },
    source_health: {},
  };
  state.errors = data.errors || [];
  render();
  elements.refresh.disabled = false;
}

for (const input of [elements.query, elements.source, elements.status, elements.country]) {
  input.addEventListener("input", renderTable);
}
elements.refresh.addEventListener("click", () => loadData(true));

loadData(false);
```

- [x] **Step 4: Commit**

Run:

```powershell
git add static/index.html static/styles.css static/app.js
git commit -m "feat: add solar operations dashboard UI"
```

## Task 4: Wire Backend Server and Documentation

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`

- [x] **Step 1: Update `.gitignore`**

Ensure `.gitignore` contains:

```gitignore
.env
output/
__pycache__/
tests/__pycache__/
```

- [x] **Step 2: Update `README.md`**

Add this section:

```markdown
## Run Dashboard

Set credentials in PowerShell:

```powershell
$env:ATMOCE_USERNAME="your-atmoce-username"
$env:ATMOCE_PASSWORD="your-atmoce-password"
$env:HUAWEI_USERNAME="your-huawei-northbound-username"
$env:HUAWEI_SYSTEM_CODE="your-huawei-northbound-system-code"
```

Start the local dashboard:

```powershell
python solar_dashboard.py
```

Open:

```text
http://127.0.0.1:8000
```

Press `Refresh` to fetch live Huawei and Atmoce data.
```

- [x] **Step 3: Run backend tests**

Run:

```powershell
python -m unittest tests.test_solar_fetch tests.test_solar_dashboard
```

Expected: all tests pass.

- [x] **Step 4: Commit**

Run:

```powershell
git add .gitignore README.md
git commit -m "docs: add dashboard run instructions"
```

## Task 5: Manual Live Verification

**Files:**
- No code changes expected unless verification reveals a bug.

- [x] **Step 1: Start the dashboard server**

Run:

```powershell
$env:ATMOCE_USERNAME="bundit.k@mrdiy.com"
$env:ATMOCE_PASSWORD="<real password>"
$env:HUAWEI_USERNAME="DIY_KORN"
$env:HUAWEI_SYSTEM_CODE="<real system code>"
python solar_dashboard.py
```

Expected: terminal prints `Solar Operations dashboard running at http://127.0.0.1:8000`.

- [x] **Step 2: Open the dashboard in the browser**

Open:

```text
http://127.0.0.1:8000
```

Expected:

- Top nav is visible.
- KPI cards are visible.
- Source health cards are visible.
- Table shell is visible.

- [x] **Step 3: Press Refresh**

Expected:

- The table loads combined Huawei and Atmoce rows.
- Source filter `Atmoce` shows Atmoce rows only.
- Source filter `Huawei` shows Huawei rows only.
- Status filter `Normal` shows normal/healthy rows.
- CSV export downloads or opens `/api/export.csv`.

- [x] **Step 4: Stop the server**

Press `Ctrl+C` in the PowerShell window running the server.

- [x] **Step 5: Commit any verification fixes**

If bugs were fixed during manual verification, run:

```powershell
python -m unittest tests.test_solar_fetch tests.test_solar_dashboard
git add solar_dashboard.py solar_fetch.py static/index.html static/styles.css static/app.js tests README.md .gitignore
git commit -m "fix: polish dashboard verification issues"
```

Expected: commit is only needed if code changed.

## Self-Review

Spec coverage:

- Unified dashboard: Task 3.
- KPI cards: Task 2 summary and Task 3 UI.
- Source health: Task 2 summary and Task 3 UI.
- Filterable table: Task 2 filter helper and Task 3 frontend filters.
- CSV export: Task 2 CSV helper and endpoint.
- Manual refresh: Task 2 server endpoint and Task 3 refresh button.
- Connector normalization: Task 1 and existing `solar_fetch.py`.
- Collector errors per source: Task 2 server cache/error response and Task 3 error display.

Plan completeness scan:

- No unresolved future-work markers or vague implementation instructions are present.
- Real credentials are represented as environment variables or `<real password>` only in manual verification instructions.

Type consistency:

- Normalized field names match the design spec and existing `COMMON_FIELDS`.
- Frontend filter values match backend `_status_bucket()` values: `normal`, `faulty`, `offline`, `unknown`.

