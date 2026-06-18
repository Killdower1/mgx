"""Smoke tests: data loading and DataProcessor."""

import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

import pandas as pd
import numpy as np
from data_processor import DataProcessor, normalize_outlet_name
from config import DATA_CSV_PATH, OUTLET_MAPPING_PATH


class DataProcessorSmokeTests(unittest.TestCase):
    """Smoke tests for DataProcessor — load data, mapping, filters."""

    @classmethod
    def setUpClass(cls):
        cls.dp = DataProcessor()

    # ==================== NORMALIZE ====================

    def test_normalize_outlet_name_strips_and_lowers(self):
        self.assertEqual(normalize_outlet_name("  Aeon Deltamas  "), "aeon deltamas")

    def test_normalize_outlet_name_collapses_spaces(self):
        self.assertEqual(normalize_outlet_name("Mall   Taman   Anggrek"), "mall taman anggrek")

    def test_normalize_outlet_name_handles_none(self):
        self.assertEqual(normalize_outlet_name(None), "")

    # ==================== OUTLET MAPPING ====================

    def test_load_outlet_mapping_returns_dataframe(self):
        mapping = self.dp.load_outlet_mapping()
        self.assertIsInstance(mapping, pd.DataFrame)

    def test_load_outlet_mapping_has_expected_columns(self):
        mapping = self.dp.load_outlet_mapping()
        mandatory = {"outlet_name"}
        if not mapping.empty:
            self.assertTrue(
                mandatory.issubset(mapping.columns),
                f"Missing columns: {mandatory - set(mapping.columns)}",
            )

    def test_load_outlet_mapping_has_data(self):
        mapping = self.dp.load_outlet_mapping()
        self.assertGreater(len(mapping), 0, "Outlet mapping kosong")

    # ==================== LOAD DATA ====================

    def test_load_data_returns_dataframe(self):
        df = self.dp.load_data()
        self.assertIsInstance(df, pd.DataFrame)

    def test_load_data_has_rows(self):
        df = self.dp.load_data()
        self.assertGreater(len(df), 0, "Data utama kosong")

    def test_load_data_has_mandatory_columns(self):
        df = self.dp.load_data()
        mandatory = {"outlet_name", "periode", "total_revenue",
                      "foto_qty", "outlet_status"}
        self.assertTrue(
            mandatory.issubset(df.columns),
            f"Missing columns: {mandatory - set(df.columns)}",
        )

    def test_load_data_has_positive_revenue(self):
        df = self.dp.load_data()
        self.assertGreater(df["total_revenue"].sum(), 0, "Total revenue must be > 0")

    def test_load_data_returns_unique_outlets(self):
        df = self.dp.load_data()
        self.assertGreater(df["outlet_name"].nunique(), 0)

    # ==================== APPLY OUTLET MAPPING ====================

    def test_apply_outlet_mapping_does_not_crash(self):
        raw = pd.read_csv(DATA_CSV_PATH)
        result = self.dp.apply_outlet_mapping(raw)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)

    def test_apply_outlet_mapping_preserves_row_count(self):
        raw = pd.read_csv(DATA_CSV_PATH)
        result = self.dp.apply_outlet_mapping(raw)
        self.assertEqual(len(result), len(raw))

    # ==================== METRICS ====================

    def test_calculate_metrics_returns_dict(self):
        df = self.dp.load_data()
        metrics = self.dp.calculate_metrics(df)
        self.assertIsInstance(metrics, dict)
        for key in ("total_revenue", "total_outlets", "avg_conversion", "total_photos"):
            self.assertIn(key, metrics)

    def test_calculate_metrics_values_are_positive(self):
        df = self.dp.load_data()
        metrics = self.dp.calculate_metrics(df)
        self.assertGreater(metrics["total_revenue"], 0)
        self.assertGreater(metrics["total_outlets"], 0)

    # ==================== TOP PERFORMERS ====================

    def test_get_top_performers_returns_n_rows(self):
        df = self.dp.load_data()
        top = self.dp.get_top_performers(df, n=5)
        self.assertEqual(len(top), 5)

    def test_get_top_performers_sorted_by_revenue_desc(self):
        df = self.dp.load_data()
        top = self.dp.get_top_performers(df, n=5)
        revs = top["total_revenue"].values
        self.assertTrue(all(revs[i] >= revs[i + 1] for i in range(len(revs) - 1)))

    # ==================== AGGREGATIONS ====================

    def test_aggregate_by_area_returns_dataframe(self):
        df = self.dp.load_data()
        agg = self.dp.aggregate_by_area(df)
        self.assertIsInstance(agg, pd.DataFrame)
        if not agg.empty:
            self.assertIn("total_revenue", agg.columns)

    def test_aggregate_by_kategori_returns_dataframe(self):
        df = self.dp.load_data()
        agg = self.dp.aggregate_by_kategori(df)
        self.assertIsInstance(agg, pd.DataFrame)
        if not agg.empty:
            self.assertIn("total_revenue", agg.columns)

    # ==================== FILTER ====================

    def test_filter_data_returns_subset(self):
        df = self.dp.load_data()
        if "area" in df.columns and df["area"].nunique() > 1:
            area = df["area"].iloc[0]
            filtered = self.dp.filter_data(df, area=area, kategori="Semua", tipe="Semua")
            self.assertGreater(len(filtered), 0)
            self.assertTrue((filtered["area"] == area).all())

    # ==================== EDGE: EMPTY ====================

    def test_calculate_metrics_empty_df(self):
        empty = pd.DataFrame()
        metrics = self.dp.calculate_metrics(empty)
        self.assertEqual(metrics["total_revenue"], 0)
        self.assertEqual(metrics["total_outlets"], 0)


if __name__ == "__main__":
    unittest.main()
