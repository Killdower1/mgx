"""Unit tests for services/erpnext module — aggregation + config, no live API calls."""

import sys
import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# Ensure project root is importable
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from config import (
    CONFIG_DIR, ERPNEXT_CONFIG_PATH,
    load_erpnext_config, save_erpnext_config,
)
from services.erpnext import (
    LEAD_FIELDS,
    FIELD_DISPLAY_NAMES,
    aggregate_lead_data,
    aggregate_team_performance,
)


class ERPNextConfigTests(unittest.TestCase):
    """Test ERPNext config load/save roundtrip."""

    def setUp(self):
        self.backup = load_erpnext_config()

    def tearDown(self):
        save_erpnext_config(self.backup)

    def test_load_empty_when_no_file(self):
        """Returns empty dict when file doesn't exist."""
        if ERPNEXT_CONFIG_PATH.exists():
            ERPNEXT_CONFIG_PATH.unlink()
        cfg = load_erpnext_config()
        self.assertIsInstance(cfg, dict)
        self.assertEqual(cfg, {})

    def test_save_and_load_roundtrip(self):
        """Save then load returns identical data."""
        test_data = {
            "url": "https://erp.test.id",
            "api_key": "test_key_123",
            "api_secret": "test_secret_456",
        }
        save_erpnext_config(test_data)
        loaded = load_erpnext_config()
        self.assertEqual(loaded, test_data)

    def test_save_updates_existing(self):
        """Saving new data replaces old data."""
        save_erpnext_config({"url": "https://old.url"})
        save_erpnext_config({"url": "https://new.url", "api_key": "k"})
        loaded = load_erpnext_config()
        self.assertEqual(loaded["url"], "https://new.url")
        self.assertEqual(loaded["api_key"], "k")


class AggregateLeadDataTests(unittest.TestCase):
    """Test aggregate_lead_data with sample DataFrames."""

    def setUp(self):
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=10)
        last_month = now - timedelta(days=40)

        self.sample_data = pd.DataFrame([
            {
                "name": "LEAD-001",
                "lead_name": "John Doe",
                "status": "Open",
                "city": "Jakarta",
                "source": "Website",
                "lead_owner": "Alice",
                "custom_kategori_tempat": "Mall",
                "creation": now,
            },
            {
                "name": "LEAD-002",
                "lead_name": "Jane Smith",
                "status": "Contact",
                "city": "Bandung",
                "source": "Referral",
                "lead_owner": "Bob",
                "custom_kategori_tempat": "Restoran",
                "creation": yesterday,
            },
            {
                "name": "LEAD-003",
                "lead_name": "Bob Wilson",
                "status": "Won",
                "city": "Jakarta",
                "source": "Website",
                "lead_owner": "Alice",
                "custom_kategori_tempat": "Mall",
                "creation": last_week,
            },
            {
                "name": "LEAD-004",
                "lead_name": "Alice Brown",
                "status": "Lost",
                "city": "Surabaya",
                "source": "Instagram",
                "lead_owner": "Charlie",
                "custom_kategori_tempat": "Hotel",
                "creation": last_month,
            },
            {
                "name": "LEAD-005",
                "lead_name": "Charlie Davis",
                "status": "Open",
                "city": "Jakarta",
                "source": "Website",
                "lead_owner": "Bob",
                "custom_kategori_tempat": "Mall",
                "creation": now,
            },
        ])

        self.empty_df = pd.DataFrame()

    def test_aggregate_with_data(self):
        """Returns correct counts and distributions."""
        agg = aggregate_lead_data(self.sample_data)

        self.assertEqual(agg["total_all"], 5)

        # Time-based: today count >= 2 (2 records with creation=now)
        self.assertGreaterEqual(agg["total_today"], 2)
        # This week count >= 2 (depends on day of week the test runs)
        self.assertGreaterEqual(agg["total_this_week"], 2)
        # This month count >= 4 (4 within last 30 days)
        self.assertGreaterEqual(agg["total_this_month"], 4)

        # Status distribution
        self.assertIn("status_distribution", agg)
        self.assertEqual(agg["status_distribution"].get("Open", 0), 2)
        self.assertEqual(agg["status_distribution"].get("Won", 0), 1)
        self.assertEqual(agg["status_distribution"].get("Lost", 0), 1)

        # City top 10
        self.assertEqual(len(agg["city_top10"]), 3)
        jakarta_count = next(
            (cnt for city, cnt in agg["city_top10"] if city == "Jakarta"), 0
        )
        self.assertEqual(jakarta_count, 3)

        # Kategori tempat
        self.assertIn("kategori_tempat", agg)
        self.assertEqual(agg["kategori_tempat"].get("Mall", 0), 3)

        # Source distribution
        self.assertIn("source_distribution", agg)
        self.assertEqual(agg["source_distribution"].get("Website", 0), 3)

    def test_aggregate_empty_df(self):
        """Returns zeroed stats for empty DataFrame."""
        agg = aggregate_lead_data(self.empty_df)
        self.assertEqual(agg["total_all"], 0)
        self.assertEqual(agg["total_today"], 0)
        self.assertEqual(agg["total_this_week"], 0)
        self.assertEqual(agg["total_this_month"], 0)
        self.assertEqual(agg["status_distribution"], {})
        self.assertEqual(agg["city_top10"], [])
        self.assertEqual(agg["kategori_tempat"], {})
        self.assertEqual(agg["source_distribution"], {})

    def test_aggregate_missing_columns(self):
        """Gracefully handles missing columns."""
        minimal_df = pd.DataFrame([
            {"name": "L-001", "lead_name": "Test"},
            {"name": "L-002", "lead_name": "Test 2"},
        ])
        agg = aggregate_lead_data(minimal_df)
        self.assertEqual(agg["total_all"], 2)
        # Missing columns should not cause error
        self.assertEqual(agg["total_today"], 0)
        self.assertEqual(agg["status_distribution"], {})
        self.assertEqual(agg["kategori_tempat"], {})

    def test_aggregate_nan_values(self):
        """Handles NaN values in categorical columns."""
        df_nan = self.sample_data.copy()
        df_nan.loc[0, "city"] = None
        df_nan.loc[1, "status"] = None

        agg = aggregate_lead_data(df_nan)
        # Should not crash — NaN should be filled as 'Unknown'
        self.assertIn("status_distribution", agg)
        self.assertIn("city_top10", agg)


