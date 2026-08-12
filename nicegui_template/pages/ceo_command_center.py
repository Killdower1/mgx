"""CEO Command Center — compact, evidence-based executive control tower."""

import calendar
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from nicegui import ui

from services.dashboard_adapter import get_adapter


ROOT = Path(__file__).resolve().parents[2]
LEAD_CACHE = ROOT / "streamlit_template" / "data" / "lead_partnership_cache.json"
DAILY_SUMMARY_CACHE = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"
PROBLEM_FILES = {
    "summary": (Path("/var/www/difotoin-dashboard/problem_booth_summary.json"), ROOT / "problem_booth_summary.json"),
    "monthly": (Path("/var/www/difotoin-dashboard/problem_booth_monthly.json"), ROOT / "problem_booth_monthly.json"),
}
CARD = "background:#1e1e2e;border:1px solid #313244;border-radius:12px;padding:16px;"
COLORS = {"green": "#22c55e", "yellow": "#f59e0b", "red": "#ef4444", "gray": "#94a3b8"}


def _safe_periods(values) -> list[str]:
    """Chronologically sort period labels, leaving unknown formats at the end."""
    clean = sorted({str(v).strip() for v in values if str(v).strip() and str(v) != "nan"})
    return sorted(clean, key=lambda value: (pd.isna(pd.to_datetime(value, errors="coerce")), pd.to_datetime(value, errors="coerce") if not pd.isna(pd.to_datetime(value, errors="coerce")) else pd.Timestamp.max, value))


def _number(value) -> str:
    try:
        return f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _currency(value) -> str:
    return f"Rp {_number(value)}"


def _pct(value) -> str:
    try:
        return f"{float(value):.1f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _status(value, yellow_at, red_at, *, lower_is_bad=False) -> str:
    """Classify a metric with explicit, reusable green/yellow/red thresholds."""
    if value is None:
        return "gray"
    if lower_is_bad:
        return "red" if value <= red_at else "yellow" if value <= yellow_at else "green"
    return "red" if value >= red_at else "yellow" if value >= yellow_at else "green"


def _read_json(paths) -> tuple[dict, Path | None]:
    for path in paths:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data, path
        except (OSError, json.JSONDecodeError):
            continue
    return {}, None


def _load_problem_files() -> tuple[dict, dict, list[str]]:
    summary, summary_path = _read_json(PROBLEM_FILES["summary"])
    monthly, monthly_path = _read_json(PROBLEM_FILES["monthly"])
    warnings = []
    if not summary_path:
        warnings.append("Ringkasan problem booth belum tersedia.")
    if not monthly_path:
        warnings.append("Data bulanan problem booth belum tersedia.")
    return summary, monthly, warnings


