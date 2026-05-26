const state = {
  sites: [],
  summary: null,
  errors: [],
  lastRefreshAt: null,
  nextRefreshAt: null,
  refreshSchedule: [],
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
  const sources = ["huawei", "atmoce"];
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
  elements.errors.textContent = errors.join("\n");
}

function renderCacheMeta() {
  const schedule = state.refreshSchedule.length ? state.refreshSchedule.join(", ") : "08:00, 12:00, 16:00, 20:00";
  elements.cacheMeta.textContent = `Cached data. Last update: ${formatDateTime(state.lastRefreshAt)}. Next scheduled refresh: ${formatDateTime(state.nextRefreshAt)}. Daily rounds: ${schedule}.`;
}

function render() {
  renderKpis(state.summary);
  renderHealth(state.summary);
  renderTable();
  renderErrors(state.errors);
  renderCacheMeta();
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

loadData(false);
