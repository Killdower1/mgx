import re
import unittest
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")


class KemitraanPriceSourceTests(unittest.TestCase):
    def test_sharing_master_columns_do_not_expose_harga_mesin(self):
        match = re.search(r"SHARING_MASTER_COLUMNS\s*=\s*\[(.*?)\]", APP_SOURCE, re.S)
        self.assertIsNotNone(match, "Blok SHARING_MASTER_COLUMNS harus ada.")
        block = match.group(1)
        self.assertNotIn(
            '"harga_mesin"',
            block,
            "Harga mesin gak boleh nongol sebagai kolom input terpisah di sharing master.",
        )

    def test_data_editor_does_not_expose_harga_mesin_column(self):
        self.assertNotIn(
            '"harga_mesin": st.column_config.NumberColumn("Harga Mesin"',
            APP_SOURCE,
            "Editor masih nampilin kolom Harga Mesin padahal harus numpang ke Harga Beli Kemitraan.",
        )

    def test_internal_alias_keeps_harga_mesin_equal_to_harga_beli(self):
        self.assertRegex(
            APP_SOURCE,
            r'out\["harga_mesin"\]\s*=\s*out\["harga_beli_kemitraan"\]',
            "App harus bikin alias internal: harga_mesin = harga_beli_kemitraan.",
        )


if __name__ == "__main__":
    unittest.main()
