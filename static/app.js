const state = {
  sites: [],
  summary: null,
  errors: [],
  lastRefreshAt: null,
  nextRefreshAt: null,
  refreshSchedule: [],
  backendReport: null,
  monthlyKwh: null,
  monthlyKwhLoaded: false,
  monthlyKwhLoading: false,
  view: "dashboard",
};

const elements = {
  kpis: document.querySelector("#kpis"),
  sourceHealth: document.querySelector("#sourceHealth"),
  rows: document.querySelector("#siteRows"),
  rowCount: document.querySelector("#rowCount"),
  empty: document.querySelector("#emptyState"),
  errors: document.querySelector("#errors"),
  refresh: document.querySelector("#refreshButton"),
  cacheMeta: document.querySelector("#cacheMeta"),
  viewSections: document.querySelectorAll("[data-view]"),
  viewLinks: document.querySelectorAll("[data-view-link]"),
  reportKpis: document.querySelector("#reportKpis"),
  reportSummaryRows: document.querySelector("#reportSummaryRows"),
  reportSummaryCount: document.querySelector("#reportSummaryCount"),
  reportHealthRows: document.querySelector("#reportHealthRows"),
  reportHealthCount: document.querySelector("#reportHealthCount"),
  performanceRows: document.querySelector("#performanceRows"),
  performanceCount: document.querySelector("#performanceCount"),
  monthlyRows: document.querySelector("#monthlyRows"),
  monthlyCount: document.querySelector("#monthlyCount"),
  monthlyKwhHead: document.querySelector("#monthlyKwhHead"),
  monthlyKwhRows: document.querySelector("#monthlyKwhRows"),
  monthlyKwhCount: document.querySelector("#monthlyKwhCount"),
  monthlyKwhStatus: document.querySelector("#monthlyKwhStatus"),
  refreshMonthlyKwh: document.querySelector("#refreshMonthlyKwhButton"),
  exceptionRows: document.querySelector("#exceptionRows"),
  exceptionCount: document.querySelector("#exceptionCount"),
  exportSummary: document.querySelector("#exportSummaryButton"),
  exportPerformance: document.querySelector("#exportPerformanceButton"),
  loadMonthlyHistory: document.querySelector("#loadMonthlyHistoryButton"),
  exportMonthly: document.querySelector("#exportMonthlyButton"),
  exportExceptions: document.querySelector("#exportExceptionsButton"),
  query: document.querySelector("#queryInput"),
  source: document.querySelector("#sourceFilter"),
  status: document.querySelector("#statusFilter"),
  country: document.querySelector("#countryFilter"),
};

