"""Smoke tests: config loading, paths, and master data."""

import sys
import json
import unittest
from pathlib import Path

# Ensure project root is importable
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from config import (
    BASE_DIR, DATA_DIR, CONFIG_DIR,
    DATA_CSV_PATH, OUTLET_MAPPING_PATH, OUTLET_PARTNERSHIPS_PATH,
    USERS_PATH, AUTH_SESSIONS_PATH, DELETED_OUTLETS_PATH,
    MASTER_DATA_PATH, UPLOAD_STAGING_DIR,
    Config, load_master_data, save_master_data,
)


class ConfigSmokeTests(unittest.TestCase):
    """Smoke tests — verify config module loads and core paths work."""

    # ==================== PATH SANITY ====================

    def test_base_dir_is_inside_project(self):
        self.assertTrue(str(BASE_DIR).endswith("streamlit_template"),
                        f"BASE_DIR = {BASE_DIR}")

    def test_data_csv_path_points_to_existing_file(self):
        self.assertTrue(
            DATA_CSV_PATH.exists(),
            f"DATA_CSV_PATH tidak ditemukan: {DATA_CSV_PATH}",
        )

    def test_outlet_mapping_path_points_to_existing_file(self):
        self.assertTrue(
            OUTLET_MAPPING_PATH.exists(),
            f"OUTLET_MAPPING_PATH tidak ditemukan: {OUTLET_MAPPING_PATH}",
        )

    def test_master_data_path_inside_data_dir(self):
        self.assertTrue(str(MASTER_DATA_PATH).startswith(str(DATA_DIR)))

    def test_config_dir_is_subdir_of_base(self):
        self.assertTrue(str(CONFIG_DIR).startswith(str(BASE_DIR)))

    # ==================== CONFIG CLASS ====================

    def test_config_creates_default_and_reads_thresholds(self):
        cfg = Config()
        keep = cfg.get_threshold("keeper_minimum")
        opt = cfg.get_threshold("optimasi_minimum")
        self.assertIsInstance(keep, (int, float))
        self.assertIsInstance(opt, (int, float))
        self.assertGreater(keep, opt,
                           "Keeper threshold harus lebih besar dari Optimasi")

    def test_config_set_and_get_threshold(self):
        cfg = Config()
        cfg.set_threshold("keeper_minimum", 99_999_999)
        self.assertEqual(cfg.get_threshold("keeper_minimum"), 99_999_999)

    def test_config_format_currency_idr(self):
        cfg = Config()
        result = cfg.format_currency(1_500_000)
        self.assertIn("Rp", result)
        self.assertTrue(
            "1.500" in result or "1,500" in result,
            f"Expected '1.500' or '1,500' in format: {result}",
        )

    def test_config_save_and_reload(self):
        cfg = Config()
        old = cfg.get_threshold("keeper_minimum")
        cfg.set_threshold("keeper_minimum", 88_888_888)
        cfg.save_config()
        cfg2 = Config()
        self.assertEqual(cfg2.get_threshold("keeper_minimum"), 88_888_888)
        # Restore
        cfg2.set_threshold("keeper_minimum", old)
        cfg2.save_config()

    # ==================== MASTER DATA ====================

    def test_load_master_data_returns_dict_with_expected_keys(self):
        data = load_master_data()
        self.assertIsInstance(data, dict)
        for key in ("areas", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"):
            self.assertIn(key, data)
            self.assertIsInstance(data[key], list)

    def test_save_and_load_master_data_roundtrip(self):
        original = load_master_data()
        test_data = {
            "areas": ["Test Area"],
            "kategori_tempat": ["Test Kategori"],
            "sub_kategori_tempat": ["Test Sub"],
            "tipe_tempat": ["Test Tipe"],
        }
        save_master_data(test_data)
        loaded = load_master_data()
        self.assertEqual(loaded, test_data)
        # Restore
        save_master_data(original)

    # ==================== CSV STRUCTURE ====================

    def test_data_csv_has_expected_columns(self):
        import pandas as pd
        df = pd.read_csv(DATA_CSV_PATH)
        mandatory = {"outlet_name", "periode", "total_revenue",
                      "foto_qty", "unlock_qty", "print_qty", "outlet_status"}
        self.assertTrue(
            mandatory.issubset(df.columns),
            f"Missing columns: {mandatory - set(df.columns)}",
        )

    def test_data_csv_is_not_empty(self):
        import pandas as pd
        df = pd.read_csv(DATA_CSV_PATH)
        self.assertGreater(len(df), 0, "Data CSV kosong")


if __name__ == "__main__":
    unittest.main()
