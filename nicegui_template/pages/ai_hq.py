"""Difotoin AI HQ — Phase 1 static executive command center prototype."""
from __future__ import annotations

from nicegui import ui

ROOMS = [
    {
        "key": "ceo",
        "name": "CEO Room",
        "status": "warning",
        "headline": "4 open decisions",
        "summary": "Owner-level decisions queued from Finance, Ops, and Marketing.",
        "agent": "Chief of Staff Agent",
        "metrics": ["4 decisions", "2 urgent", "1 waiting approval"],
    },
    {
        "key": "ops",
        "name": "Ops Room",
        "status": "warning",
        "headline": "3 outlets need attention",
        "summary": "Outlet performance, queue health, complaint signal, and escalation watch.",
        "agent": "Ops Agent",
        "metrics": ["3 outlet flags", "7 follow-ups", "1 SLA risk"],
    },
    {
        "key": "machine",
        "name": "Machine Control Room",
        "status": "critical",
        "headline": "CCC 8090 future live source",
        "summary": "Printer, camera/screenshot freshness, modem, ESP heartbeat, and device health control surface.",
        "agent": "Machine Control Agent",
        "metrics": ["8090 linked concept", "No live writes", "Phase 2 data source"],
    },
    {
        "key": "finance",
        "name": "Finance Room",
        "status": "warning",
        "headline": "MTD pace behind target",
        "summary": "Revenue pace, RS exposure, cash collection, and anomaly briefing.",
        "agent": "Finance Agent",
        "metrics": ["MTD pace 84%", "RS watch", "Daily brief ready"],
    },
    {
        "key": "sales",
        "name": "Sales Room",
        "status": "healthy",
        "headline": "12 active leads",
        "summary": "Lead partnership pipeline, aging follow-up, and owner-facing opportunities.",
        "agent": "Sales Agent",
        "metrics": ["12 active leads", "3 hot", "4 aging"],
    },
    {
        "key": "marketing",
        "name": "Marketing Room",
        "status": "warning",
        "headline": "Voucher queue warning",
        "summary": "Instagram campaign, voucher delivery, content queue, and ad learning signals.",
        "agent": "Marketing Agent",
        "metrics": ["Voucher monitor", "IG campaign", "2 content drafts"],
    },
    {
        "key": "tech",
        "name": "Tech Room",
        "status": "healthy",
        "headline": "Sync heartbeat normal",
        "summary": "Deploy, ERPNext sync, cron health, dashboard routes, and integration backlog.",
        "agent": "Dev Agent",
        "metrics": ["8502 online", "ERP cron ok", "No deploy block"],
    },
    {
        "key": "knowledge",
        "name": "Knowledge Room",
        "status": "healthy",
        "headline": "SOP/KB tracker ready",
        "summary": "Owner decisions, SOP, playbooks, and reusable operational knowledge.",
        "agent": "Knowledge Agent",
        "metrics": ["KB indexed", "SOP queue", "Decision log"],
    },
]

AGENTS = [
    ("Chief of Staff Agent", "reviewing", "CEO decisions + daily brief"),
    ("Ops Agent", "watching", "Outlet escalations"),
    ("Machine Control Agent", "standby", "CCC 8090 bridge concept"),
    ("Finance Agent", "reviewing", "MTD pace + RS"),
    ("Sales Agent", "working", "Lead follow-up"),
    ("Marketing Agent", "warning", "Voucher resend strategy"),
    ("Dev Agent", "healthy", "Deploy/sync monitor"),
    ("Knowledge Agent", "healthy", "SOP + decision memory"),
]

DECISIONS = [
    ("High", "MTD revenue behind pace", "Pick corrective action before month-end drag gets larger."),
    ("High", "Outlet issue needs escalation", "Ops wants approval on top-priority booth follow-up."),
    ("Medium", "Voucher failures require resend strategy", "Marketing recommends controlled resend batch."),
    ("Medium", "Lead follow-up aging", "Sales proposes owner-level nudge for hot leads."),
]

EVENTS = [
    "Finance Agent generated daily revenue brief",
    "Ops Agent flagged 3 outlets for review",
    "Machine Control Room mapped CCC 8090 as Phase 2 source",
    "Marketing Agent detected voucher queue warning",
    "Sync Agent verified ERPNext cron heartbeat",
]

KPI_CARDS = [
    ("Business Health", "Warning", "Needs owner focus today", "warning"),
    ("Today Revenue", "Rp --", "Live data in Phase 2", "info"),
    ("MTD Pace", "84%", "Mock signal", "warning"),
    ("Open Decisions", "4", "CEO inbox", "warning"),
    ("Critical Alerts", "1", "Machine room", "critical"),
]


def _status_color(status: str) -> str:
    return {
        "healthy": "#22c55e",
        "working": "#38bdf8",
        "reviewing": "#a78bfa",
        "watching": "#60a5fa",
        "standby": "#94a3b8",
        "warning": "#f59e0b",
        "critical": "#ef4444",
    }.get(status, "#94a3b8")


