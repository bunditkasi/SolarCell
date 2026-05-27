# Solar API Field Mapping Design

## Goal

Create a clear data dictionary for Huawei FusionSolar and Atmoce OpenAPI, then decide which fields should be normalized into shared report columns. The dashboard must not silently merge fields whose meaning is uncertain. Each mapping group requires user approval before implementation.

## Current State

The app already normalizes a small shared site schema:

- `source`
- `site_id`
- `site_name`
- `status`
- `country`
- `installed_date`
- `capacity_kw`
- `battery_capacity_kwh`
- `current_power_kw`
- `today_energy_kwh`
- `month_energy_kwh`
- `lifetime_energy_kwh`
- `last_sync`
- `collector_status`

Atmoce now uses the official OpenAPI connector when `ATMOCE_APP_KEY` and `ATMOCE_APP_SECRET` are configured. Huawei uses FusionSolar Northbound API.

## Available Atmoce API Data

Atmoce data is available from the official OpenAPI reference and verified with live calls.

### Authentication

- `POST /openapi/v1/auth/token`
- `POST /openapi/v1/auth/cancel_token`

### Site Basic Data

Endpoints:

- `GET /openapi/v1/sites/getSites`
- `GET /openapi/v1/sites/getSite`

Relevant fields:

- `siteId`
- `name`
- `buildState`
- `countryGEC`
- `countryISO`
- `countrySTANAG`
- `timeZone`
- `longitude`
- `latitude`
- `address`
- `solarCapacity`
- `MICapacity`
- `batteryCapacity`
- `gridTiedTime`
- `phaseType`
- `maxChargePower`
- `maxDischargePower`

### Atmoce Device Data

Endpoint:

- `GET /openapi/v1/device/getDevicesBySite`

Verified device groups:

- `gateway`
- `micro_inverter`
- `storage`

Relevant fields:

- `siteId`
- `deviceSN`
- `deviceType`
- `deviceMode`
- `gatewayMode`
- `gatewayOutputMode`
- `MICapacity`
- `batteryCapacity`
- `maxChargePower`
- `maxDischargePower`

### Atmoce Site Latest Power

Endpoint:

- `GET /openapi/v1/sites/getSitesLastPower`

Relevant fields:

- `siteId`
- `lastReportedTime`
- `status`
- `solarGenerationPower`
- `solarReactivePower`
- `dailySolarGeneration`
- `monthlySolarGeneration`
- `yearlySolarGeneration`
- `lifetimeSolarGeneration`
- `gridPower`
- `dailyToGrid`
- `dailyFromGrid`
- `monthlyToGrid`
- `monthlyFromGrid`
- `yearlyToGrid`
- `yearlyFromGrid`
- `lifetimeToGrid`
- `lifetimeFromGrid`
- `consumptionPower`
- `dailyConsumption`
- `monthlyConsumption`
- `yearlyConsumption`
- `lifetimeConsumption`
- `batteryPower`
- `batterySOC`
- `batteryStatus`
- `batteryMode`
- `dailyBatteryCharging`
- `dailyBatteryDischarge`
- `monthlyBatteryCharging`
- `monthlyBatteryDischarge`
- `yearlyBatteryCharging`
- `yearlyBatteryDischarge`
- `lifetimeBatteryCharging`
- `lifetimeBatteryDischarge`
- `totalCo2Reduced`
- `totalTreesPlanted`

### Atmoce Site Energy Summary

Endpoint:

- `GET /openapi/v1/sites/getSitesEnergy`

Relevant fields:

- `siteId`
- `dateType`
- `date`
- `solarGeneration`
- `consumption`
- `toGrid`
- `fromGrid`
- `batteryCharging`
- `batteryDischarge`

### Atmoce Microinverter Data

Endpoints:

- `GET /openapi/v1/microInverter/getMIsLastData`
- `GET /openapi/v1/microInverter/getMIsHistoryData`
- `GET /openapi/v1/microInverter/getMIsDayData`

Relevant fields:

- `SN`
- `lastReportedTime`
- `status`
- `generationPower`
- `dailyGeneration`
- `monthlyGeneration`
- `yearlyGeneration`
- `lifetimeGeneration`
- `pvData`
- `pvNumber`
- `pvPower`
- `pvDailyGeneration`
- `pvMonthlyGeneration`
- `pvYearlyGeneration`
- `pvLifetimeGeneration`

### Atmoce Battery Data

