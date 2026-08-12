"""Three tangible revenue-comparison prototypes for CEO review."""

import calendar

import pandas as pd
from nicegui import ui

from pages.ceo_command_center import (
    CARD,
    COLORS,
    _currency,
    _load_daily_revenue,
    _pct,
    _short_date,
)


OPTION_META = {
    1: ("CEO Option 1 — Simple & Fast", "Baca cepat: dua pulse utama, tanpa penjelasan panjang."),
    2: ("CEO Option 2 — Calendar-Aware", "Konteks kalender dibuat terlihat agar perbandingan tidak terasa lebih presisi dari datanya."),
    3: ("CEO Option 3 — Hybrid CEO-Friendly", "Ringkas di permukaan, kontekstual di belakang, dan langsung mengarah ke tindakan."),
}


def _comparison_metrics(frame: pd.DataFrame) -> dict:
    """Calculate the common same-weekday daily and same-day MTD comparisons."""
    if frame.empty:
        return {"available": False}

    totals = frame.groupby("date")["revenue"].sum().sort_index()
    if totals.empty:
        return {"available": False}

    reference = totals.index.max()
    latest = float(totals.loc[reference])
    same_weekday = totals.loc[
        (totals.index < reference) & (totals.index.weekday == reference.weekday())
    ].tail(4)
    weekday_average = float(same_weekday.mean()) if not same_weekday.empty else None
    daily_delta = ((latest / weekday_average) - 1) * 100 if weekday_average else None

    current_start = reference.replace(day=1)
    previous_end = current_start - pd.Timedelta(days=1)
    previous_start = previous_end.replace(day=1)
    compare_day = min(reference.day, calendar.monthrange(previous_start.year, previous_start.month)[1])
    previous_compare_end = previous_start.replace(day=compare_day)
    current_mtd = float(totals.loc[(totals.index >= current_start) & (totals.index <= reference)].sum())
    previous_rows = totals.loc[(totals.index >= previous_start) & (totals.index <= previous_compare_end)]
    previous_mtd = float(previous_rows.sum()) if not previous_rows.empty else None
    mtd_delta = ((current_mtd / previous_mtd) - 1) * 100 if previous_mtd else None

    return {
        "available": True,
        "reference": reference,
        "latest": latest,
        "weekday_average": weekday_average,
        "weekday_count": len(same_weekday),
        "daily_delta": daily_delta,
        "current_mtd": current_mtd,
        "previous_mtd": previous_mtd,
        "previous_compare_end": previous_compare_end,
        "mtd_delta": mtd_delta,
        "day_type": "Weekend" if reference.weekday() >= 5 else "Weekday",
    }


def _tone(delta) -> str:
    if delta is None:
        return "gray"
    return "green" if delta >= -5 else "yellow" if delta >= -15 else "red"


def _chip(text: str, tone: str = "gray"):
    color = COLORS[tone]
    ui.label(text).style(
        f"color:{color};background:{color}18;border:1px solid {color}4d;"
    ).classes("text-xs px-2.5 py-1 rounded-full")


def _card(label: str, value: str, comparison: str, delta=None, *, large=False):
    tone = _tone(delta)
    with ui.element("div").style(CARD).classes("flex-1 min-w-[250px]"):
        ui.label(label).classes("text-xs text-gray-400 uppercase tracking-wide")
        ui.label(value).style(f"color:{COLORS[tone]};").classes(
            "text-3xl font-bold mt-2" if large else "text-2xl font-bold mt-2"
        )
        ui.label(comparison).classes("text-sm text-gray-300 mt-2")


