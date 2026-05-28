import argparse
import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import CookieJar


COMMON_FIELDS = [
    "source",
    "site_id",
    "site_name",
    "status",
    "country",
    "installed_date",
    "capacity_kw",
    "battery_capacity_kwh",
    "current_power_kw",
    "today_energy_kwh",
    "month_energy_kwh",
    "lifetime_energy_kwh",
]


def _float_or_none(value):
    if value in (None, "", "--"):
        return None
    if isinstance(value, str):
        value = value.replace(",", "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_or_none(value, digits=3):
    value = _float_or_none(value)
    return round(value, digits) if value is not None else None


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ms_to_utc_iso(value):
    millis = _float_or_none(value)
    if millis is None:
        return _utc_now_iso()
    return datetime.fromtimestamp(millis / 1000, timezone.utc).replace(microsecond=0).isoformat()


def _ddmmyyyy_to_iso(value):
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return value


def _json_request(opener, method, url, payload=None, headers=None, timeout=30):
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            return json.loads(text), response
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {text[:500]}") from exc


def _unwrap_atmoce_data(response):
    data = response.get("data")
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def _chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def normalize_atmoce_station(row):
    return {
        "source": "atmoce",
        "site_id": str(row.get("stationId") or row.get("businessId") or ""),
        "site_name": row.get("stationName") or row.get("name") or "",
        "status": row.get("stationRunStatusName") or row.get("status") or "",
        "country": row.get("country") or "",
        "installed_date": row.get("gridConnectedDate") or "",
        "capacity_kw": _round_or_none(row.get("panelCapacity")),
        "battery_capacity_kwh": _round_or_none(row.get("storageCapacity")),
        "current_power_kw": _round_or_none((_float_or_none(row.get("generationPower")) or 0) / 1000),
        "today_energy_kwh": _round_or_none(row.get("dailyGeneration")),
        "month_energy_kwh": _round_or_none(row.get("monthGeneration")),
        "lifetime_energy_kwh": _round_or_none(row.get("totalGeneration")),
        "last_sync": _utc_now_iso(),
        "collector_status": "ok",
    }


def normalize_atmoce_openapi_site(site, last_power=None, energy=None):
    last_power = last_power or {}
    energy = energy or {}
    status_map = {0: "Offline", 1: "Normal", 2: "Fault"}
    return {
        "source": "atmoce",
        "site_id": str(site.get("siteId") or ""),
        "site_name": site.get("name") or "",
        "status": status_map.get(last_power.get("status"), str(last_power.get("status") or "")),
        "country": site.get("countryISO") or site.get("countryGEC") or site.get("countrySTANAG") or "",
        "installed_date": _ddmmyyyy_to_iso(site.get("gridTiedTime")),
        "capacity_kw": _round_or_none(site.get("solarCapacity")),
        "battery_capacity_kwh": _round_or_none(site.get("batteryCapacity")),
        "current_power_kw": _round_or_none((_float_or_none(last_power.get("solarGenerationPower")) or 0) / 1000),
        "today_energy_kwh": _round_or_none(last_power.get("dailySolarGeneration") or energy.get("solarGeneration")),
        "month_energy_kwh": _round_or_none(last_power.get("monthlySolarGeneration")),
        "lifetime_energy_kwh": _round_or_none(last_power.get("lifetimeSolarGeneration")),
        "last_sync": _ms_to_utc_iso(last_power.get("lastReportedTime")),
        "collector_status": "ok",
    }


def normalize_huawei_station(station, kpi=None, collector_status="ok", source="huawei"):
    data = (kpi or {}).get("dataItemMap") or {}
    capacity_mw = _float_or_none(station.get("capacity"))
    current_power_kw = _float_or_none(data.get("active_power") or data.get("current_power"))
    return {
        "source": source,
        "site_id": station.get("stationCode") or "",
        "site_name": station.get("stationName") or "",
        "status": f"health_state_{data.get('real_health_state')}" if data.get("real_health_state") is not None else "",
        "country": station.get("country") or "",
        "installed_date": station.get("gridConnectionTime") or "",
        "capacity_kw": round(capacity_mw * 1000, 3) if capacity_mw is not None else None,
        "battery_capacity_kwh": None,
        "current_power_kw": _round_or_none(current_power_kw),
        "today_energy_kwh": _round_or_none(data.get("day_power")),
        "month_energy_kwh": _round_or_none(data.get("month_power")),
        "lifetime_energy_kwh": _round_or_none(data.get("total_power")),
        "last_sync": _utc_now_iso(),
        "collector_status": collector_status,
    }


def normalize_huawei_web_station(row):
    return {
        "source": "huawei01",
        "site_id": row.get("site_id") or row.get("station_dn") or "",
        "site_name": row.get("site_name") or "",
        "status": row.get("status") or "",
        "country": row.get("country") or "",
        "installed_date": row.get("installed_date") or row.get("grid_connection_date") or "",
        "capacity_kw": _round_or_none(row.get("capacity_kw")),
        "battery_capacity_kwh": _round_or_none(row.get("battery_capacity_kwh")),
        "current_power_kw": _round_or_none(row.get("current_power_kw")),
        "today_energy_kwh": _round_or_none(row.get("today_energy_kwh")),
        "month_energy_kwh": _round_or_none(row.get("month_energy_kwh")),
        "lifetime_energy_kwh": _round_or_none(row.get("lifetime_energy_kwh")),
        "last_sync": row.get("last_sync") or _utc_now_iso(),
        "collector_status": row.get("collector_status") or "ok",
    }


def load_huawei01_snapshot(path=None):
    env_path = os.environ.get("HUAWEI01_JSON_PATH")
    path = path or env_path or os.path.join("data", "huawei01_sites.json")
    if not os.path.exists(path):
        if env_path and path == env_path:
            raise RuntimeError(f"Huawei01 snapshot file not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("sites") if isinstance(payload, dict) else payload
    return [normalize_huawei_web_station(row) for row in (rows or [])]


def _fetch_source(label, fetcher):
    try:
        return fetcher()
    except Exception as exc:
        print(f"Warning: {label} fetch failed; skipping source for this run: {exc}", file=sys.stderr)
        return []


class AtmoceClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.authorization = None

    def login(self):
        encoded_password = base64.b64encode(self.password.encode("utf-8")).decode("ascii")
        payload = {
            "username": self.username,
            "encrypted": True,
            "password": encoded_password,
            "appType": "web",
        }
        response, _ = _json_request(
            self.opener,
            "POST",
            f"{self.base_url}/permission-auth/api/login",
            payload,
            headers={"Steck-Accept-Language": "en-US"},
        )
        if response.get("code") != 200:
            raise RuntimeError(f"Atmoce login failed: {response}")
        data = response.get("data") or {}
        self.authorization = f"{data.get('prefix', 'Bearer ')}{data['token']}"

    def post(self, path, payload):
        if not self.authorization:
            self.login()
        response, _ = _json_request(
            self.opener,
            "POST",
            f"{self.base_url}{path}",
            payload,
            headers={
                "Authorization": self.authorization,
                "Steck-Accept-Language": "en-US",
            },
        )
        code = response.get("code")
        if code not in (200, None):
            raise RuntimeError(f"Atmoce request failed for {path}: {response}")
        return response

    def fetch_stations(self, page_size=100):
        response = self.post(
            "/energy-manage/webMultipleStation/getWebStationsBasicInfo",
            {
                "pageIndex": 1,
                "pageSize": page_size,
                "collected": False,
                "timeStamp": int(time.time() * 1000),
            },
        )
        data = response.get("data") or {}
        rows = data.get("data") if isinstance(data, dict) else None
        if isinstance(rows, dict):
            rows = rows.get("data")
        return [normalize_atmoce_station(row) for row in (rows or [])]


class AtmoceOpenApiClient:
    def __init__(self, base_url, app_key, app_secret):
        self.base_url = base_url.rstrip("/")
        self.app_key = app_key
        self.app_secret = app_secret
        self.opener = urllib.request.build_opener()
        self.access_token = None

    def login(self):
        response, _ = _json_request(
            self.opener,
            "POST",
            f"{self.base_url}/openapi/v1/auth/token",
            {
                "grant_type": "system",
                "app_key": self.app_key,
                "app_secret": self.app_secret,
            },
        )
        if not response.get("success"):
            raise RuntimeError(f"Atmoce OpenAPI login failed: {response}")
        data = response.get("data") or {}
        self.access_token = data["access_token"]

    def get(self, path, params=None):
        if not self.access_token:
            self.login()
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        response, _ = _json_request(
            self.opener,
            "GET",
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        if not response.get("success"):
            raise RuntimeError(f"Atmoce OpenAPI request failed for {path}: {response}")
        return response

    def fetch_sites(self):
        sites = []
        page = 1
        while True:
            response = self.get("/openapi/v1/sites/getSites", {"page": page})
            sites.extend(response.get("data") or [])
            if response.get("pageEnd") == 1:
                return sites
            page += 1

    def fetch_stations(self):
        sites = self.fetch_sites()
        site_ids = [site.get("siteId") for site in sites if site.get("siteId")]
        latest_by_id = {}
        energy_by_id = {}
        for chunk in _chunks(site_ids, 100):
            joined = ",".join(chunk)
            latest = self.get("/openapi/v1/sites/getSitesLastPower", {"siteIds": joined})
            for row in latest.get("data") or []:
                latest_by_id[row.get("siteId")] = row
            energy = self.get("/openapi/v1/sites/getSitesEnergy", {"siteIds": joined})
            for row in energy.get("data") or []:
                energy_by_id[row.get("siteId")] = row
        return [
            normalize_atmoce_openapi_site(
                site,
                latest_by_id.get(site.get("siteId")),
                energy_by_id.get(site.get("siteId")),
            )
            for site in sites
        ]


class HuaweiClient:
    def __init__(self, base_url, username, system_code, source="huawei"):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.system_code = system_code
        self.source = source
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.xsrf_token = None

    def login(self):
        response, raw = _json_request(
            self.opener,
            "POST",
            f"{self.base_url}/thirdData/login",
            {"userName": self.username, "systemCode": self.system_code},
        )
        if not response.get("success"):
            raise RuntimeError(f"Huawei login failed: {response}")
        self.xsrf_token = raw.headers.get("xsrf-token") or raw.headers.get("XSRF-TOKEN")
        if not self.xsrf_token:
            raise RuntimeError("Huawei login did not return an XSRF token")

    def post(self, path, payload):
        if not self.xsrf_token:
            self.login()
        response, _ = _json_request(
            self.opener,
            "POST",
            f"{self.base_url}{path}",
            payload,
            headers={"XSRF-TOKEN": self.xsrf_token},
        )
        if not response.get("success"):
            raise RuntimeError(f"Huawei request failed for {path}: {response}")
        return response

    def fetch_stations(self):
        station_response = self.post("/thirdData/getStationList", {})
        stations = station_response.get("data") or []
        codes = [station.get("stationCode") for station in stations if station.get("stationCode")]
        kpi_by_code = {}
        if codes:
            try:
                kpi_response = self.post("/thirdData/getStationRealKpi", {"stationCodes": ",".join(codes[:100])})
                for row in kpi_response.get("data") or []:
                    kpi_by_code[row.get("stationCode")] = row
            except RuntimeError as exc:
                message = str(exc)
                if "407" not in message and "ACCESS_FREQUENCY_IS_TOO_HIGH" not in message:
                    raise
                print("Warning: Huawei real-time KPI rate limit reached; returning station list without KPI values.", file=sys.stderr)
        status = "degraded" if not kpi_by_code and codes else "ok"
        return [
            normalize_huawei_station(
                station,
                kpi_by_code.get(station.get("stationCode")),
                collector_status=status,
                source=self.source,
            )
            for station in stations
        ]


def build_huawei01_fetcher(environ=None):
    environ = environ or os.environ
    if environ.get("HUAWEI01_USERNAME") and (
        environ.get("HUAWEI01_SYSTEM_CODE") or environ.get("HUAWEI01_PASSWORD")
    ):
        client = HuaweiClient(
            environ.get("HUAWEI01_BASE_URL") or environ.get("HUAWEI_BASE_URL", "https://kr5.fusionsolar.huawei.com"),
            environ.get("HUAWEI01_USERNAME"),
            environ.get("HUAWEI01_SYSTEM_CODE") or environ.get("HUAWEI01_PASSWORD"),
            source="huawei01",
        )
        return lambda: fetch_huawei01_stations(client.fetch_stations, load_huawei01_snapshot)
    return load_huawei01_snapshot


def fetch_huawei01_stations(api_fetcher, snapshot_fetcher):
    api_rows = api_fetcher()
    snapshot_rows = snapshot_fetcher()
    snapshot_by_id = {row.get("site_id"): row for row in snapshot_rows if row.get("site_id")}
    rows = []
    for row in api_rows:
        snapshot = snapshot_by_id.get(row.get("site_id")) or {}
        merged = dict(snapshot)
        merged.update({key: value for key, value in row.items() if value not in (None, "")})
        rows.append(merged)
    seen = {row.get("site_id") for row in rows if row.get("site_id")}
    missing = [row for row in snapshot_rows if row.get("site_id") and row.get("site_id") not in seen]
    if not missing:
        return rows
    rows = [dict(row, collector_status="degraded") for row in rows]
    rows.extend(dict(row, collector_status="degraded") for row in missing)
    return rows


def fetch_all():
    atmoce_base_url = os.environ.get("ATMOCE_BASE_URL", "https://www.atmocecloud.com")
    if os.environ.get("ATMOCE_APP_KEY") and os.environ.get("ATMOCE_APP_SECRET"):
        atmoce = AtmoceOpenApiClient(
            atmoce_base_url,
            _required_env("ATMOCE_APP_KEY"),
            _required_env("ATMOCE_APP_SECRET"),
        )
    else:
        atmoce = AtmoceClient(
            atmoce_base_url,
            _required_env("ATMOCE_USERNAME"),
            _required_env("ATMOCE_PASSWORD"),
        )
    huawei = HuaweiClient(
        os.environ.get("HUAWEI_BASE_URL", "https://kr5.fusionsolar.huawei.com"),
        _required_env("HUAWEI_USERNAME"),
        _required_env("HUAWEI_SYSTEM_CODE"),
    )
    return (
        _fetch_source("Atmoce", atmoce.fetch_stations)
        + _fetch_source("Huawei", huawei.fetch_stations)
        + _fetch_source("Huawei01", build_huawei01_fetcher())
    )


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMON_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in COMMON_FIELDS})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch and combine Huawei FusionSolar and Atmoce solar site data.")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--output", help="Optional output file path. Defaults to stdout.")
    args = parser.parse_args(argv)

    rows = fetch_all()
    if args.format == "csv":
        if args.output:
            write_csv(rows, args.output)
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=COMMON_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    else:
        text = json.dumps(rows, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(text)
        else:
            print(text)


if __name__ == "__main__":
    main()
