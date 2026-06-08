import csv
from datetime import datetime, timezone
import io
import unittest

from solar_dashboard import (
    current_cache,
    build_report,
    filter_sites,
    refresh_cache,
    sites_to_csv,
    summarize_sites,
)


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
    {
        "source": "atmoce",
        "site_id": "A2",
        "site_name": "Offline Branch",
        "status": "Offline",
        "country": "Thailand",
        "capacity_kw": 10.0,
        "current_power_kw": 0.0,
        "today_energy_kwh": 0.0,
        "month_energy_kwh": 12.5,
        "lifetime_energy_kwh": 120.0,
        "collector_status": "ok",
    },
]


class DashboardAggregationTest(unittest.TestCase):
    def test_summarize_sites_totals_and_source_health(self):
        summary = summarize_sites(SITES)

        self.assertEqual(summary["site_count"], 3)
        self.assertEqual(summary["status_counts"]["normal"], 2)
        self.assertEqual(summary["status_counts"]["faulty"], 0)
        self.assertEqual(summary["status_counts"]["offline"], 1)
        self.assertEqual(summary["total_capacity_kw"], 83.4)
        self.assertEqual(summary["current_power_kw"], 50.0)
        self.assertEqual(summary["today_energy_kwh"], 259.0)
        self.assertEqual(summary["source_health"]["atmoce"], "ok")
        self.assertEqual(summary["source_health"]["huawei"], "degraded")

    def test_filter_sites_by_source_status_and_search(self):
        result = filter_sites(SITES, source="huawei", status="normal", query="pckn")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["site_id"], "H1")

    def test_huawei_health_state_mapping(self):
        sites = [
            {"source": "huawei", "status": "health_state_3"},
            {"source": "huawei", "status": "health_state_1"},
            {"source": "huawei", "status": "health_state_2"},
        ]

        summary = summarize_sites(sites)

        self.assertEqual(summary["status_counts"]["normal"], 1)
        self.assertEqual(summary["status_counts"]["offline"], 1)
        self.assertEqual(summary["status_counts"]["faulty"], 1)

    def test_sites_to_csv_contains_common_columns(self):
        text = sites_to_csv(SITES)
        rows = list(csv.DictReader(io.StringIO(text)))

        self.assertEqual(rows[0]["source"], "atmoce")
        self.assertEqual(rows[1]["site_name"], "PCKN Mr. DIY")

    def test_refresh_cache_updates_shared_export_source(self):
        cache = refresh_cache(lambda: SITES, now_provider=lambda: datetime(2026, 5, 26, 4, 30, tzinfo=timezone.utc))
        rows = list(csv.DictReader(io.StringIO(sites_to_csv(current_cache()["sites"]))))

        self.assertIs(cache, current_cache())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["site_id"], "H1")
        self.assertEqual(cache["last_refresh_at"], "2026-05-26T04:30:00+00:00")
        self.assertIsNone(cache["next_refresh_at"])
        self.assertEqual(cache["refresh_schedule"], [])

    def test_build_report_groups_sources_and_exceptions(self):
        report = build_report(SITES)

        self.assertEqual(report["source_rows"][0]["source"], "atmoce")
        self.assertEqual(report["source_rows"][0]["site_count"], 2)
        self.assertEqual(report["source_rows"][0]["offline_count"], 1)
        self.assertEqual(report["source_rows"][0]["today_energy_kwh"], 166.6)
        self.assertEqual(report["source_rows"][1]["source"], "huawei")
        self.assertEqual(report["source_rows"][1]["site_count"], 1)
        self.assertEqual(len(report["exception_rows"]), 1)
        self.assertEqual(report["exception_rows"][0]["site_name"], "Offline Branch")

    def test_build_report_includes_site_performance_and_source_health_detail(self):
        report = build_report(SITES)

        self.assertEqual(report["performance_rows"][0]["site_name"], "PKON")
        self.assertEqual(report["performance_rows"][0]["yield_per_kwp"], 3.883)
        self.assertEqual(report["performance_rows"][0]["current_load_percent"], 69.93)
        self.assertEqual(report["performance_rows"][-1]["site_name"], "Offline Branch")
        self.assertEqual(report["health_rows"][0]["source"], "atmoce")
        self.assertEqual(report["health_rows"][0]["collector_status"], "ok")
        self.assertEqual(report["health_rows"][1]["source"], "huawei")
        self.assertEqual(report["health_rows"][1]["collector_status"], "degraded")


if __name__ == "__main__":
    unittest.main()