def _header(option: int):
    title, subtitle = OPTION_META[option]
    ui.label(f"🧪 {title}").classes("text-3xl font-bold text-white")
    ui.label(subtitle).classes("text-sm text-gray-400")
    with ui.element("div").style(
        "background:#181825;border:1px solid #45475a;border-radius:10px;padding:12px 16px;"
    ).classes("w-full mt-3"):
        ui.label("CARA MEMBANDINGKAN").classes("text-[10px] text-blue-300 font-bold tracking-widest")
        ui.label(
            "Harian: tanggal data terakhir vs rata-rata maksimal 4 tanggal sebelumnya dengan hari yang sama "
            "• Bulanan: MTD bulan data terakhir vs tanggal yang sama pada bulan sebelumnya"
        ).classes("text-xs text-gray-300 mt-1")


def _empty_state(warning: str | None):
    with ui.element("div").style(CARD).classes("w-full mt-5"):
        ui.label("Revenue harian belum dapat dibandingkan").classes("text-lg font-bold text-white")
        ui.label(warning or "Cache harian kosong atau tidak valid.").classes("text-sm text-gray-400 mt-1")
        ui.label("Halaman tetap aman ditinjau; metrik akan muncul otomatis saat cache tersedia.").classes("text-xs text-amber-300 mt-3")


def _render_option_1(metrics: dict):
    ui.label("Bacaan Harian").classes("text-lg font-bold text-white mt-6")
    daily_detail = (
        f"vs Rata-rata {metrics['weekday_count']} Hari Sejenis: {_currency(metrics['weekday_average'])} "
        f"({_pct(metrics['daily_delta'])})"
        if metrics["weekday_average"] is not None else "Pembanding hari sejenis belum tersedia"
    )
    with ui.row().classes("w-full gap-3"):
        _card("Revenue Hari Data Terakhir", _currency(metrics["latest"]), daily_detail, metrics["daily_delta"], large=True)

    ui.label("Bacaan Bulanan").classes("text-lg font-bold text-white mt-4")
    monthly_detail = (
        f"vs MTD bulan lalu {_currency(metrics['previous_mtd'])} • {_pct(metrics['mtd_delta'])}"
        if metrics["previous_mtd"] is not None else "MTD bulan lalu belum tersedia"
    )
    with ui.row().classes("w-full gap-3"):
        _card("Pace MTD vs Bulan Lalu", _currency(metrics["current_mtd"]), monthly_detail, metrics["mtd_delta"], large=True)
    ui.label("Catatan: perbandingan memakai hari sejenis untuk harian dan tanggal MTD setara untuk bulanan.").classes("text-xs text-gray-500 mt-2")


def _render_option_2(metrics: dict):
    with ui.row().classes("gap-2 flex-wrap mt-5"):
        _chip(metrics["day_type"], "green")
        _chip("Holiday context belum dihubungkan", "yellow")
        _chip("Komposisi kalender bisa berbeda", "yellow")

    ui.label("Daily Baseline dengan Konteks").classes("text-lg font-bold text-white mt-4")
    with ui.row().classes("w-full gap-3 flex-wrap"):
        _card("Revenue Tanggal Data Terakhir", _currency(metrics["latest"]), f"{_short_date(metrics['reference'])} • {metrics['day_type']}", metrics["daily_delta"])
        baseline = _currency(metrics["weekday_average"]) if metrics["weekday_average"] is not None else "N/A"
        detail = f"{metrics['weekday_count']} kemunculan sebelumnya • delta {_pct(metrics['daily_delta'])}"
        _card("Baseline Hari Kalender Sejenis", baseline, detail, metrics["daily_delta"])

    ui.label("Monthly Pace dengan Konteks").classes("text-lg font-bold text-white mt-4")
    with ui.row().classes("w-full gap-3 flex-wrap"):
        _card("MTD Bulan Data Terakhir", _currency(metrics["current_mtd"]), f"s.d. {_short_date(metrics['reference'])}", metrics["mtd_delta"])
        previous = _currency(metrics["previous_mtd"]) if metrics["previous_mtd"] is not None else "N/A"
        _card("MTD Bulan Sebelumnya", previous, f"s.d. {_short_date(metrics['previous_compare_end'])} • delta {_pct(metrics['mtd_delta'])}", metrics["mtd_delta"])

    with ui.element("div").style(CARD).classes("w-full mt-4"):
        ui.label("Catatan Fairness Perbandingan").classes("text-sm font-bold text-white")
        ui.label(
            "Hari dalam bulan dibandingkan pada cutoff tanggal yang sama, tetapi jumlah weekday/weekend dan hari khusus dapat berbeda. "
            "Belum ada dataset libur yang terhubung, jadi tampilan ini adalah prototype konteks kalender—bukan klaim holiday-adjusted."
        ).classes("text-xs text-gray-400 mt-1")