Endpoints:

- `GET /openapi/v1/battery/getBatterysLastData`
- `GET /openapi/v1/battery/getBatterysHistoryData`
- `GET /openapi/v1/battery/getBatterysDayData`

Relevant fields:

- `SN`
- `lastReportedTime`
- `status`
- `power`
- `SOC`
- `batteryMode`
- `dailyCharging`
- `dailyDischarge`
- `monthlyCharging`
- `monthlyDischarge`
- `yearlyCharging`
- `yearlyDischarge`
- `lifetimeCharging`
- `lifetimeDischarge`

### Atmoce Gateway Data

Endpoints:

- `GET /openapi/v1/gateway/getGatewaysLastData`
- `GET /openapi/v1/gateway/getGatewaysHistoryData`
- `GET /openapi/v1/gateway/getGatewaysEnergy`

Relevant fields:

- `lastReportedTime`
- `status`
- `solarGenerationPower`
- `solarGenerationPowerA`
- `solarGenerationPowerB`
- `solarGenerationPowerC`
- `solarReactivePower`
- `gridPower`
- `gridPowerA`
- `gridPowerB`
- `gridPowerC`
- `gridPowerL1`
- `gridPowerL2`
- `gridVoltage`
- `gridVoltageA`
- `gridVoltageB`
- `gridVoltageC`
- `gridVoltageL1`
- `gridVoltageL2`
- `gridVoltageAB`
- `gridVoltageBC`
- `gridVoltageCA`
- `consumptionPower`
- `batteryPower`
- `batteryPowerA`
- `batteryPowerB`
- `batteryPowerC`
- `batterySOC`
- `batteryStatus`
- `batteryMode`
- daily, monthly, yearly, and lifetime solar/consumption/grid/battery energy totals

### Atmoce Control Data

Endpoints:

- `POST /openapi/v1/device/paramSet`
- `GET /openapi/v1/device/getParamSettingTask`
- `POST /openapi/v1/device/paramRead`
- `GET /openapi/v1/device/getParamReadingTask`

Decision: exclude these from reporting for now because they are control/readback APIs for settings rather than operational reporting. Never call write/control APIs from the dashboard without a separate approval flow.

## Available Huawei API Data

Huawei data is available from FusionSolar Northbound API and verified with live calls.

### Authentication

- `POST /thirdData/login`

### Plant List

Endpoint:

- `POST /thirdData/getStationList`

Verified fields:

- `stationCode`
- `stationName`
- `capacity`
- `stationAddr`
- `stationLinkman`
- `linkmanPho`
- `aidType`
- `buildState`
- `combineType`

Huawei documentation also notes newer plant-list APIs may exist in some regions, including `/thirdData/stations`. Keep `getStationList` while it works in the current region.

### Plant Real-Time KPI

Endpoint:

- `POST /thirdData/getStationRealKpi`

Verified fields in `dataItemMap`:

- `day_power`
- `month_power`
- `total_power`
- `day_on_grid_energy`
- `day_use_energy`
- `day_income`
- `total_income`
- `real_health_state`

### Huawei Device List

Endpoint:

- `POST /thirdData/getDevList`

Verified fields:

- `id`
- `devDn`
- `devName`
- `devTypeId`
- `esnCode`
- `model`
- `invType`
- `softwareVersion`
- `stationCode`
- `latitude`
- `longitude`
- `optimizerNumber`

Verified device type IDs from sample:

- `1`
- `47`
- `62`

The exact device type meaning should be confirmed from Huawei documentation before mapping them to user-facing labels.

### Huawei Device KPI APIs

Huawei documentation describes additional interfaces for device-level real-time and historical KPI data, including:

- real-time device data
- daily device KPI
- monthly device KPI
- yearly device KPI

These are not yet implemented in the app because they require careful rate-limit handling and device-type-specific mapping.

## Proposed Canonical Mapping Groups

### Group 1: Core Report Fields

These fields are safe to normalize first and should power the dashboard and first reports.

