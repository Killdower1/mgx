import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTLET_MAPPING_PATH = BASE_DIR / "data" / "difotoin_outlet_mapping.csv"
PARTNERSHIP_PATH = BASE_DIR / "data" / "outlet_partnerships.json"

def to_number(value):
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_numeric(str(value).replace(",", ""), errors="coerce")
        return None if pd.isna(parsed) else float(parsed)
    except Exception:
        return None

def to_pct(value):
    number = to_number(value)
    if number is None:
        return None
    return number / 100 if number > 1 else number

def main():
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python import_outlets_master.py <outlet-list.xlsx>")
        raise SystemExit(1)

    source = Path(sys.argv[1])
    df = pd.read_excel(source)
    rows = []
    seen = set()

    for _, row in df.iterrows():
        name = str(row.get("NAME") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        partner_share = to_pct(row.get("PARTNER_SHARE"))
        broker_share = to_pct(row.get("BROKER_SHARE")) or 0
        sharing = None if partner_share is None else max(0, min(1, 1 - partner_share - broker_share))
        venue_type = str(row.get("TYPE") or "").strip()
        initial_cost = to_number(row.get("INITIAL_COST"))

        rows.append({
            "outlet_name": name,
            "outlet_id": str(row.get("ID") or "").strip(),
            "area": str(row.get("BRANCH") or "").strip(),
            "kategori_tempat": venue_type,
            "sub_kategori_tempat": "",
            "tipe_tempat": venue_type,
            "outlet_status_master": str(row.get("STATUS") or "").strip(),
            "partner_share": partner_share,
            "broker_share": broker_share if broker_share else None,
            "sharing_bagi_hasil": sharing,
            "ownership_status": "",
            "harga_beli_kemitraan": initial_cost,
            "harga_mesin": initial_cost,
            "monthly_rent": to_number(row.get("MONTHLY_RENT")),
            "minimum_payment": to_number(row.get("MINIMUM_PAYMENT")),
            "created_at": row.get("CREATED_AT") if pd.notna(row.get("CREATED_AT")) else "",
        })

    out = pd.DataFrame(rows)
    OUTLET_MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTLET_MAPPING_PATH, index=False)

    if not PARTNERSHIP_PATH.exists():
        PARTNERSHIP_PATH.write_text(json.dumps({
            "_instructions": "Key boleh nama outlet atau outlet_id. ownership_status: kemitraan | milik sendiri. harga_beli_kemitraan dalam Rupiah, boleh null.",
            "outlets": {},
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {len(out)} outlets to {OUTLET_MAPPING_PATH}")

if __name__ == "__main__":
    main()
