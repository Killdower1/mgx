import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import import_outlets_master as iom


class ImportOutletsMasterTests(unittest.TestCase):
    def test_initial_cost_populates_harga_beli_kemitraan_and_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "outlet-list.xlsx"
            outlet_mapping = tmp / "difotoin_outlet_mapping.csv"
            partnership = tmp / "outlet_partnerships.json"

            df = pd.DataFrame(
                [
                    {
                        "ID": 1,
                        "NAME": "Outlet A",
                        "BRANCH": "Jakarta",
                        "STATUS": "Active",
                        "TYPE": "Franchise",
                        "PARTNER_SHARE": 80,
                        "BROKER_SHARE": 10,
                        "MONTHLY_RENT": 5500000,
                        "MINIMUM_PAYMENT": 0,
                        "INITIAL_COST": 150000000,
                        "CREATED_AT": "2026-06-01 10:00:00",
                    },
                    {
                        "ID": 2,
                        "NAME": "Outlet B",
                        "BRANCH": "Bali",
                        "STATUS": "Active",
                        "TYPE": "Permanent",
                        "PARTNER_SHARE": 20,
                        "BROKER_SHARE": 0,
                        "MONTHLY_RENT": 3000000,
                        "MINIMUM_PAYMENT": 500000,
                        "INITIAL_COST": "-",
                        "CREATED_AT": "2026-06-02 11:00:00",
                    },
                ]
            )
            df.to_excel(source, index=False)

            with mock.patch.object(iom, "OUTLET_MAPPING_PATH", outlet_mapping), mock.patch.object(
                iom, "PARTNERSHIP_PATH", partnership
            ), mock.patch.object(sys, "argv", ["import_outlets_master.py", str(source)]):
                iom.main()

            out = pd.read_csv(outlet_mapping)
            self.assertEqual(len(out), 2)
            self.assertEqual(out.loc[0, "harga_beli_kemitraan"], 150000000.0)
            self.assertEqual(out.loc[0, "harga_mesin"], 150000000.0)
            self.assertTrue(pd.isna(out.loc[1, "harga_beli_kemitraan"]))
            self.assertTrue(pd.isna(out.loc[1, "harga_mesin"]))

            payload = json.loads(partnership.read_text(encoding="utf-8"))
            self.assertIn("outlets", payload)
            self.assertEqual(payload["outlets"], {})


if __name__ == "__main__":
    unittest.main()