def _action_signal(metrics: dict) -> tuple[str, str, str]:
    deltas = [value for value in (metrics.get("daily_delta"), metrics.get("mtd_delta")) if value is not None]
    if not deltas:
        return "Watch", "yellow", "Baseline belum lengkap; pantau kualitas data sebelum mengambil kesimpulan."
    worst = min(deltas)
    if worst >= -5:
        return "Normal", "green", "Momentum berada dalam rentang normal; pertahankan ritme eksekusi."
    if worst >= -15:
        return "Watch", "yellow", "Ada pelemahan ringan; pantau outlet penyumbang gap pada update berikutnya."
    if worst >= -25:
        return "Investigate", "yellow", "Pelemahan material; cek outlet dan faktor operasional penyumbang gap."
    return "Critical", "red", "Pelemahan tajam; tetapkan owner investigasi dan recovery hari ini."


def _render_option_3(metrics: dict):
    with ui.row().classes("gap-2 flex-wrap mt-5"):
        _chip(f"Data terakhir: {_short_date(metrics['reference'])}", "green")
        _chip(metrics["day_type"])
        _chip(f"Baseline: {metrics['weekday_count']}/4 hari sejenis", "green" if metrics["weekday_count"] == 4 else "yellow")
        _chip("Holiday: belum terhubung", "gray")

    with ui.row().classes("w-full gap-3 flex-wrap mt-4"):
        daily_detail = f"vs hari sejenis {_currency(metrics['weekday_average'])} • {_pct(metrics['daily_delta'])}" if metrics["weekday_average"] is not None else "Baseline hari sejenis belum tersedia"
        monthly_detail = f"vs MTD bulan lalu {_currency(metrics['previous_mtd'])} • {_pct(metrics['mtd_delta'])}" if metrics["previous_mtd"] is not None else "MTD bulan lalu belum tersedia"
        _card("Daily Pulse", _currency(metrics["latest"]), daily_detail, metrics["daily_delta"])
        _card("Monthly Pace", _currency(metrics["current_mtd"]), monthly_detail, metrics["mtd_delta"])

    signal, tone, detail = _action_signal(metrics)
    with ui.element("div").style(
        f"background:{COLORS[tone]}12;border:1px solid {COLORS[tone]}66;border-radius:12px;padding:18px;"
    ).classes("w-full mt-4"):
        with ui.row().classes("w-full items-center gap-4 flex-wrap"):
            ui.label("ACTION SIGNAL").classes("text-xs text-gray-400 font-bold tracking-widest")
            ui.label(signal).style(f"color:{COLORS[tone]};").classes("text-2xl font-bold")
            ui.label(detail).classes("text-sm text-gray-300 flex-1 min-w-[260px]")


def create_page(container, option: int):
    """Render one of the three review options into a NiceGUI container."""
    if option not in OPTION_META:
        raise ValueError(f"Unknown CEO review option: {option}")
    with container:
        _header(option)
        frame, warning = _load_daily_revenue()
        metrics = _comparison_metrics(frame)
        if not metrics["available"]:
            _empty_state(warning)
            return
        if warning:
            ui.label(f"⚠️ {warning}").classes("text-xs text-amber-300 mt-3")
        if option == 1:
            _render_option_1(metrics)
        elif option == 2:
            _render_option_2(metrics)
        else:
            _render_option_3(metrics)
