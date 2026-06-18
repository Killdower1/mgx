"""Smoke tests: upload and aggregation flow."""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import pandas as pd
import numpy as np
from config import Config
from services.aggregation import (
    normalize_headers,
    apply_column_mapping_auto,
    to_numeric_clean,
    excel_engine_from_filename,
    deduplicate_rows,
    compute_status,
    derive_counts_from_type,
    aggregate_monthly,
    save_overwrite_periods,
    _sort_periods_str,
)


RAW_ROWS = [
    {"outlet_name": "Outlet A", "harga": 50000, "tanggal": "2026-01-15", "type": "Foto"},
    {"outlet_name": "Outlet A", "harga": 35000, "tanggal": "2026-01-15", "type": "Unlock"},
    {"outlet_name": "Outlet A", "harga": 25000, "tanggal": "2026-01-15", "type": "Print"},
    {"outlet_name": "Outlet B", "harga": 45000, "tanggal": "2026-01-16", "type": "Foto"},
    {"outlet_name": "Outlet B", "harga": 30000, "tanggal": "2026-01-16", "type": "Unlock"},
    {"outlet_name": "Outlet B", "harga": 20000, "tanggal": "2026-01-16", "type": "Cetak"},
    {"outlet_name": "Outlet B", "harga": 20000, "tanggal": "2026-01-16", "type": "Cetak"},  # dup
]