def _load_daily_revenue() -> tuple[pd.DataFrame, str | None]:
    """Load valid daily revenue rows; never substitute monthly data for daily facts."""
    try:
        raw = json.loads(DAILY_SUMMARY_CACHE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("records", raw.get("data", []))
        if not isinstance(raw, list) or not raw:
            return pd.DataFrame(), "Data revenue harian belum tersedia; perbandingan pace tidak ditampilkan."
        frame = pd.DataFrame(raw)
        revenue_col = "revenue" if "revenue" in frame else "total_revenue" if "total_revenue" in frame else None
        if "date" not in frame or revenue_col is None:
            return pd.DataFrame(), "Format data revenue harian tidak lengkap; perbandingan pace tidak ditampilkan."
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame["revenue"] = pd.to_numeric(frame[revenue_col], errors="coerce")
        frame = frame.dropna(subset=["date", "revenue"])
        return frame, None if not frame.empty else "Data revenue harian tidak valid; perbandingan pace tidak ditampilkan."
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return pd.DataFrame(), "Data revenue harian belum tersedia; perbandingan pace tidak ditampilkan."


def _daily_revenue_metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"available": False}
    totals = frame.groupby("date")["revenue"].sum().sort_index()
    reference = totals.index.max()
    current_start = reference.replace(day=1)
    previous_end = current_start - pd.Timedelta(days=1)
    previous_start = previous_end.replace(day=1)
    compare_day = min(reference.day, calendar.monthrange(previous_start.year, previous_start.month)[1])
    previous_compare_end = previous_start.replace(day=compare_day)
    current_mtd = float(totals.loc[(totals.index >= current_start) & (totals.index <= reference)].sum())
    previous_window = totals.loc[(totals.index >= previous_start) & (totals.index <= previous_compare_end)]
    previous_mtd = float(previous_window.sum()) if not previous_window.empty else None
    pace_delta = ((current_mtd / previous_mtd) - 1) * 100 if previous_mtd else None
    full_month_rows = totals.loc[(totals.index >= previous_start) & (totals.index <= previous_end)]
    full_month = float(full_month_rows.sum()) if not full_month_rows.empty else None

    calendar_days = pd.date_range(reference - pd.Timedelta(days=6), reference, freq="D")
    seven_day_average = float(totals.reindex(calendar_days, fill_value=0).mean())
    earlier = totals.loc[totals.index < reference]
    previous_date = earlier.index.max() if not earlier.empty else None
    previous_day = float(earlier.loc[previous_date]) if previous_date is not None else None
    latest = float(totals.loc[reference])
    daily_delta = ((latest / previous_day) - 1) * 100 if previous_day else None
    versus_average = ((latest / seven_day_average) - 1) * 100 if seven_day_average else None

    outlet_declines = None
    if previous_mtd is not None and "outlet_name" in frame:
        current_outlets = frame.loc[(frame["date"] >= current_start) & (frame["date"] <= reference)].groupby("outlet_name")["revenue"].sum()
        previous_outlets = frame.loc[(frame["date"] >= previous_start) & (frame["date"] <= previous_compare_end)].groupby("outlet_name")["revenue"].sum()
        paired = pd.concat([current_outlets.rename("current"), previous_outlets.rename("previous")], axis=1).dropna()
        outlet_declines = int((paired["current"] < paired["previous"]).sum())
    return {
        "available": True, "reference": reference, "current_mtd": current_mtd,
        "previous_start": previous_start, "previous_end": previous_end,
        "previous_compare_end": previous_compare_end,
        "previous_mtd": previous_mtd, "pace_delta": pace_delta, "full_month": full_month,
        "latest": latest, "previous_date": previous_date, "previous_day": previous_day,
        "daily_delta": daily_delta, "seven_day_average": seven_day_average,
        "versus_average": versus_average, "outlet_declines": outlet_declines,
    }


def _short_date(value) -> str:
    months = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{value.day} {months[value.month]}"


def _parse_dt(value):
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def _load_leads(now: datetime | None = None) -> dict:
    data, path = _read_json((LEAD_CACHE,))
    records = data.get("records", []) if isinstance(data.get("records", []), list) else []
    now = now or datetime.now(timezone.utc)
    terminal = {"live", "lost", "rejected", "closed"}
    high_open, stagnant = [], []
    for record in records:
        priority = str(record.get("priority", "")).strip().lower()
        state = str(record.get("status_lead", "")).strip().lower()
        if priority == "high" and state not in terminal:
            high_open.append(record)
            modified = _parse_dt(record.get("modified"))
            if modified and (now - modified).days >= 30:
                stagnant.append(record)
    return {
        "available": bool(path), "records": records, "high_open": high_open,
        "stagnant": stagnant, "last_sync": data.get("last_sync"),
    }


def _freshness_age(value) -> int | None:
    stamp = _parse_dt(value)
    return max(0, (datetime.now(timezone.utc) - stamp).days) if stamp else None


def _badge(label: str, tone: str):
    color = COLORS[tone]
    ui.label(label).style(f"color:{color};background:{color}1f;border:1px solid {color}55;").classes("text-xs font-bold px-2 py-1 rounded-full")


def _metric_card(label, value, detail, tone):
    with ui.element("div").style(CARD).classes("flex-1 min-w-[190px]"):
        with ui.row().classes("items-start justify-between w-full gap-2"):
            ui.label(label).classes("text-xs text-gray-400 uppercase tracking-wide")
            _badge({"green": "Hijau", "yellow": "Kuning", "red": "Merah", "gray": "N/A"}[tone], tone)
        ui.label(value).style(f"color:{COLORS[tone]};").classes("text-2xl font-bold mt-2")
        ui.label(detail).classes("text-xs text-gray-500 mt-1")


def _section(title, subtitle=""):
    ui.label(title).classes("text-xl font-bold text-white mt-3")
    if subtitle:
        ui.label(subtitle).classes("text-xs text-gray-500 -mt-1 mb-1")


