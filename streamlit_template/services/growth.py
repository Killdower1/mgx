"""Services for perbandingan periode — growth metrics"""

import pandas as pd
import numpy as np


def calculate_growth_metrics(cur, prev):
    """Calculate growth metrics between two periods."""
    gm = {}
    cur_rev = float(cur['total_revenue'].sum())
    prev_rev = float(prev['total_revenue'].sum())
    gm['revenue_growth'] = ((cur_rev - prev_rev) / prev_rev * 100) if prev_rev else 0

    cur_photo = int(cur['foto_qty'].sum())
    prev_photo = int(prev['foto_qty'].sum())
    gm['photo_growth'] = ((cur_photo - prev_photo) / prev_photo * 100) if prev_photo else 0

    cur_conv = float(cur['conversion_rate'].mean())
    prev_conv = float(prev['conversion_rate'].mean())
    gm['conversion_change'] = cur_conv - prev_conv
    return gm