def _status_bg(status: str) -> str:
    return {
        "healthy": "rgba(34,197,94,.13)",
        "working": "rgba(56,189,248,.13)",
        "reviewing": "rgba(167,139,250,.13)",
        "watching": "rgba(96,165,250,.13)",
        "standby": "rgba(148,163,184,.12)",
        "warning": "rgba(245,158,11,.15)",
        "critical": "rgba(239,68,68,.16)",
    }.get(status, "rgba(148,163,184,.12)")


def _inject_css() -> None:
    ui.add_head_html("""
<style>
.ai-hq-root { color: #e5e7eb; }
.ai-hq-hero { background: radial-gradient(circle at top left, rgba(59,130,246,.22), transparent 34%), linear-gradient(135deg,#111827,#0f172a 48%,#11111b); border:1px solid #273244; border-radius:24px; box-shadow:0 22px 70px rgba(0,0,0,.35); }
.ai-hq-card { background: rgba(30,41,59,.72); border:1px solid rgba(148,163,184,.18); border-radius:18px; box-shadow:0 10px 30px rgba(0,0,0,.18); }
.ai-hq-room { min-height:126px; transition: transform .14s ease, border-color .14s ease, background .14s ease; }
.ai-hq-room:hover { transform: translateY(-2px); border-color: rgba(96,165,250,.55); background: rgba(30,64,175,.18); }
.ai-hq-chip { border:1px solid rgba(148,163,184,.18); border-radius:999px; padding:4px 10px; font-size:11px; color:#cbd5e1; background:rgba(15,23,42,.55); }
.ai-hq-mini-grid { display:grid; grid-template-columns: repeat(4,minmax(180px,1fr)); gap:14px; }
.ai-hq-kpi-grid { display:grid; grid-template-columns: repeat(5,minmax(150px,1fr)); gap:12px; }
.ai-hq-main-grid { display:grid; grid-template-columns: minmax(0,1.55fr) minmax(320px,.75fr); gap:16px; }
.ai-hq-lower-grid { display:grid; grid-template-columns: 1fr 1fr 1fr; gap:16px; }
@media (max-width: 1100px) { .ai-hq-kpi-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } .ai-hq-main-grid, .ai-hq-lower-grid { grid-template-columns: 1fr; } .ai-hq-mini-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
@media (max-width: 640px) { .ai-hq-kpi-grid, .ai-hq-mini-grid { grid-template-columns: 1fr; } .ai-hq-hero { border-radius:18px; } }
</style>
""")


