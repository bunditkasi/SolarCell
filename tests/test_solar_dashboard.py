import csv
import io
import unittest

from solar_dashboard import filter_sites, sites_to_csv, summarize_sites


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
