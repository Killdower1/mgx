"""Atomic hourly ERPNext Lead Kemitraan cache refresh; never replace with partial data."""
from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "streamlit_template/config/erpnext_config.json"
CACHE = ROOT / "streamlit_template/data/lead_kemitraan_cache.json"


def fetch_and_validate(session=None):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    session = session or requests.Session()
    url = cfg["url"].rstrip("/")
    headers = {"Authorization": "token {}:{}".format(cfg["api_key"], cfg["api_secret"])}
    count = session.get(url + "/api/method/frappe.client.get_count", headers=headers,
                        params={"doctype": "Lead Kemitraan"}, timeout=30)
    count.raise_for_status()
    expected = int(count.json()["message"])
    if expected <= 0:
        raise ValueError("ERP count is zero; refusing cache overwrite")
    records = []
    for offset in range(0, expected + 200, 200):
        response = session.get(url + "/api/resource/Lead%20Kemitraan", headers=headers,
                               params={"fields": '["*"]', "limit_page_length": 200,
                                       "limit_start": offset, "order_by": "creation desc"}, timeout=60)
        response.raise_for_status()
        batch = response.json()["data"]
        records.extend(batch)
        if len(batch) < 200:
            break
    ids = [x.get("name") for x in records]
    if len(records) != expected or len(set(ids)) != expected or any(not x for x in ids):
        raise ValueError("incomplete/duplicate ERP fetch: {} rows, {} unique; ERP count {}".format(
            len(records), len(set(ids)), expected))
    return {"last_sync": datetime.now(timezone.utc).isoformat(), "records": records}


def main():
    data = fetch_and_validate()
    fd, path = tempfile.mkstemp(prefix=".lead_kemitraan_", suffix=".json", dir=CACHE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(path, CACHE.stat().st_mode & 0o777 if CACHE.exists() else 0o640)
        os.replace(path, CACHE)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    print("Lead Kemitraan synced: {} rows; {}".format(len(data["records"]), data["last_sync"]))


if __name__ == "__main__":
    main()
