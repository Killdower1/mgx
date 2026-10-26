"""Proyeksi omzet akhir bulan dengan Prophet (Meta) — dijalankan di venv terpisah.

Input : streamlit_template/data/api_cache/daily_summary.json (harian per outlet)
Output: streamlit_template/data/api_cache/forecast_monthly.json

Model:
- Prophet harian (weekly + yearly seasonality, multiplicative)
- holidays Indonesia (python-holidays) + lower/upper window 1 hari supaya
  efek long weekend ikut tertangkap
- backtest 14 hari terakhir (MAPE) supaya akurasi bisa dinyatakan, bukan diklaim

Jalankan: /var/www/difotoin-dashboard/.venv-forecast/bin/python scripts/forecast_prophet.py
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"
OUT = ROOT / "streamlit_template" / "data" / "api_cache" / "forecast_monthly.json"
JUNK = ("test", "coba", "dummy", "sample")


def _load_daily() -> pd.DataFrame:
    rows = json.loads(DAILY.read_text())
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
    df = df[~df["outlet_name"].str.lower().str.startswith(JUNK)]
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)
    agg = df.groupby("date", as_index=False)["revenue"].sum()
    agg = agg.sort_values("date")
    return agg


def _holidays(start_year: int, end_year: int) -> pd.DataFrame:
    import holidays as hol

    years = list(range(start_year, end_year + 1))
    id_hol = hol.country_holidays("ID", years=years)
    rows = []
    for d, name in id_hol.items():
        rows.append({
            "ds": pd.Timestamp(d),
            "holiday": str(name)[:60],
            "lower_window": -1,
            "upper_window": 1,
        })
    return pd.DataFrame(rows)


def _fit(train: pd.DataFrame, holidays: pd.DataFrame, horizon_days: int, interval: float = 0.8):
    import logging

    from prophet import Prophet

    logging.getLogger("prophet").setLevel(logging.ERROR)
    logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

    model = Prophet(
        holidays=holidays if not holidays.empty else None,
        seasonality_mode="multiplicative",
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=interval,
        changepoint_prior_scale=0.05,
    )
    model.fit(train[["ds", "y"]])
    future = model.make_future_dataframe(periods=horizon_days, freq="D")
    fc = model.predict(future)
    return model, fc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--backtest-days", type=int, default=14)
    args = ap.parse_args()

    daily = _load_daily()
    if daily.empty or len(daily) < 90:
        print("SKIP: data harian < 90 hari")
        return 1

    ds = daily.rename(columns={"date": "ds", "revenue": "y"})
    ds["ds"] = pd.to_datetime(ds["ds"]).dt.tz_localize(None)

    today = pd.Timestamp(date.today())
    month_start = today.replace(day=1)
    next_month = (month_start + pd.offsets.MonthEnd(1)).normalize()
    horizon = max(1, (next_month - today).days)

    holidays = _holidays(ds["ds"].dt.year.min(), next_month.year)

    # ── backtest 14 hari terakhir ─────────────────────────────────────────
    bt_days = int(args.backtest_days)
    train_bt = ds[ds["ds"] <= (today - pd.Timedelta(days=bt_days))]
    mape = None
    if len(train_bt) >= 120:
        _, fc_bt = _fit(train_bt, holidays, horizon_days=bt_days)
        actual = ds[(ds["ds"] > train_bt["ds"].max()) & (ds["ds"] <= today)]
        pred = fc_bt[fc_bt["ds"].isin(actual["ds"])]
        merged = actual.merge(pred[["ds", "yhat"]], on="ds", how="inner")
        merged = merged[merged["y"] > 0]
        if len(merged) >= 7:
            mape = float(((merged["yhat"] - merged["y"]).abs() / merged["y"]).mean() * 100.0)

    # ── model final ───────────────────────────────────────────────────────
    model, fc = _fit(ds, holidays, horizon_days=horizon + 1)
    fc = fc[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

    actual_mtd = ds[(ds["ds"] >= month_start) & (ds["ds"] <= today)]
    mtd_actual = float(actual_mtd["y"].sum())

    rest = fc[(fc["ds"] > today) & (fc["ds"] <= next_month)]
    proj_rest = float(rest["yhat"].sum())
    proj_rest_lo = float(rest["yhat_lower"].sum())
    proj_rest_hi = float(rest["yhat_upper"].sum())

    # baseline pembanding: bulan lalu (penuh & pace hari yang sama)
    prev_month_start = (month_start - pd.Timedelta(days=1)).replace(day=1)
    prev_month_end = month_start - pd.Timedelta(days=1)
    prev_full = float(ds[(ds["ds"] >= prev_month_start) & (ds["ds"] <= prev_month_end)]["y"].sum())
    prev_same_days = min(today.day, prev_month_end.day)
    prev_pace_end = prev_month_start + pd.Timedelta(days=prev_same_days - 1)
    prev_pace = float(ds[(ds["ds"] >= prev_month_start) & (ds["ds"] <= prev_pace_end)]["y"].sum())

    # hari libur/long weekend yang tersisa
    hol_rows = []
    if not holidays.empty:
        h = holidays[(holidays["ds"] > today) & (holidays["ds"] <= next_month)]
        for _, r in h.iterrows():
            hol_rows.append({"date": r["ds"].strftime("%Y-%m-%d"), "name": r["holiday"]})

    history = ds.tail(60)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "month": month_start.strftime("%Y-%m"),
        "today": today.strftime("%Y-%m-%d"),
        "days_in_month": int(next_month.day),
        "day_of_month": int(today.day),
        "days_left": int(horizon),
        "mtd_actual": round(mtd_actual),
        "projected_remaining": round(proj_rest),
        "projected_total": round(mtd_actual + proj_rest),
        "projected_lower": round(mtd_actual + proj_rest_lo),
        "projected_upper": round(mtd_actual + proj_rest_hi),
        "prev_month_total": round(prev_full),
        "prev_month_pace": round(prev_pace),
        "prev_same_days": prev_same_days,
        "mape_14d": round(mape, 2) if mape is not None else None,
        "backtest_days": bt_days,
        "history": [
            {"date": r["ds"].strftime("%Y-%m-%d"), "y": round(float(r["y"]))}
            for _, r in history.iterrows()
        ],
        "forecast": [
            {
                "date": r["ds"].strftime("%Y-%m-%d"),
                "yhat": round(float(r["yhat"])),
                "lower": round(float(r["yhat_lower"])),
                "upper": round(float(r["yhat_upper"])),
            }
            for _, r in fc[(fc["ds"] >= month_start - pd.Timedelta(days=30))].iterrows()
        ],
        "holidays_remaining": hol_rows,
        "engine": "prophet",
    }

    out = Path(args.out)
    out.write_text(json.dumps(payload, ensure_ascii=False))
    print("OK", out, "projected_total", payload["projected_total"], "mape", payload["mape_14d"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