class AggregateTeamPerformanceTests(unittest.TestCase):
    """Test aggregate_team_performance with sample DataFrames."""

    def setUp(self):
        self.sample_data = pd.DataFrame([
            {"lead_owner": "Alice", "status": "Open"},
            {"lead_owner": "Alice", "status": "Contact"},
            {"lead_owner": "Alice", "status": "Won"},
            {"lead_owner": "Bob", "status": "Open"},
            {"lead_owner": "Bob", "status": "Lost"},
            {"lead_owner": "Charlie", "status": "Won"},
            {"lead_owner": "Charlie", "status": "Lost"},
            {"lead_owner": "Charlie", "status": "Contact"},
            {"lead_owner": "Charlie", "status": "Open"},
        ])
        self.empty_df = pd.DataFrame()

    def test_team_performance_counts(self):
        """Verifies correct counts per owner."""
        perf = aggregate_team_performance(self.sample_data)

        self.assertEqual(len(perf), 3)  # 3 unique owners

        alice = perf[perf["lead_owner"] == "Alice"]
        self.assertEqual(alice["Total"].values[0], 3)
        # Alice: Open + Contact both count as "Open" (in pipeline)
        self.assertEqual(alice["Open"].values[0], 2)
        self.assertEqual(alice["Contacted"].values[0], 1)  # Contact
        self.assertEqual(alice["Converted"].values[0], 1)  # Won
        self.assertEqual(alice["Lost"].values[0], 0)

        bob = perf[perf["lead_owner"] == "Bob"]
        self.assertEqual(bob["Total"].values[0], 2)
        self.assertEqual(bob["Open"].values[0], 1)
        self.assertEqual(bob["Contacted"].values[0], 0)
        self.assertEqual(bob["Converted"].values[0], 0)
        self.assertEqual(bob["Lost"].values[0], 1)

        charlie = perf[perf["lead_owner"] == "Charlie"]
        self.assertEqual(charlie["Total"].values[0], 4)
        self.assertEqual(charlie["Open"].values[0], 2)  # Open + Contact
        self.assertEqual(charlie["Contacted"].values[0], 1)  # Contact
        self.assertEqual(charlie["Converted"].values[0], 1)  # Won
        self.assertEqual(charlie["Lost"].values[0], 1)

    def test_team_performance_empty(self):
        """Returns empty DataFrame for empty input."""
        perf = aggregate_team_performance(self.empty_df)
        self.assertTrue(perf.empty)

    def test_team_performance_missing_column(self):
        """Returns empty when lead_owner column missing."""
        df_no_owner = pd.DataFrame([{"status": "Open"}])
        perf = aggregate_team_performance(df_no_owner)
        self.assertTrue(perf.empty)

    def test_team_performance_sorting(self):
        """Results sorted by Total descending."""
        perf = aggregate_team_performance(self.sample_data)
        totals = perf["Total"].values
        for i in range(len(totals) - 1):
            self.assertGreaterEqual(totals[i], totals[i + 1])


class LeadFieldsValidationTests(unittest.TestCase):
    """Validate LEAD_FIELDS and FIELD_DISPLAY_NAMES consistency."""

    def test_lead_fields_contains_core_fields(self):
        """Core required fields are present."""
        required = {"name", "lead_name", "status", "city", "source",
                     "lead_owner", "creation", "modified"}
        self.assertTrue(
            required.issubset(set(LEAD_FIELDS)),
            f"Missing core fields: {required - set(LEAD_FIELDS)}",
        )

    def test_lead_fields_contains_custom_fields(self):
        """Custom fields used in aggregations are present."""
        custom_required = {"custom_kategori_tempat", "custom_tipe_tempat",
                           "custom_tahu_difotoin_dari"}
        self.assertTrue(
            custom_required.issubset(set(LEAD_FIELDS)),
            f"Missing custom fields: {custom_required - set(LEAD_FIELDS)}",
        )

    def test_field_display_names_covers_core_fields(self):
        """Core fields have display name mappings."""
        core = {"name", "lead_name", "status", "city", "source",
                "lead_owner", "creation"}
        unmapped = core - set(FIELD_DISPLAY_NAMES.keys())
        self.assertEqual(
            unmapped, set(),
            f"Core fields without display names: {unmapped}",
        )

    def test_no_duplicate_field_names(self):
        """LEAD_FIELDS has no duplicates."""
        self.assertEqual(len(LEAD_FIELDS), len(set(LEAD_FIELDS)),
                         "LEAD_FIELDS contains duplicate entries")


if __name__ == "__main__":
    unittest.main()