def _render_kpi_card(title: str, value: str, note: str, status: str) -> None:
    color = _status_color(status)
    with ui.element("div").classes("ai-hq-card p-4"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(title).classes("text-xs text-slate-400 uppercase tracking-wide")
            ui.element("div").classes("w-2.5 h-2.5 rounded-full").style(f"background:{color}; box-shadow:0 0 14px {color};")
        ui.label(value).classes("text-2xl font-bold text-white mt-2")
        ui.label(note).classes("text-xs text-slate-400")


def _render_room_card(room: dict, selected: dict, on_select) -> None:
    active = room["key"] == selected["key"]
    color = _status_color(room["status"])
    border = color if active else "rgba(148,163,184,.18)"
    with ui.card().classes("ai-hq-card ai-hq-room p-4 cursor-pointer").style(f"border-color:{border};").on("click", lambda r=room: on_select(r)):
        with ui.row().classes("items-start justify-between w-full"):
            ui.label(room["name"]).classes("text-base font-semibold text-white")
            ui.label(room["status"].upper()).classes("text-[10px] font-bold px-2 py-1 rounded-full").style(f"color:{color}; background:{_status_bg(room['status'])};")
        ui.label(room["headline"]).classes("text-sm text-slate-300 mt-2")
        ui.label(room["summary"]).classes("text-xs text-slate-400 leading-relaxed mt-1")
        with ui.row().classes("gap-1 mt-3"):
            for metric in room["metrics"][:2]:
                ui.label(metric).classes("ai-hq-chip")


def _render_detail_panel(selected: dict) -> None:
    color = _status_color(selected["status"])
    with ui.element("div").classes("ai-hq-card p-5 h-full"):
        ui.label("Selected Control Room").classes("text-xs text-slate-400 uppercase tracking-wide")
        with ui.row().classes("items-center gap-3 mt-2"):
            ui.element("div").classes("w-3 h-3 rounded-full").style(f"background:{color}; box-shadow:0 0 16px {color};")
            ui.label(selected["name"]).classes("text-xl font-bold text-white")
        ui.label(selected["headline"]).classes("text-sm text-slate-300 mt-3")
        ui.label(selected["summary"]).classes("text-sm text-slate-400 leading-relaxed mt-2")
        ui.separator().classes("my-4 bg-slate-700")
        ui.label("Assigned Agent").classes("text-xs text-slate-400 uppercase tracking-wide")
        ui.label(selected["agent"]).classes("text-base text-white mt-1")
        ui.label("Phase 1 mode: static prototype, no live data writes, no machine control action.").classes("text-xs text-amber-300 mt-3")
        with ui.column().classes("gap-2 mt-4"):
            for metric in selected["metrics"]:
                ui.label("• " + metric).classes("text-sm text-slate-300")


def _render_decision_inbox() -> None:
    with ui.element("div").classes("ai-hq-card p-5"):
        ui.label("CEO Decision Inbox").classes("text-lg font-bold text-white")
        ui.label("Mock queue for owner-level calls.").classes("text-xs text-slate-400 mb-3")
        with ui.column().classes("gap-3 w-full"):
            for priority, title, note in DECISIONS:
                status = "critical" if priority == "High" else "warning"
                with ui.element("div").classes("p-3 rounded-xl border border-slate-700 bg-slate-900/40"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(title).classes("text-sm font-semibold text-white")
                        ui.label(priority).classes("text-[10px] px-2 py-1 rounded-full").style(f"color:{_status_color(status)}; background:{_status_bg(status)};")
                    ui.label(note).classes("text-xs text-slate-400 mt-1")


def _render_agent_board() -> None:
    with ui.element("div").classes("ai-hq-card p-5"):
        ui.label("Agent Status Board").classes("text-lg font-bold text-white")
        ui.label("Visible workers for the executive layer.").classes("text-xs text-slate-400 mb-3")
        with ui.column().classes("gap-2 w-full"):
            for name, status, task in AGENTS:
                color = _status_color(status)
                with ui.row().classes("items-center justify-between w-full p-2 rounded-lg bg-slate-900/35"):
                    with ui.row().classes("items-center gap-2"):
                        ui.element("div").classes("w-2.5 h-2.5 rounded-full").style(f"background:{color};")
                        with ui.column().classes("gap-0"):
                            ui.label(name).classes("text-sm text-white")
                            ui.label(task).classes("text-[11px] text-slate-400")
                    ui.label(status).classes("text-[10px] uppercase").style(f"color:{color};")


def _render_events() -> None:
    with ui.element("div").classes("ai-hq-card p-5"):
        ui.label("Latest Events").classes("text-lg font-bold text-white")
        ui.label("Activity log placeholder.").classes("text-xs text-slate-400 mb-3")
        with ui.column().classes("gap-3"):
            for event in EVENTS:
                with ui.row().classes("items-start gap-2"):
                    ui.label("●").classes("text-xs mt-1").style("color:#38bdf8;")
                    ui.label(event).classes("text-sm text-slate-300")


def create_page(container: ui.column) -> None:
    """Render AI HQ Phase 1 page into the provided container."""
    _inject_css()
    selected = {"room": ROOMS[0]}
    detail_holder = ui.column().classes("w-full")
    room_holder = ui.column().classes("w-full")

    def refresh_rooms() -> None:
        room_holder.clear()
        with room_holder:
            with ui.element("div").classes("ai-hq-mini-grid"):
                for room in ROOMS:
                    _render_room_card(room, selected["room"], select_room)

    def refresh_detail() -> None:
        detail_holder.clear()
        with detail_holder:
            _render_detail_panel(selected["room"])

    def select_room(room: dict) -> None:
        selected["room"] = room
        refresh_rooms()
        refresh_detail()

    container.classes("ai-hq-root gap-5")
    with container:
        with ui.element("div").classes("ai-hq-hero p-6 w-full"):
            with ui.row().classes("items-start justify-between w-full gap-4"):
                with ui.column().classes("gap-1"):
                    ui.label("Difotoin AI HQ").classes("text-3xl sm:text-4xl font-black text-white")
                    ui.label("Executive command center for agents, alerts, tasks, and decisions.").classes("text-sm sm:text-base text-slate-300")
                ui.label("Command Status: Simulasi Phase 1").classes("text-xs sm:text-sm px-3 py-2 rounded-full border border-amber-400/30 bg-amber-500/10 text-amber-200")

        with ui.element("div").classes("ai-hq-kpi-grid w-full"):
            for title, value, note, status in KPI_CARDS:
                _render_kpi_card(title, value, note, status)

        with ui.element("div").classes("ai-hq-main-grid w-full"):
            with ui.element("div").classes("ai-hq-card p-5"):
                with ui.row().classes("items-center justify-between w-full mb-4"):
                    with ui.column().classes("gap-0"):
                        ui.label("Office Map").classes("text-xl font-bold text-white")
                        ui.label("Click a room to inspect responsibility, agent, and current mock signal.").classes("text-xs text-slate-400")
                    ui.label("No live control in Phase 1").classes("ai-hq-chip")
                refresh_rooms()
            refresh_detail()

        with ui.element("div").classes("ai-hq-lower-grid w-full"):
            _render_decision_inbox()
            _render_agent_board()
            _render_events()
