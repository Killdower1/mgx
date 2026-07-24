#!/usr/bin/env python3
"""
Audit raw_by_month/ data quality.
Generates audit_report.json with per-month breakdown.
"""
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

RAW_DIR = Path("/var/www/difotoin-dashboard/streamlit_template/data/api_cache/raw_by_month")
REPORT_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/data/api_cache/audit_report.json")

def audit_month(path: Path) -> dict:
    with open(path) as f:
        txns = json.load(f)
    
    stats = {
        "total_records": len(txns),
        "unique_ids": len(set(str(t.get("id", "")) for t in txns)),
        "duplicate_ids": len(txns) - len(set(str(t.get("id", "")) for t in txns)),
        "by_type": defaultdict(int),
        "by_amount": {
            "positive": 0,
            "zero": 0,
            "null": 0,
        },
        "revenue": 0.0,
        "sessions": 0,
        "unlocks": 0,
        "prints": 0,
        "with_parent_id": 0,
    }
    
    for t in txns:
        tx_type_raw = t.get("type")
        tx_type = tx_type_raw or "session"
        stats["by_type"][tx_type] += 1
        
        amt = t.get("processed_gross_amount")
        if amt is None:
            stats["by_amount"]["null"] += 1
        elif amt > 0:
            stats["by_amount"]["positive"] += 1
            stats["revenue"] += float(amt)
        else:
            stats["by_amount"]["zero"] += 1
        
        if t.get("parent_id"):
            stats["with_parent_id"] += 1
        
        details = t.get("details", []) or []
        has_capture = any((d.get("capture_qty") or 0) > 0 for d in details)
        
        if tx_type_raw in (None, "") and has_capture:
            stats["sessions"] += 1
        elif tx_type == "unlock-photo":
            stats["unlocks"] += 1
        elif tx_type == "print":
            stats["prints"] += 1
    
    stats["by_type"] = dict(stats["by_type"])
    return stats

def main():
    report = {
        "generated_at": datetime.now().isoformat(),
        "months": {},
        "summary": {
            "total_records": 0,
            "total_revenue": 0.0,
            "total_sessions": 0,
            "total_unlocks": 0,
            "total_prints": 0,
        }
    }
    
    for f in sorted(RAW_DIR.glob("*.json")):
        period = f.stem
        print(f"Auditing {period}...")
        report["months"][period] = audit_month(f)
        m = report["months"][period]
        report["summary"]["total_records"] += m["total_records"]
        report["summary"]["total_revenue"] += m["revenue"]
        report["summary"]["total_sessions"] += m["sessions"]
        report["summary"]["total_unlocks"] += m["unlocks"]
        report["summary"]["total_prints"] += m["prints"]
    
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to {REPORT_PATH}")
    print(f"Grand total: {report['summary']['total_records']:,} records")
    print(f"Grand revenue: Rp {report['summary']['total_revenue']:,.0f}")
    print(f"Grand sessions: {report['summary']['total_sessions']:,}")
    print(f"Grand unlocks: {report['summary']['total_unlocks']:,}")
    print(f"Grand prints: {report['summary']['total_prints']:,}")
    conv = report['summary']['total_unlocks'] / report['summary']['total_sessions'] * 100 if report['summary']['total_sessions'] > 0 else 0
    print(f"Grand conversion rate: {conv:.2f}%")

if __name__ == "__main__":
    main()
