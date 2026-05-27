import unittest

from solar_fetch import HuaweiClient, normalize_atmoce_openapi_site, normalize_atmoce_station, normalize_huawei_station


class NormalizeSolarDataTest(unittest.TestCase):
    def test_normalize_atmoce_station_uses_common_schema(self):
        row = {
            "stationId": 1637,
            "stationName": "PKON",
            "stationRunStatusName": "Normal",
            "country": "Thailand",
            "gridConnectedDate": "2026-05-23",
            "panelCapacity": 42.9,
            "storageCapacity": 14,
            "generationPower": 30081,
            "dailyGeneration": 166.69,
            "totalGeneration": 644.25,
        }

        normalized = normalize_atmoce_station(row)

        self.assertEqual(normalized["source"], "atmoce")
        self.assertEqual(normalized["site_id"], "1637")
        self.assertEqual(normalized["site_name"], "PKON")
        self.assertEqual(normalized["status"], "Normal")
        self.assertEqual(normalized["capacity_kw"], 42.9)
        self.assertEqual(normalized["battery_capacity_kwh"], 14.0)
        self.assertEqual(normalized["current_power_kw"], 30.081)
        self.assertEqual(normalized["today_energy_kwh"], 166.69)
        self.assertEqual(normalized["lifetime_energy_kwh"], 644.25)
        self.assertRegex(normalized["last_sync"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(normalized["collector_status"], "ok")

    def test_normalize_atmoce_openapi_site_uses_official_fields(self):
        site = {
            "siteId": "764260751203",
            "name": "PRMB",
            "countryISO": "TH",
            "gridTiedTime": "27/01/2026",
            "solarCapacity": 37.18,
            "batteryCapacity": 14,
        }
        last_power = {
            "siteId": "764260751203",
            "lastReportedTime": 1779849000000,
            "status": 1,
            "solarGenerationPower": 15227,
            "dailySolarGeneration": 28.53,
            "monthlySolarGeneration": 4174.25,
            "lifetimeSolarGeneration": 19733.02,
        }

        normalized = normalize_atmoce_openapi_site(site, last_power)

        self.assertEqual(normalized["source"], "atmoce")
        self.assertEqual(normalized["site_id"], "764260751203")
        self.assertEqual(normalized["site_name"], "PRMB")
        self.assertEqual(normalized["status"], "Normal")
        self.assertEqual(normalized["country"], "TH")
        self.assertEqual(normalized["installed_date"], "2026-01-27")
        self.assertEqual(normalized["capacity_kw"], 37.18)
        self.assertEqual(normalized["battery_capacity_kwh"], 14.0)
        self.assertEqual(normalized["current_power_kw"], 15.227)
        self.assertEqual(normalized["today_energy_kwh"], 28.53)
        self.assertEqual(normalized["month_energy_kwh"], 4174.25)
        self.assertEqual(normalized["lifetime_energy_kwh"], 19733.02)
        self.assertEqual(normalized["last_sync"], "2026-05-27T02:30:00+00:00")
        self.assertEqual(normalized["collector_status"], "ok")

    def test_normalize_huawei_station_merges_kpi_data(self):
        station = {
            "stationCode": "NE=55039818",
            "stationName": "12  PLPR  Mr.DIY Nern payom.",
            "capacity": 0.03872,
        }
        kpi = {
            "stationCode": "NE=55039818",
            "dataItemMap": {
                "day_power": 112.4,
                "total_power": 75747.72,
                "real_health_state": 3,
                "month_power": 3951.52,
            },
        }

        normalized = normalize_huawei_station(station, kpi)

        self.assertEqual(normalized["source"], "huawei")
        self.assertEqual(normalized["site_id"], "NE=55039818")
        self.assertEqual(normalized["site_name"], "12  PLPR  Mr.DIY Nern payom.")
        self.assertEqual(normalized["capacity_kw"], 38.72)
        self.assertEqual(normalized["today_energy_kwh"], 112.4)
        self.assertEqual(normalized["lifetime_energy_kwh"], 75747.72)
        self.assertEqual(normalized["status"], "health_state_3")
        self.assertRegex(normalized["last_sync"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(normalized["collector_status"], "ok")

    def test_huawei_fetch_stations_keeps_station_list_when_realtime_kpi_is_rate_limited(self):
        class FakeHuaweiClient(HuaweiClient):
            def __init__(self):
                pass

            def post(self, path, payload):
                if path == "/thirdData/getStationList":
                    return {
                        "data": [
                            {
                                "stationCode": "NE=1",
                                "stationName": "Demo Station",
                                "capacity": 0.0312,
                            }
                        ]
                    }
                if path == "/thirdData/getStationRealKpi":
                    raise RuntimeError("Huawei request failed: {'failCode': 407, 'data': 'ACCESS_FREQUENCY_IS_TOO_HIGH'}")
                raise AssertionError(path)

        rows = FakeHuaweiClient().fetch_stations()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["site_id"], "NE=1")
        self.assertEqual(rows[0]["capacity_kw"], 31.2)
        self.assertIsNone(rows[0]["today_energy_kwh"])
        self.assertEqual(rows[0]["collector_status"], "degraded")


if __name__ == "__main__":
    unittest.main()