def create_page(container):
    with container:
        warnings = []
        try:
            df = get_adapter().load_data()
        except Exception as exc:
            df = pd.DataFrame()
            warnings.append(f"Data transaksi belum dapat dimuat ({type(exc).__name__}).")
        summary, monthly, problem_warnings = _load_problem_files()
        warnings.extend(problem_warnings)
        leads = _load_leads()
        if not leads["available"]:
            warnings.append("Cache lead partnership belum tersedia.")
        daily_frame, daily_warning = _load_daily_revenue()
        daily = _daily_revenue_metrics(daily_frame)
        if daily_warning:
            warnings.append(daily_warning)

        periods = _safe_periods(df.get("periode", pd.Series(dtype=str)).dropna().tolist()) if not df.empty else []
        active_period = periods[-1] if periods else None
        previous_period = periods[-2] if len(periods) > 1 else None
        current = df[df["periode"].astype(str) == active_period].copy() if active_period and "periode" in df else pd.DataFrame()
        previous = df[df["periode"].astype(str) == previous_period].copy() if previous_period and "periode" in df else pd.DataFrame()
        for frame in (current, previous):
            for col in ("total_revenue", "paid_per_photo_rate"):
                if col in frame:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

        revenue = daily.get("current_mtd") if daily["available"] else None
        previous_revenue = daily.get("full_month") if daily["available"] else None
        revenue_delta = daily.get("pace_delta") if daily["available"] else None
        active_rows = current
        if "outlet_status" in current:
            active_rows = current[~current["outlet_status"].fillna("").astype(str).str.lower().isin({"tidak aktif", "inactive", ""})]
        outlets = active_rows["outlet_name"].nunique() if "outlet_name" in active_rows else len(active_rows)
        conversion = float(active_rows["paid_per_photo_rate"].mean()) if not active_rows.empty and "paid_per_photo_rate" in active_rows else None

        declines = daily.get("outlet_declines") if daily["available"] else None

        statuses = summary.get("statuses", {}) if isinstance(summary.get("statuses", {}), dict) else {}
        critical_ops = sum(int(v or 0) for k, v in statuses.items() if str(k).strip().lower() in {"open", "reopen", "uncompleted", "on the way", ""})
        open_records = summary.get("open_problems", []) if isinstance(summary.get("open_problems", []), list) else []
        aged_ops = sum(1 for r in open_records if (_parse_dt(r.get("tanggal_foto")) and (datetime.now(timezone.utc) - _parse_dt(r.get("tanggal_foto"))).days >= 7))
        lead_stagnant = len(leads["stagnant"])
        lead_age = _freshness_age(leads["last_sync"])
        problem_age = _freshness_age(summary.get("last_sync"))
        data_age = max([v for v in (lead_age, problem_age) if v is not None], default=None)

        with ui.row().classes("w-full items-start justify-between gap-4"):
            with ui.column().classes("gap-1"):
                ui.label("👑 CEO Command Center").classes("text-3xl font-bold text-white")
                ui.label("Ringkasan kesehatan bisnis, risiko utama, dan keputusan yang membutuhkan perhatian CEO.").classes("text-sm text-gray-400")
            with ui.row().classes("gap-2 flex-wrap justify-end"):
                _badge(f"Periode: {active_period or 'N/A'}", "green" if active_period else "gray")
                _badge(f"Lead sync: {leads['last_sync'] or 'N/A'}", _status(lead_age, 3, 7))
                _badge(f"Ops sync: {summary.get('last_sync') or 'N/A'}", _status(problem_age, 3, 7))

        for warning in warnings:
            ui.label(f"⚠️ {warning}").classes("w-full text-xs text-amber-300 bg-amber-950/30 border border-amber-700/40 rounded px-3 py-2")

        _section("Pulse Harian CEO", "Sinyal revenue harian dari tanggal data terbaru, bukan tanggal sistem.")
        with ui.row().classes("w-full gap-3 flex-wrap"):
            if daily["available"]:
                daily_tone = _status(daily["versus_average"], -10, -25, lower_is_bad=True)
                _metric_card("Revenue Hari Terakhir", _currency(daily["latest"]), _short_date(daily["reference"]), daily_tone)
                _metric_card("Delta vs Hari Data Sebelumnya", _pct(daily["daily_delta"]), f"vs {_short_date(daily['previous_date'])}" if daily["previous_date"] is not None else "pembanding belum tersedia", _status(daily["daily_delta"], -10, -25, lower_is_bad=True))
                _metric_card("Rata-rata 7 Hari", _currency(daily["seven_day_average"]), f"hari terakhir {_pct(daily['versus_average'])} vs rata-rata 7 hari kalender", daily_tone)
            else:
                _metric_card("Revenue Harian", "N/A", "Data harian belum tersedia; tidak memakai estimasi bulanan.", "gray")

        _section("Executive Health Bar", "Ambang pace: kuning ≤-10%, merah ≤-20%; conversion ≤20% merah; isu ≥50 merah.")
        with ui.row().classes("w-full gap-3 flex-wrap"):
            pace_detail = f"MTD s.d. {_short_date(daily['reference'])} vs MTD s.d. {_short_date(daily['previous_compare_end'])}" if daily["available"] and daily["previous_mtd"] is not None else "Perbandingan MTD setara belum tersedia"
            _metric_card("Pace Revenue Bulan Berjalan", _currency(revenue) if revenue is not None else "N/A", f"{pace_detail} · {_pct(revenue_delta)}" if revenue_delta is not None else pace_detail, _status(revenue_delta, -10, -20, lower_is_bad=True))
            full_month_detail = f"{_short_date(daily['previous_start'])}–{_short_date(daily['previous_end'])} · bulan penuh" if daily["available"] and previous_revenue is not None else "Bulan penuh belum tersedia"
            _metric_card("Revenue Bulan Lengkap Terakhir", _currency(previous_revenue) if previous_revenue is not None else "N/A", full_month_detail, "green" if previous_revenue is not None else "gray")
            decline_detail = f"{declines} outlet turun pada window MTD setara" if declines is not None else "Perbandingan outlet MTD belum tersedia"
            _metric_card("Outlet Aktif", _number(outlets), decline_detail, _status(declines, 1, max(5, int(outlets * .25))))
            _metric_card("Effective Conversion", _pct(conversion), "rata-rata paid per photo outlet aktif", _status(conversion, 30, 20, lower_is_bad=True))
            _metric_card("Critical Ops Issues", _number(critical_ops), f"{aged_ops} open record berumur ≥7 hari", _status(critical_ops, 10, 50))
            _metric_card("High Priority Lead Stagnant", _number(lead_stagnant), "high priority non-terminal, ≥30 hari", _status(lead_stagnant, 1, 5))

        alarms = [
            ("Pace revenue MTD", f"{_pct(revenue_delta) if revenue_delta is not None else 'Belum dapat dihitung'} pada window MTD yang setara.", _status(revenue_delta, -10, -20, lower_is_bad=True), "Revenue"),
            ("Outlet kehilangan momentum", f"{declines} outlet turun pada window MTD setara." if declines is not None else "Perbandingan outlet MTD belum tersedia.", _status(declines, 1, max(5, int(outlets * .25))), "Commercial"),
            ("Backlog problem booth", f"{critical_ops} open/uncompleted; {aged_ops} record open berumur ≥7 hari.", _status(critical_ops, 10, 50), "Operations"),
            ("Lead bernilai tinggi stagnan", f"{lead_stagnant} dari {len(leads['high_open'])} lead High non-terminal tidak berubah ≥30 hari.", _status(lead_stagnant, 1, 5), "Partnership"),
            ("Kontrol freshness data", f"Umur terlama cache lead/ops: {data_age} hari." if data_age is not None else "Timestamp sinkronisasi tidak lengkap.", _status(data_age, 3, 7), "Data Control"),
        ]
        _section("CEO Radar — 5 Alarm", "Exception yang paling membutuhkan perhatian lintas fungsi.")
        with ui.row().classes("w-full gap-3 flex-wrap"):
            for title, detail, tone, owner in alarms:
                with ui.element("div").style(CARD).classes("flex-1 min-w-[220px]"):
                    with ui.row().classes("justify-between items-center w-full gap-2"):
                        ui.label(title).classes("text-sm font-bold text-white")
                        _badge(owner, tone)
                    ui.label(detail).classes("text-xs text-gray-400 mt-2")

        decisions = []
        if daily["available"] and daily["versus_average"] is not None and daily["versus_average"] <= -15:
            decisions.append(("Cek penurunan revenue harian", f"Revenue {_short_date(daily['reference'])} {_pct(abs(daily['versus_average']))} di bawah rata-rata 7 hari; cek outlet penyumbang gap sebelum operasional hari berikutnya."))
        elif daily["available"] and daily["daily_delta"] is not None and daily["daily_delta"] <= -20:
            decisions.append(("Validasi penurunan harian", f"Revenue {_short_date(daily['reference'])} turun {_pct(abs(daily['daily_delta']))} vs hari data sebelumnya; cek outlet dengan penurunan nominal terbesar."))
        if revenue_delta is not None and revenue_delta < 0:
            decisions.append(("Audit pace outlet", f"Pace MTD tertinggal {_pct(abs(revenue_delta))}; tetapkan recovery owner untuk outlet dengan gap terbesar pada window setara."))
        if lead_stagnant:
            decisions.append(("Intervensi lead High", f"Putuskan jalur founder/senior outreach untuk {lead_stagnant} lead stagnan ≥30 hari."))
        if critical_ops:
            decisions.append(("Turunkan backlog operasional", f"Minta rencana penutupan {critical_ops} isu open/uncompleted, dimulai dari {aged_ops} record aged."))
        if data_age is not None and data_age >= 3:
            decisions.append(("Pulihkan ritme sinkronisasi", f"Cache terlama berumur {data_age} hari; tunjuk owner dan SLA freshness."))
        if not decisions:
            decisions.append(("Pertahankan ritme eksekusi", "Tidak ada exception besar dari data tersedia; validasi kembali pada sinkronisasi berikutnya."))
        _section("Decision Board")
        with ui.element("div").style(CARD).classes("w-full"):
            for index, (title, detail) in enumerate(decisions[:5], 1):
                with ui.row().classes("w-full items-start gap-3 py-2 border-b border-[#313244] last:border-0"):
                    ui.label(str(index)).classes("w-6 h-6 text-center rounded-full bg-[#313244] text-xs font-bold pt-1")
                    with ui.column().classes("gap-0 flex-1"):
                        ui.label(title).classes("text-sm font-bold text-white")
                        ui.label(detail).classes("text-xs text-gray-400")

        domain_rows = [
            ("Revenue Engine", _status(revenue_delta, -10, -20, lower_is_bad=True), [f"MTD {_currency(revenue) if revenue is not None else 'N/A'}", f"Pace setara {_pct(revenue_delta)}", f"{outlets} outlet aktif"]),
            ("Operasional Booth", _status(critical_ops, 10, 50), [f"{critical_ops} isu belum tuntas", f"{aged_ops} open ≥7 hari", f"{summary.get('total', 0)} total historis"]),
            ("Partnership / Expansion", _status(lead_stagnant, 1, 5), [f"{len(leads['high_open'])} High non-terminal", f"{lead_stagnant} stagnant", f"{len(leads['records'])} lead tercache"]),
            ("Data Freshness / Control", _status(data_age, 3, 7), [f"Lead age {lead_age if lead_age is not None else 'N/A'} hari", f"Ops age {problem_age if problem_age is not None else 'N/A'} hari", "Fallback prod → lokal aktif"]),
        ]
        _section("Minister / Domain Scoreboard", "Hanya domain dengan sumber data yang tersedia.")
        with ui.row().classes("w-full gap-3 flex-wrap"):
            for name, tone, signals in domain_rows:
                with ui.element("div").style(CARD).classes("flex-1 min-w-[240px]"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(name).classes("font-bold text-white")
                        _badge({"green": "Hijau", "yellow": "Kuning", "red": "Merah", "gray": "N/A"}[tone], tone)
                    for signal in signals:
                        ui.label(f"• {signal}").classes("text-xs text-gray-400")

        matrix = [
            ("Revenue & Growth", [f"MTD berjalan: {_currency(revenue) if revenue is not None else 'N/A'}", f"Bulan lengkap terakhir: {_currency(previous_revenue) if previous_revenue is not None else 'N/A'}", f"Pace MTD setara: {_pct(revenue_delta)}"]),
            ("Outlet Quality", [f"Aktif: {_number(outlets)}", f"Menurun (MTD setara): {_number(declines) if declines is not None else 'N/A'}", f"Conversion: {_pct(conversion)}"]),
            ("Operational Stability", [f"Belum tuntas: {_number(critical_ops)}", f"Open aged: {_number(aged_ops)}", f"Sync: {summary.get('last_sync') or 'N/A'}"]),
            ("Expansion Pipeline", [f"High open: {_number(len(leads['high_open']))}", f"High stagnant: {_number(lead_stagnant)}", f"Total cache: {_number(len(leads['records']))}"]),
        ]
        _section("Business Matrix")
        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-3 w-full"):
            for title, bullets in matrix:
                with ui.element("div").style(CARD):
                    ui.label(title).classes("text-sm font-bold text-white mb-1")
                    for bullet in bullets:
                        ui.label(f"• {bullet}").classes("text-xs text-gray-400")

        _section("Quick Drilldown")
        with ui.row().classes("w-full gap-2 flex-wrap pb-8"):
            for label, route in [("Trend", "/trend"), ("AI Decision", "/ai-decision"), ("Ranking", "/ranking"), ("Problem Booth", "/problem-booth"), ("Lead Partnership", "/lead-partnership"), ("Conversion", "/conversion")]:
                ui.button(label, on_click=lambda r=route: ui.navigate.to(r)).props("outline dense color=primary")
