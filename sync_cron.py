#!/usr/bin/env python3
"""Cron sync script — called every 6 hours."""
import sys
from pathlib import Path

# Add nicegui_template to path
PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ / 'nicegui_template'))

from services import difotoin_api_adapter as api

ok, msg = api.run_sync(months_back=12)
print(msg)
import sys; sys.exit(0 if ok else 1)
