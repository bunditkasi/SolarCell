import csv
from datetime import datetime, timezone
import io
import unittest

from solar_dashboard import (
    current_cache,
    filter_sites,
    next_refresh_time,
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

    def test_refresh_cache_updates_shared_export_source(self):
        cache = refresh_cache(lambda: SITES, now_provider=lambda: datetime(2026, 5, 26, 4, 30, tzinfo=timezone.utc))
        rows = list(csv.DictReader(io.StringIO(sites_to_csv(current_cache()["sites"]))))

        self.assertIs(cache, current_cache())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["site_id"], "H1")
        self.assertEqual(cache["last_refresh_at"], "2026-05-26T04:30:00+00:00")
        self.assertEqual(cache["next_refresh_at"], "2026-05-26T12:00:00+07:00")
        self.assertEqual(cache["refresh_schedule"], ["08:00", "12:00", "16:00", "20:00"])

    def test_next_refresh_time_uses_four_daily_bangkok_slots(self):
        morning = datetime(2026, 5, 26, 7, 59, tzinfo=timezone.utc)
        evening = datetime(2026, 5, 26, 14, 0, tzinfo=timezone.utc)

        self.assertEqual(next_refresh_time(morning).isoformat(), "2026-05-26T16:00:00+07:00")
        self.assertEqual(next_refresh_time(evening).isoformat(), "2026-05-27T08:00:00+07:00")


if __name__ == "__main__":
    unittest.main()