| Canonical field | Atmoce source | Huawei source | Notes |
| --- | --- | --- | --- |
| `source` | fixed `atmoce` | fixed `huawei` | Already implemented |
| `site_id` | `siteId` | `stationCode` | Same purpose |
| `site_name` | `name` | `stationName` | Same purpose |
| `status` | `status` from site latest power | `real_health_state` | Requires common status labels |
| `country` | `countryISO`, fallback GEC/STANAG | plant address/country if available | Huawei current response has address but not clean country |
| `installed_date` | `gridTiedTime` | plant grid connection field if available | Huawei current response may be blank |
| `capacity_kw` | `solarCapacity` | `capacity * 1000` | Huawei reports MW |
| `current_power_kw` | `solarGenerationPower / 1000` | Huawei plant or device active power if available | Huawei current plant KPI does not always expose current power |
| `today_energy_kwh` | `dailySolarGeneration` | `day_power` | Same reporting intent |
| `month_energy_kwh` | `monthlySolarGeneration` | `month_power` | Same reporting intent |
| `lifetime_energy_kwh` | `lifetimeSolarGeneration` | `total_power` | Same reporting intent |
| `last_sync` | `lastReportedTime` | request time or KPI timestamp if available | Huawei current response has no per-row timestamp |

### Group 2: Energy Flow Fields

These fields should be added to reports after approval because vendor definitions may differ.

| Canonical field | Atmoce source | Huawei source | Notes |
| --- | --- | --- | --- |
| `current_grid_power_kw` | `gridPower / 1000` | device/plant KPI if available | Direction sign must be documented |
| `current_consumption_kw` | `consumptionPower / 1000` | device/plant KPI if available | May require Huawei device KPI |
| `today_grid_export_kwh` | `dailyToGrid` | `day_on_grid_energy` | Likely same concept |
| `today_grid_import_kwh` | `dailyFromGrid` | not confirmed | Huawei may require device/meter KPI |
| `today_consumption_kwh` | `dailyConsumption` | `day_use_energy` | Likely same concept |
| `month_grid_export_kwh` | `monthlyToGrid` | not confirmed | Atmoce available |
| `month_grid_import_kwh` | `monthlyFromGrid` | not confirmed | Atmoce available |
| `lifetime_grid_export_kwh` | `lifetimeToGrid` | not confirmed | Atmoce available |
| `lifetime_grid_import_kwh` | `lifetimeFromGrid` | not confirmed | Atmoce available |

### Group 3: Battery Fields

These fields should be added only if battery reporting is needed on the report page.

| Canonical field | Atmoce source | Huawei source | Notes |
| --- | --- | --- | --- |
| `battery_capacity_kwh` | `batteryCapacity` | device info if available | Already partially implemented for Atmoce |
| `battery_soc_pct` | `batterySOC` or battery `SOC` | device KPI if available | Huawei requires device KPI mapping |
| `current_battery_power_kw` | `batteryPower / 1000` or battery `power / 1000` | device KPI if available | Direction sign must be documented |
| `today_battery_charge_kwh` | `dailyBatteryCharging` or `dailyCharging` | device KPI if available | Atmoce has site and battery-level values |
| `today_battery_discharge_kwh` | `dailyBatteryDischarge` or `dailyDischarge` | device KPI if available | Atmoce has site and battery-level values |
| `month_battery_charge_kwh` | `monthlyBatteryCharging` or `monthlyCharging` | device KPI if available | Optional |
| `month_battery_discharge_kwh` | `monthlyBatteryDischarge` or `monthlyDischarge` | device KPI if available | Optional |
| `lifetime_battery_charge_kwh` | `lifetimeBatteryCharging` or `lifetimeCharging` | device KPI if available | Optional |
| `lifetime_battery_discharge_kwh` | `lifetimeBatteryDischarge` or `lifetimeDischarge` | device KPI if available | Optional |

## Approval Flow

Implement mapping in this order:

1. Ask for approval for Group 1 Core Report Fields.
2. Implement and test Group 1 only.
3. Ask for approval for Group 2 Energy Flow Fields.
4. Implement Group 2 only if approved.
5. Ask for approval for Group 3 Battery Fields.
6. Implement Group 3 only if approved.

No write/control APIs are in scope for this mapping work.

## Testing Strategy

- Unit tests for Atmoce OpenAPI normalization.
- Unit tests for Huawei plant KPI normalization.
- Unit tests for status mapping.
- Live smoke test with production-like credentials.
- Vercel production smoke test after deployment.

## Open Decisions

1. Huawei status mapping is approved as `health_state_3 = Normal`, `health_state_1 = Offline`, and `health_state_2 = Fault`.
2. Should `current_power_kw` be blank for Huawei until device KPI is added, or should another Huawei plant field be used if available?
3. Should Energy Flow and Battery fields be visible on the main dashboard table or only on the Reports page?
