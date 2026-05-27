# Solar Data Connector

Fetches solar site data from Atmoce Cloud and Huawei FusionSolar Northbound API, then normalizes both sources into one schema.

## Setup

Set credentials as environment variables. Do not commit real credentials.

PowerShell example:

```powershell
$env:ATMOCE_APP_KEY="your-atmoce-openapi-app-key"
$env:ATMOCE_APP_SECRET="your-atmoce-openapi-app-secret"
$env:ATMOCE_USERNAME="your-atmoce-username"
$env:ATMOCE_PASSWORD="your-atmoce-password"
$env:HUAWEI_USERNAME="your-huawei-northbound-username"
$env:HUAWEI_SYSTEM_CODE="your-huawei-northbound-system-code"
```

## Run

```powershell
python solar_fetch.py --format json --output output\solar-sites.json
python solar_fetch.py --format csv --output output\solar-sites.csv
```

## Run Dashboard

Set credentials in PowerShell:

```powershell
$env:ATMOCE_APP_KEY="your-atmoce-openapi-app-key"
$env:ATMOCE_APP_SECRET="your-atmoce-openapi-app-secret"
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

The dashboard uses cached data. While the server is running, it automatically refreshes four times per day in Thailand time:

- `08:00`
- `12:00`
- `16:00`
- `20:00`

Press `Refresh` only when you want to update the cache manually.

On Vercel Hobby, cron jobs are limited to once per day. The deployed version therefore uses lazy scheduled refresh: the first request after one of the scheduled rounds refreshes the cache for that round. Manual refresh remains available from the dashboard.

The combined output includes:

- `source`
- `site_id`
- `site_name`
- `status`
- `capacity_kw`
- `battery_capacity_kwh`
- `current_power_kw`
- `today_energy_kwh`
- `month_energy_kwh`
- `lifetime_energy_kwh`

## Notes

Atmoce uses the official OpenAPI flow when `ATMOCE_APP_KEY` and `ATMOCE_APP_SECRET` are configured. The older portal API remains available as a fallback when those variables are not set.

Huawei real-time KPI can return `failCode=407` if called too frequently. In that case the connector still returns the Huawei station list, with KPI values left blank for that run.
