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
$env:HUAWEI01_USERNAME="your-huawei01-northbound-username"
$env:HUAWEI01_PASSWORD="your-huawei01-northbound-system-code-or-password"
$env:HUAWEI01_JSON_PATH="data/huawei01_sites.json"
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
$env:HUAWEI01_USERNAME="your-huawei01-northbound-username"
$env:HUAWEI01_PASSWORD="your-huawei01-northbound-system-code-or-password"
$env:HUAWEI01_JSON_PATH="data/huawei01_sites.json"
```

Start the local dashboard:

```powershell
python solar_dashboard.py
```

Open:

```text
http://127.0.0.1:8000
```

The dashboard fetches fresh data when the Dashboard loads or when `Refresh` is pressed. The Reports tab reuses the data already loaded in the browser and does not trigger another vendor API call when switching tabs.

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

Huawei01 uses its Northbound API when `HUAWEI01_USERNAME` and `HUAWEI01_SYSTEM_CODE` or `HUAWEI01_PASSWORD` are configured. If those variables are missing, it falls back to the FusionSolar web snapshot at `data/huawei01_sites.json` or the path in `HUAWEI01_JSON_PATH`.
