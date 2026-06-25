"""Cron sync script — incremental: only fetch since last sync date."""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ / 'nicegui_template'))

from services import difotoin_api_adapter as api

# Check if we already have data - if so, only fetch recent stuff
last = api.get_last_sync()
if last and last.get("success"):
    # Sync only last 7 days to keep it fast
    days_back = 7
else:
    # First time: full 12 months
    days_back = 365

print(f"Syncing last {days_back} days...")
ok, msg = api.run_sync(months_back=max(1, days_back // 30), per_page=50)
print(msg)
sys.exit(0 if ok else 1)
