# Solar Operations Dashboard Design

## Goal

Build a webapp that replaces separate Huawei FusionSolar and Atmoce logins for day-to-day solar monitoring and reporting. The first screen should feel familiar to users of Huawei FusionSolar Home/List View, while remaining a distinct MR.DIY internal dashboard rather than a copy of Huawei's branding or assets.

The app will combine data from:

- Huawei FusionSolar Northbound API as the primary Huawei source.
- Huawei web login collector as a fallback when API access is unavailable, rate-limited, or incomplete.
- Atmoce portal API as the current Atmoce source.

## MVP Scope

The first implementation focuses on a single operations dashboard and exportable site list.

In scope:

- Unified dashboard for Huawei and Atmoce sites.
- KPI cards for current power, yield today, total yield, total capacity, and status counts.
- Source health card showing Huawei API, Huawei web fallback, and Atmoce collector state.
- Filterable table of all sites.
- CSV export from the unified table.
- Manual refresh.
- Connector layer that normalizes Huawei and Atmoce data into one schema.

Out of scope for the first release:

- User account management.
- Historical trend database.
- Scheduled background jobs.
- PDF report generation.
- Alarm workflows beyond showing summary counts when available.
- Editing plant/site settings in vendor systems.

## UX Direction

The UI should use a Huawei-inspired operations layout:

- Horizontal top navigation with `Dashboard`, `Sites`, `Reports`, `Alerts`, and `Settings`.
- A compact KPI band across the top.
- A status summary section for normal, faulty, offline/disconnected, and alarm counts.
- A filter bar above the table with site name, source, status, country, and site/device ID.
- A dense table optimized for scanning many branches.

The UI must not copy Huawei's logo, icons, proprietary images, or exact color treatment. Use a restrained MR.DIY internal operations look: clean white/gray surfaces, strong table readability, source badges for Huawei and Atmoce, and status colors that are clear but not decorative.

## Dashboard Layout

The first screen is `Solar Operations`.

Top KPI cards:

- Total Current Power, in kW or MW depending on magnitude.
- Yield Today, in kWh or MWh.
- Total Yield, in kWh/MWh/GWh.
- Total Capacity, in kWp/MWp.
- Site Status counts: Normal, Faulty, Offline.
- Data Source Health: Huawei API, Huawei Web, Atmoce.

Main controls:

- Search by site name.
- Filter by source: All, Huawei, Atmoce.
- Filter by status: All, Normal, Faulty, Offline, Unknown.
- Filter by country or region.
- Search by site ID or device ID when available.
- Refresh button.
- Export CSV button.

Main table columns:

- Source.
- Status.
- Site Name.
- Install/Grid Date.
- Capacity kWp.
- Battery kWh.
- Current Power kW.
- Today kWh.
- Month kWh.
- Lifetime kWh.
- Last Sync.
- Action/View.

## Data Model

The app uses one normalized site record:

```json
{
  "source": "huawei | atmoce",
  "site_id": "string",
  "site_name": "string",
  "status": "string",
  "country": "string",
  "installed_date": "string",
  "capacity_kw": 0,
  "battery_capacity_kwh": 0,
  "current_power_kw": 0,
  "today_energy_kwh": 0,
  "month_energy_kwh": 0,
  "lifetime_energy_kwh": 0,
  "last_sync": "ISO timestamp",
  "collector_status": "ok | degraded | failed"
}
```

Known source mappings:

- Atmoce `generationPower` is watts and converts to `current_power_kw`.
- Atmoce `dailyGeneration` maps to `today_energy_kwh`.
- Atmoce `totalGeneration` maps to `lifetime_energy_kwh`.
- Huawei `capacity` from Northbound API is MW and converts to `capacity_kw`.
- Huawei `day_power` maps to `today_energy_kwh`.
- Huawei `month_power` maps to `month_energy_kwh`.
- Huawei `total_power` maps to `lifetime_energy_kwh`.

## Data Flow

1. User opens the dashboard.
2. Backend calls the unified collector.
3. Collector fetches Atmoce data through the portal API.
4. Collector fetches Huawei data through Northbound API.
5. If Huawei KPI calls fail due to rate limit or auth issues, the collector can fall back to the Huawei web collector.
6. Backend normalizes all rows into the common schema.
7. Frontend renders KPI summaries, source health, filters, and the table.
8. Export uses the same normalized rows currently displayed.

## Huawei Web Fallback

Huawei web fallback should be isolated from the API collector.

Fallback behavior:

- Use the web account only when configured and needed.
- Prefer an existing browser session when possible.
- Read list-view data from the Huawei web dashboard or trigger export if available.
- Never change settings, add plants, delete plants, or acknowledge alarms.
- Mark records from web fallback as `collector_status=degraded` if some fields are missing.

This fallback is less stable than the API because the vendor web UI may change and may require captcha, MFA, or manual login. The dashboard must communicate that state clearly instead of silently failing.

## Error Handling

Collector errors should be visible but not destroy the entire dashboard.

- If Atmoce fails, show Huawei rows and mark Atmoce source health as failed.
- If Huawei API station list succeeds but KPI is rate-limited, show Huawei station rows with blank KPI values and mark Huawei API as degraded.
- If Huawei API fails and web fallback succeeds, show web fallback rows and mark Huawei API as failed, Huawei Web as ok.
- If all collectors fail, show an empty state with the latest error summaries.

Secrets must come from environment variables or a local config file excluded from git.

## Testing

Core tests:

- Normalize Atmoce site records into the common schema.
- Normalize Huawei station and KPI records into the common schema.
- Huawei API rate-limit fallback returns station rows instead of failing the whole fetch.
- Dashboard summary calculations handle missing KPI values.
- Filters apply correctly by source, status, and site name.

Manual verification:

- Run live collector and confirm expected source counts.
- Open dashboard on desktop width and verify KPI cards, filters, and table are readable.
- Export CSV and confirm it matches the displayed data.

## Acceptance Criteria

- The first screen shows a Huawei-inspired but distinct `Solar Operations` dashboard.
- Dashboard combines Huawei and Atmoce data in one table.
- User can filter by source and status.
- User can refresh data manually.
- User can export the unified table to CSV.
- Collector failures are shown per source without breaking other sources.
- Real credentials are never committed to the repository.
