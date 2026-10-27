"""Daily, idempotent suggestions from the freshly synced outlet API cache."""
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nicegui_template'))
from services import mitra_portfolio as portfolio  # noqa: E402

OUTLETS = ROOT / 'streamlit_template/data/api_cache/outlets.json'


def run():
    if not OUTLETS.exists() or time.time() - OUTLETS.stat().st_mtime > 3 * 3600:
        raise RuntimeError('Outlet API cache missing/stale; refusing discovery')
    rows = json.loads(OUTLETS.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError('Outlet API cache empty/invalid; refusing discovery')
    doc, counts = portfolio.discover_outlets(portfolio.load(), rows, date.today().isoformat())
    if sum(counts.values()):
        portfolio.save(doc)
    print('Mitra outlet discovery:', counts, 'unassigned total:', len(doc.get('unassigned_outlets', [])))
    return counts


if __name__ == '__main__':
    run()