function number(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "--";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatDateTime(value) {
  if (!value) return "Not yet refreshed";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function statusBucket(status) {
  const text = String(status || "").toLowerCase();
  if (text === "health_state_3") return "normal";
  if (text === "health_state_1") return "offline";
  if (text === "health_state_2") return "faulty";
  if (text.includes("fault") || text.includes("alarm") || text === "2") return "faulty";
  if (text.includes("offline") || text.includes("disconnect") || text === "0") return "offline";
  if (text.includes("normal") || text === "1") return "normal";
  return "unknown";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[char]);
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
  const sources = [
    ["huawei", "HUAWEI"],
    ["atmoce", "ATMOCE"],
    ["huawei01", "Huawei01"],
  ];
  elements.sourceHealth.innerHTML = sources
    .map(([source, label]) => {
      const status = summary.source_health[source] || "unknown";
      return `<article class="card"><label>${label}</label><strong class="${status}">${status}</strong></article>`;
    })
    .join("");
}

function buildReport() {
  const sourceRows = [...new Set(state.sites.map((site) => site.source || "unknown"))]
    .sort()
    .map((source) => {
      const sites = state.sites.filter((site) => (site.source || "unknown") === source);
      const counts = { normal: 0, faulty: 0, offline: 0, unknown: 0 };
      let collectorStatus = "ok";
      for (const site of sites) counts[statusBucket(site.status)] += 1;
      for (const site of sites) {
        const nextStatus = site.collector_status || "ok";
        if (nextStatus === "failed") collectorStatus = "failed";
        else if (nextStatus === "degraded" && collectorStatus !== "failed") collectorStatus = "degraded";
      }
      return {
        source,
        site_count: sites.length,
        capacity_kw: sites.reduce((sum, site) => sum + (Number(site.capacity_kw) || 0), 0),
        current_power_kw: sites.reduce((sum, site) => sum + (Number(site.current_power_kw) || 0), 0),
        today_energy_kwh: sites.reduce((sum, site) => sum + (Number(site.today_energy_kwh) || 0), 0),
        month_energy_kwh: sites.reduce((sum, site) => sum + (Number(site.month_energy_kwh) || 0), 0),
        lifetime_energy_kwh: sites.reduce((sum, site) => sum + (Number(site.lifetime_energy_kwh) || 0), 0),
        normal_count: counts.normal,
        offline_count: counts.offline,
        faulty_count: counts.faulty,
        unknown_count: counts.unknown,
        collector_status: collectorStatus,
      };
    });
  const performanceRows = state.sites
    .map((site) => {
      const capacity = Number(site.capacity_kw) || 0;
      const today = Number(site.today_energy_kwh) || 0;
      const current = Number(site.current_power_kw) || 0;
      return {
        source: site.source || "unknown",
        site_id: site.site_id || "",
        site_name: site.site_name || "",
        status: site.status || "",
        capacity_kw: site.capacity_kw,
        current_power_kw: site.current_power_kw,
        today_energy_kwh: site.today_energy_kwh,
        yield_per_kwp: capacity ? today / capacity : null,
        current_load_percent: capacity ? (current / capacity) * 100 : null,
      };
    })
    .sort((a, b) => (b.yield_per_kwp ?? -1) - (a.yield_per_kwp ?? -1));
  const monthlyRows = state.backendReport?.monthly_rows || state.sites
    .filter((site) => site.month_energy_kwh !== null && site.month_energy_kwh !== undefined && site.month_energy_kwh !== "")
    .map((site) => {
      const capacity = Number(site.capacity_kw) || 0;
      const energy = Number(site.month_energy_kwh) || 0;
      return {
        month: site.month || "current",
        source: site.source || "unknown",
        site_id: site.site_id || "",
        site_name: site.site_name || "",
        energy_kwh: site.month_energy_kwh,
        capacity_kw: site.capacity_kw,
        yield_per_kwp: capacity ? energy / capacity : null,
        coverage: site.monthly_coverage || "current_month",
      };
    })
    .sort((a, b) => String(b.month).localeCompare(String(a.month)) || String(a.source).localeCompare(String(b.source)));
  return {
    sourceRows,
    healthRows: sourceRows.map((row) => ({
      source: row.source,
      collector_status: row.collector_status,
      normal_count: row.normal_count,
      offline_count: row.offline_count,
      faulty_count: row.faulty_count,
      unknown_count: row.unknown_count,
    })),
    performanceRows,
    monthlyRows,
    exceptionRows: state.sites.filter((site) => ["faulty", "offline", "unknown"].includes(statusBucket(site.status))),
  };
}

function renderTable() {
  const rows = filteredSites();
  elements.rowCount.textContent = `${rows.length} sites`;
  elements.empty.hidden = state.view !== "dashboard" || rows.length > 0;
  elements.rows.innerHTML = rows
    .map((site) => {
      const bucket = statusBucket(site.status);
      const rowClass = ["offline", "faulty"].includes(bucket) ? "alert-row" : "";
      return `<tr class="${rowClass}">
        <td><span class="badge">${escapeHtml(site.source || "--")}</span></td>
        <td class="${bucket}">${escapeHtml(site.status || bucket)}</td>
        <td>${escapeHtml(site.site_name || "--")}</td>
        <td>${escapeHtml(site.installed_date || "--")}</td>
        <td>${number(site.capacity_kw)}</td>
        <td>${number(site.battery_capacity_kwh)}</td>
        <td>${number(site.current_power_kw)}</td>
        <td>${number(site.today_energy_kwh)}</td>
        <td>${number(site.month_energy_kwh)}</td>
        <td>${number(site.lifetime_energy_kwh)}</td>
        <td>${escapeHtml(site.last_sync || "--")}</td>
      </tr>`;
    })
    .join("");
}

function renderReports() {
  const report = buildReport();
  const offlineFaulty = report.exceptionRows.length;
  const summary = state.summary || {};
  elements.reportKpis.innerHTML = [
    ["Report Sites", number(state.sites.length, 0)],
    ["Today Yield", `${number(summary.today_energy_kwh)} kWh`],
    ["Total Capacity", `${number(summary.total_capacity_kw)} kWp`],
    ["Exceptions", number(offlineFaulty, 0)],
  ].map(([label, value]) => `<article class="card"><label>${label}</label><strong>${value}</strong></article>`).join("");

  elements.reportSummaryCount.textContent = `${report.sourceRows.length} sources`;
  elements.reportSummaryRows.innerHTML = report.sourceRows.map((row) => `<tr>
    <td><span class="badge">${escapeHtml(row.source)}</span></td>
    <td>${number(row.site_count, 0)}</td>
    <td>${number(row.capacity_kw)}</td>
    <td>${number(row.current_power_kw)}</td>
    <td>${number(row.today_energy_kwh)}</td>
    <td>${number(row.month_energy_kwh)}</td>
    <td>${number(row.lifetime_energy_kwh)}</td>
    <td class="ok">${number(row.normal_count, 0)}</td>
    <td class="offline">${number(row.offline_count, 0)}</td>
    <td class="faulty">${number(row.faulty_count, 0)}</td>
    <td class="unknown">${number(row.unknown_count, 0)}</td>
  </tr>`).join("");

  elements.reportHealthCount.textContent = `${report.healthRows.length} sources`;
  elements.reportHealthRows.innerHTML = report.healthRows.map((row) => `<tr>
    <td><span class="badge">${escapeHtml(row.source)}</span></td>
    <td class="${escapeHtml(row.collector_status)}">${escapeHtml(row.collector_status)}</td>
    <td class="ok">${number(row.normal_count, 0)}</td>
    <td class="offline">${number(row.offline_count, 0)}</td>
    <td class="faulty">${number(row.faulty_count, 0)}</td>
    <td class="unknown">${number(row.unknown_count, 0)}</td>
  </tr>`).join("");

  elements.performanceCount.textContent = `${report.performanceRows.length} sites`;
  elements.performanceRows.innerHTML = report.performanceRows.map((site) => {
    const bucket = statusBucket(site.status);
    const rowClass = ["offline", "faulty"].includes(bucket) ? "alert-row" : "";
    return `<tr class="${rowClass}">
      <td><span class="badge">${escapeHtml(site.source || "--")}</span></td>
      <td class="${bucket}">${escapeHtml(site.status || bucket)}</td>
      <td>${escapeHtml(site.site_name || "--")}</td>
      <td>${number(site.capacity_kw)}</td>
      <td>${number(site.current_power_kw)}</td>
      <td>${number(site.today_energy_kwh)}</td>
      <td>${number(site.yield_per_kwp, 3)}</td>
      <td>${number(site.current_load_percent)}</td>
    </tr>`;
  }).join("");

  elements.monthlyCount.textContent = `${report.monthlyRows.length} rows`;
  elements.monthlyRows.innerHTML = report.monthlyRows.map((row) => `<tr>
    <td>${escapeHtml(row.month || "--")}</td>
    <td><span class="badge">${escapeHtml(row.source || "--")}</span></td>
    <td>${escapeHtml(row.site_name || "--")}</td>
    <td>${number(row.energy_kwh)}</td>
    <td>${number(row.capacity_kw)}</td>
    <td>${number(row.yield_per_kwp, 3)}</td>
    <td>${escapeHtml(row.coverage || "--")}</td>
  </tr>`).join("");

  elements.exceptionCount.textContent = `${report.exceptionRows.length} exceptions`;
  elements.exceptionRows.innerHTML = report.exceptionRows.map((site) => {
    const bucket = statusBucket(site.status);
    const rowClass = ["offline", "faulty"].includes(bucket) ? "alert-row" : "";
    return `<tr class="${rowClass}">
      <td><span class="badge">${escapeHtml(site.source || "--")}</span></td>
      <td class="${bucket}">${escapeHtml(site.status || bucket)}</td>
      <td>${escapeHtml(site.site_name || "--")}</td>
      <td>${number(site.capacity_kw)}</td>
      <td>${number(site.current_power_kw)}</td>
      <td>${number(site.today_energy_kwh)}</td>
      <td>${escapeHtml(site.last_sync || "--")}</td>
    </tr>`;
  }).join("");
}

function monthlyCell(value) {
  if (value === "On process") return `<span class="status-chip in-progress">On process</span>`;
  if (value === "N/A" || value === null || value === undefined || value === "") return `<span class="status-chip muted">N/A</span>`;
  return number(value);
}

function renderMonthlyKwh() {
  const table = state.monthlyKwh || { months: [], current_month: "", rows: [] };
  const monthHeaders = table.months.map((month) => {
    const label = month === table.current_month ? `${month} (On process)` : month;
    return `<th>${escapeHtml(label)}</th>`;
  }).join("");
  elements.monthlyKwhHead.innerHTML = `<tr>
    <th>Source</th>
    <th>Site Name</th>
    <th>Capacity kWp</th>
    ${monthHeaders}
  </tr>`;
  elements.monthlyKwhRows.innerHTML = table.rows.map((row) => `<tr>
    <td><span class="badge">${escapeHtml(row.source || "--")}</span></td>
    <td>${escapeHtml(row.site_name || "--")}</td>
    <td>${number(row.capacity_kw)}</td>
    ${table.months.map((month) => `<td>${monthlyCell(row.values?.[month])}</td>`).join("")}
  </tr>`).join("");
  elements.monthlyKwhCount.textContent = `${table.rows.length} sites`;
  if (state.monthlyKwhLoading) {
    elements.monthlyKwhStatus.textContent = "Loading monthly kWh data...";
  } else if (state.monthlyKwhLoaded) {
    elements.monthlyKwhStatus.textContent = `Loaded ${table.months.length} months. Current month ${table.current_month || "--"} is On process.`;
  } else {
    elements.monthlyKwhStatus.textContent = "Open this page to load monthly kWh data.";
  }
}

function renderErrors(errors) {
  elements.errors.hidden = !errors.length;
  elements.errors.textContent = errors.join("\n");
}

function renderCacheMeta() {
  elements.cacheMeta.textContent = `Data updates when the Dashboard loads or Refresh is pressed. Last update: ${formatDateTime(state.lastRefreshAt)}.`;
}

function render() {
  renderKpis(state.summary);
  renderHealth(state.summary);
  renderTable();
  renderErrors(state.errors);
  renderCacheMeta();
  renderReports();
  renderMonthlyKwh();
  renderView();
}

function renderView() {
  for (const section of elements.viewSections) section.hidden = section.dataset.view !== state.view;
  for (const link of elements.viewLinks) link.classList.toggle("active", link.dataset.viewLink === state.view);
}

function setView(view) {
  state.view = view;
  window.location.hash = view;
  renderView();
  if (view === "reports") renderReports();
  if (view === "monthly") loadMonthlyKwh(false);
}

function rowsToCsv(rows, fields) {
  const escapeCell = (value) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [fields.join(","), ...rows.map((row) => fields.map((field) => escapeCell(row[field])).join(","))].join("\n");
}

function downloadCsv(filename, text) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportSummaryReport() {
  const rows = buildReport().sourceRows;
  downloadCsv("solar-source-summary.csv", rowsToCsv(rows, ["source", "site_count", "capacity_kw", "current_power_kw", "today_energy_kwh", "month_energy_kwh", "lifetime_energy_kwh", "normal_count", "offline_count", "faulty_count", "unknown_count"]));
}

function exportExceptionReport() {
  const rows = buildReport().exceptionRows;
  downloadCsv("solar-exceptions.csv", rowsToCsv(rows, ["source", "status", "site_id", "site_name", "capacity_kw", "current_power_kw", "today_energy_kwh", "last_sync"]));
}

function exportPerformanceReport() {
  const rows = buildReport().performanceRows;
  downloadCsv("solar-site-performance.csv", rowsToCsv(rows, ["source", "status", "site_id", "site_name", "capacity_kw", "current_power_kw", "today_energy_kwh", "yield_per_kwp", "current_load_percent"]));
}

function exportMonthlyReport() {
  const rows = buildReport().monthlyRows;
  downloadCsv("solar-monthly-kwh.csv", rowsToCsv(rows, ["month", "source", "site_id", "site_name", "energy_kwh", "capacity_kw", "yield_per_kwp", "coverage"]));
}

async function loadMonthlyHistory() {
  elements.loadMonthlyHistory.disabled = true;
  elements.loadMonthlyHistory.textContent = "Loading...";
  const response = await fetch("/api/reports");
  const data = await response.json();
  state.backendReport = data.report || null;
  state.errors = data.errors || [];
  renderReports();
  renderErrors(state.errors);
  elements.loadMonthlyHistory.textContent = "Load History";
  elements.loadMonthlyHistory.disabled = false;
}

async function loadMonthlyKwh(force = false) {
  if (state.monthlyKwhLoading || (state.monthlyKwhLoaded && !force)) return;
  state.monthlyKwhLoading = true;
  elements.refreshMonthlyKwh.disabled = true;
  renderMonthlyKwh();
  try {
    const response = await fetch("/api/monthly-kwh");
    const data = await response.json();
    state.monthlyKwh = data.monthly_kwh || { months: [], current_month: "", rows: [] };
    state.summary = data.summary || state.summary;
    state.errors = data.errors || [];
    state.lastRefreshAt = data.last_refresh_at || state.lastRefreshAt;
    state.monthlyKwhLoaded = true;
  } finally {
    state.monthlyKwhLoading = false;
    elements.refreshMonthlyKwh.disabled = false;
    renderMonthlyKwh();
    renderErrors(state.errors);
    renderCacheMeta();
  }
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
  state.lastRefreshAt = data.last_refresh_at || null;
  state.nextRefreshAt = data.next_refresh_at || null;
  state.refreshSchedule = data.refresh_schedule || [];
  render();
  elements.refresh.disabled = false;
}

for (const input of [elements.query, elements.source, elements.status, elements.country]) {
  input.addEventListener("input", renderTable);
}
elements.refresh.addEventListener("click", () => loadData(true));
elements.exportSummary.addEventListener("click", exportSummaryReport);
elements.exportPerformance.addEventListener("click", exportPerformanceReport);
elements.loadMonthlyHistory.addEventListener("click", loadMonthlyHistory);
elements.refreshMonthlyKwh.addEventListener("click", () => loadMonthlyKwh(true));
elements.exportMonthly.addEventListener("click", exportMonthlyReport);
elements.exportExceptions.addEventListener("click", exportExceptionReport);
for (const link of elements.viewLinks) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    setView(link.dataset.viewLink);
  });
}

const initialView = window.location.hash.replace("#", "");
state.view = ["reports", "monthly"].includes(initialView) ? initialView : "dashboard";
if (state.view === "monthly") {
  renderMonthlyKwh();
  renderErrors(state.errors);
  renderCacheMeta();
  renderView();
  loadMonthlyKwh(false);
} else {
  loadData(false);
}
