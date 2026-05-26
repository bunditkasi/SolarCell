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
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_or_none(value, digits=3):
    value = _float_or_none(value)
    return round(value, digits) if value is not None else None


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def normalize_huawei_station(station, kpi=None, collector_status="ok"):
    data = (kpi or {}).get("dataItemMap") or {}
    capacity_mw = _float_or_none(station.get("capacity"))
    current_power_kw = _float_or_none(data.get("active_power") or data.get("current_power"))
    return {
        "source": "huawei",
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


class HuaweiClient:
    def __init__(self, base_url, username, system_code):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.system_code = system_code
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
            )
            for station in stations
        ]


def fetch_all():
    atmoce = AtmoceClient(
        os.environ.get("ATMOCE_BASE_URL", "https://www.atmocecloud.com"),
        _required_env("ATMOCE_USERNAME"),
        _required_env("ATMOCE_PASSWORD"),
    )
    huawei = HuaweiClient(
        os.environ.get("HUAWEI_BASE_URL", "https://kr5.fusionsolar.huawei.com"),
        _required_env("HUAWEI_USERNAME"),
        _required_env("HUAWEI_SYSTEM_CODE"),
    )
    return atmoce.fetch_stations() + huawei.fetch_stations()


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