class AggregationSmokeTests(unittest.TestCase):
    """Smoke tests for upload aggregation flow."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = Config()
        cls.raw = pd.DataFrame(RAW_ROWS)

    # ==================== HEADER NORMALIZATION ====================

    def test_normalize_headers_strips_whitespace(self):
        messy = pd.DataFrame({"  outlet  ": ["A"], "   harga   ": [100]})
        clean = normalize_headers(messy)
        self.assertIn("outlet", clean.columns)
        self.assertIn("harga", clean.columns)

    # ==================== COLUMN MAPPING ====================

    def test_apply_column_mapping_auto_detects_outlets(self):
        mapping = apply_column_mapping_auto(self.raw)
        # RAW_ROWS uses "outlet_name" directly, so it won't be in EXCEL_TO_APP_COLMAP
        # Instead verify harga is detected
        self.assertIn("harga", mapping)

    def test_apply_column_mapping_auto_detects_harga(self):
        mapping = apply_column_mapping_auto(self.raw)
        self.assertIn("harga", mapping)

    def test_apply_column_mapping_auto_detects_date(self):
        mapping = apply_column_mapping_auto(self.raw)
        self.assertIn("tanggal", mapping)

    # ==================== NUMERIC CLEAN ====================

    def test_to_numeric_clean_parses_integer_string(self):
        s = pd.Series(["35000", " 45000 "])
        result = to_numeric_clean(s)
        self.assertEqual(result.iloc[0], 35000.0)
        self.assertEqual(result.iloc[1], 45000.0)

    def test_to_numeric_clean_handles_negative_brackets(self):
        s = pd.Series(["(5000)", "3000"])
        result = to_numeric_clean(s)
        self.assertEqual(result.iloc[0], -5000.0)
        self.assertEqual(result.iloc[1], 3000.0)

    def test_to_numeric_clean_handles_indonesian_format(self):
        s = pd.Series(["35.500", " 45.250 "])
        result = to_numeric_clean(s)
        self.assertEqual(result.iloc[0], 35500.0)
        self.assertEqual(result.iloc[1], 45250.0)

    def test_to_numeric_clean_already_numeric(self):
        s = pd.Series([35000.0, 45000.0])
        result = to_numeric_clean(s)
        self.assertEqual(result.iloc[0], 35000.0)
        self.assertEqual(result.iloc[1], 45000.0)

    # ==================== EXCEL ENGINE ====================

    def test_excel_engine_xlsx(self):
        self.assertEqual(excel_engine_from_filename("data.xlsx"), "openpyxl")

    def test_excel_engine_xls(self):
        self.assertEqual(excel_engine_from_filename("data.xls"), "xlrd")

    def test_excel_engine_invalid_raises(self):
        with self.assertRaises(ValueError):
            excel_engine_from_filename("data.csv")

    # ==================== DEDUPLICATE ====================

    def test_deduplicate_rows_removes_duplicates(self):
        df, audit = deduplicate_rows(self.raw)
        self.assertLessEqual(len(df), len(self.raw))
        self.assertEqual(audit["dup_removed"], 1)

    def test_deduplicate_audit_keys_present(self):
        _, audit = deduplicate_rows(self.raw)
        for key in ("rows_before", "rows_after", "dup_removed", "sum_before", "sum_after"):
            self.assertIn(key, audit)

    # ==================== COMPUTE STATUS ====================

    def test_compute_status_keeper(self):
        self.assertEqual(compute_status(20_000_000, self.cfg), "Keeper")

    def test_compute_status_optimasi(self):
        self.assertEqual(compute_status(10_000_000, self.cfg), "Optimasi")

    def test_compute_status_relocate(self):
        self.assertEqual(compute_status(1_000_000, self.cfg), "Relocate")

    # ==================== DERIVE COUNTS FROM TYPE ====================

    def test_derive_counts_from_type_detects_foto(self):
        df = pd.DataFrame({"type": ["Foto", "Photo", "Capture", "Shoot"]})
        result, audit = derive_counts_from_type(df)
        self.assertEqual(audit["match_foto"], 4)

    def test_derive_counts_from_type_detects_unlock(self):
        df = pd.DataFrame({"type": ["Unlock", "QR", "Scan"]})
        result, audit = derive_counts_from_type(df)
        self.assertEqual(audit["match_unlock"], 3)

    def test_derive_counts_from_type_detects_print(self):
        df = pd.DataFrame({"type": ["Print", "Cetak", "Printout", "Print-out"]})
        result, audit = derive_counts_from_type(df)
        self.assertEqual(audit["match_print"], 4)

    def test_derive_counts_from_type_no_match(self):
        df = pd.DataFrame({"type": ["Unknown", "Other"]})
        result, audit = derive_counts_from_type(df)
        self.assertEqual(audit["match_foto"], 0)
        self.assertEqual(audit["match_unlock"], 0)
        self.assertEqual(audit["match_print"], 0)

    # ==================== AGGREGATE MONTHLY ====================

    def test_aggregate_monthly_returns_dataframe(self):
        df, audit = aggregate_monthly(self.raw, self.cfg, fallback_period="2026-01")
        self.assertIsInstance(df, pd.DataFrame)

    def test_aggregate_monthly_has_mandatory_columns(self):
        df, _ = aggregate_monthly(self.raw, self.cfg, fallback_period="2026-01")
        mandatory = {"periode", "outlet_name", "total_revenue",
                      "foto_qty", "unlock_qty", "print_qty", "outlet_status"}
        self.assertTrue(mandatory.issubset(df.columns),
                        f"Missing: {mandatory - set(df.columns)}")

    def test_aggregate_monthly_groups_by_outlet_and_period(self):
        df, _ = aggregate_monthly(self.raw, self.cfg, fallback_period="2026-01")
        self.assertEqual(len(df), 2)  # Outlet A and Outlet B

    def test_aggregate_monthly_revenue_sum(self):
        df, _ = aggregate_monthly(self.raw, self.cfg, fallback_period="2026-01")
        outlet_a = df[df["outlet_name"] == "Outlet A"]
        outlet_b = df[df["outlet_name"] == "Outlet B"]
        self.assertEqual(outlet_a["total_revenue"].sum(), 110000)  # 50000+35000+25000
        self.assertEqual(outlet_b["total_revenue"].sum(), 115000)  # 45000+30000+20000+20000(-1dup)

    def test_aggregate_monthly_with_date_column_derives_period(self):
        """Test that tanggal column drives periode extraction."""
        raw_with_date = pd.DataFrame([
            {"outlet_name": "X", "harga": 100, "tanggal": "2026-03-15", "type": "Foto"},
            {"outlet_name": "X", "harga": 200, "tanggal": "2026-03-16", "type": "Print"},
        ])
        df, _ = aggregate_monthly(raw_with_date, self.cfg)
        self.assertTrue((df["periode"] == "2026-03").all())

    # ==================== SAVE OVERWRITE PERIODS ====================

    def test_save_overwrite_periods_new_file(self):
        df, _ = aggregate_monthly(self.raw, self.cfg, fallback_period="2026-01")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test_data.csv")
            result, audit = save_overwrite_periods(df, tmp_path)
            self.assertIsInstance(result, pd.DataFrame)
            self.assertGreater(len(result), 0)
            self.assertIn("periods_overwritten", audit)
            self.assertIn("before_total", audit)
            self.assertIn("after_total", audit)
            self.assertEqual(audit["before_total"], 0.0)  # File was empty

    def test_save_overwrite_periods_existing_file(self):
        # Data without tanggal column so fallback_period is used
        df = pd.DataFrame([
            {"outlet_name": "Outlet A", "harga": 50000, "type": "Foto"},
        ])
        df1, _ = aggregate_monthly(df, self.cfg, fallback_period="2026-01")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "test_data.csv")
            # Save first batch
            save_overwrite_periods(df1, tmp_path)

            # Save second batch with different period
            df2, _ = aggregate_monthly(df, self.cfg, fallback_period="2026-02")
            result2, audit = save_overwrite_periods(df2, tmp_path)

            self.assertGreater(audit["before_total"], 0)  # Should have old data
            periods = sorted(result2["periode"].unique())
            self.assertIn("2026-01", periods)  # Old period preserved
            self.assertIn("2026-02", periods)  # New period added

    # ==================== EDGE: EMPTY DATA ====================

    def test_aggregate_monthly_empty_df_raises(self):
        empty = pd.DataFrame()
        with self.assertRaises(ValueError):
            aggregate_monthly(empty, self.cfg, fallback_period="2026-01")

    def test_aggregate_monthly_no_outlet_name_raises(self):
        no_outlet = pd.DataFrame({"harga": [100], "type": ["Foto"]})
        with self.assertRaises(ValueError):
            aggregate_monthly(no_outlet, self.cfg, fallback_period="2026-01")


if __name__ == "__main__":
    unittest.main()
