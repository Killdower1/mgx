"""📋 Lead Partnership — manage partnership leads from ERPNext."""

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.erpnext import (
    load_erpnext_config,
    save_erpnext_config,
    check_connection,
    fetch_lead_partnerships,
    get_lead_partnership,
    create_lead_partnership,
    update_lead_partnership,
    get_jenis_partnership_options,
    get_skema_kerjasama_options,
    get_jenis_lokasi_options,
    get_tipe_lokasi_options,
    get_status_lead_options,
    get_source_lead_options,
    get_priority_options,
    aggregate_lp_monthly,
    aggregate_lp_by_sales_pic_full,
    LEAD_PARTNERSHIP_DISPLAY_NAMES,
)
from components.compat import rerun, HAS_COLUMN_CONFIG


def show_lead_partnership_page():
    st.title("📋 Lead Partnership")
    st.caption("Manajemen data partnership lead dari ERPNext — lihat, cari, edit, dan tambah lead.")

    # ----------------- CONFIG CHECK -----------------
    cfg = load_erpnext_config()
    connected = False

    if not cfg.get("url") or not cfg.get("api_key"):
        _render_config_form(cfg)
        return
    else:
        connected_ok, connected_msg = check_connection()
        connected = connected_ok
        if not connected_ok:
            st.warning(f"⚠️ {connected_msg}")
            with st.expander("🔧 Konfigurasi ERPNext"):
                _render_config_form(cfg)
            # Still show cached/generic data if connection fails

    # ----------------- TOOLBAR -----------------
    cols = st.columns([3, 1, 1])
    with cols[0]:
        search_q = st.text_input("🔍 Cari lead (nama, tempat, PIC, kota)", key="lp_search")
    with cols[1]:
        filter_status = st.selectbox(
            "Filter Status",
            ["Semua"] + [s for s in get_status_lead_options() if s],
            key="lp_filter_status",
        )
    with cols[2]:
        refresh = st.button("🔄 Refresh Data", type="secondary", use_container_width=True)

    # ----------------- FETCH -----------------
    if connected:
        df = fetch_lead_partnerships(limit=5000)
    else:
        df = pd.DataFrame()

    if df.empty:
        st.info("Belum ada data Lead Partnership dari ERPNext.")
        if not connected:
            st.caption("Pastikan konfigurasi ERPNext benar dan koneksi tersambung.")
        return

    # ----------------- FILTER -----------------
    if filter_status and filter_status != "Semua":
        df = df[df.get("status_lead", "").astype(str).str.strip() == filter_status].copy()

    if search_q.strip():
        q = search_q.strip().lower()
        mask = (
            df.get("nama_pic", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("nama_tempat", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("nama_perusahaan__lembaga__venue_jika_ada", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("kota_lokasi", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("name", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        )
        df = df[mask].copy()

    # ----------------- TABS -----------------
    tab_list, tab_bulanan, tab_pic, tab_add = st.tabs([
        "📋 Daftar Lead", "📊 Ringkasan Bulanan", "👤 Per PIC", "➕ Tambah Lead Baru",
    ])

    with tab_list:
        _render_lead_table(df)

    with tab_bulanan:
        _tab_ringkasan_bulanan(df)

    with tab_pic:
        _tab_per_pic(df)

    with tab_add:
        if connected:
            _render_create_form()
        else:
            st.info("Sambungkan ke ERPNext dulu untuk menambah lead baru.")


# ================= CONFIG FORM =================

def _render_config_form(cfg: dict):
    st.subheader("🔧 Konfigurasi ERPNext")
    st.caption("Masukkan kredensial ERPNext untuk mengakses Lead Partnership.")

    with st.form("erpnext_config_form"):
        url = st.text_input(
            "URL ERPNext",
            value=cfg.get("url", ""),
            placeholder="https://erp.midory.id",
            key="lp_config_url",
        )
        api_key = st.text_input(
            "API Key",
            value=cfg.get("api_key", ""),
            type="password",
            key="lp_config_key",
        )
        api_secret = st.text_input(
            "API Secret",
            value=cfg.get("api_secret", ""),
            type="password",
            key="lp_config_secret",
        )
        submitted = st.form_submit_button("💾 Simpan & Uji Koneksi", type="primary")
        if submitted:
            if not url.strip():
                st.error("URL ERPNext wajib diisi.")
            elif not api_key.strip():
                st.error("API Key wajib diisi.")
            else:
                save_erpnext_config({
                    "url": url.strip().rstrip("/"),
                    "api_key": api_key.strip(),
                    "api_secret": api_secret.strip(),
                })
                ok, msg = check_connection()
                if ok:
                    st.success(f"✅ {msg}")
                    rerun()
                else:
                    st.error(f"❌ {msg}")


# ================= LEAD TABLE =================

def _render_lead_table(df: pd.DataFrame):
    st.write(f"**{len(df)}** lead ditemukan.")

    display = df.copy()
    # Format columns for display — use actual ERPNext field names
    col_map = dict(LEAD_PARTNERSHIP_DISPLAY_NAMES)
    # Only include columns that exist in the dataframe
    avail_cols = [c for c in col_map if c in display.columns]
    # Order: most important fields first
    preferred_order = [
        "name", "nama_pic", "nama_perusahaan__lembaga__venue_jika_ada",
        "nama_tempat", "jenis_partnership", "kota_lokasi",
        "jenis_lokasi", "tipe_lokasi", "skema_kerja_sama_yang_terbuka",
        "status_lead", "source_lead", "sales_pic", "sales_pic_full",
    ]
    ordered = [c for c in preferred_order if c in avail_cols]
    remaining = [c for c in avail_cols if c not in ordered]
    final_cols = ordered + remaining

    display = display[final_cols].rename(columns=col_map)

    # Make status column more visual
    status_display_name = col_map.get("status_lead", "Status Lead")
    if status_display_name in display.columns:
        display[status_display_name] = display[status_display_name].apply(_status_badge)

    # Use st.dataframe with config
    if HAS_COLUMN_CONFIG:
        col_config = {
            col_map.get("name", "ID Lead"): st.column_config.TextColumn("ID Lead", width="small"),
            col_map.get("nama_pic", "Nama PIC"): st.column_config.TextColumn("Nama PIC", width="medium"),
            col_map.get("sales_pic", "Sales PIC"): st.column_config.TextColumn("Sales PIC", width="medium"),
            col_map.get("sales_pic_full", "Sales PIC (Full)"): st.column_config.TextColumn("Sales PIC (Full)", width="medium"),
        }
    else:
        col_config = None

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=400,
    )

    # ----------------- DETAIL / EDIT SELECTION -----------------
    lead_names = df["name"].tolist() if "name" in df.columns else []
    if lead_names:
        st.markdown("---")
        st.subheader("✏️ Edit Lead")
        selected = st.selectbox(
            "Pilih Lead untuk diedit",
            lead_names,
            format_func=lambda x: f"{x} — {_get_lead_label(df, x)}",
            key="lp_select_edit",
        )
        if selected:
            _render_edit_form(selected)


def _get_lead_label(df: pd.DataFrame, name: str) -> str:
    row = df[df["name"] == name]
    if row.empty:
        return name
    r = row.iloc[0]
    parts = [str(r.get("nama_pic", "")), str(r.get("nama_tempat", "")), str(r.get("kota_lokasi", ""))]
    return " - ".join(p for p in parts if p.strip())


def _status_badge(status) -> str:
    status_str = str(status or "").strip()
    if not status_str:
        return "-"
    badges = {
        "New": "🆕",
        "Contact": "🔵",
        "Need Info": "🟠",
        "Qualified": "🟢",
        "Negotiation": "🟡",
        "Approved": "✅",
        "Live": "💚",
        "Lost": "🔴",
    }
    emoji = badges.get(status_str, "⚪")
    return f"{emoji} {status_str}"


# ================= EDIT FORM =================

def _render_edit_form(record_name: str):
    detail = get_lead_partnership(record_name)
    if not detail:
        st.error(f"Tidak bisa mengambil detail lead {record_name}.")
        return

    with st.form(f"edit_lp_{record_name}"):
        st.markdown(f"**Mengedit:** {record_name}")
        cols = st.columns(2)

        with cols[0]:
            nama_pic = st.text_input(
                "Nama PIC", value=detail.get("nama_pic", ""),
                key=f"lp_edit_nama_pic_{record_name}",
            )
            nama_perusahaan = st.text_input(
                "Perusahaan / Venue",
                value=detail.get("nama_perusahaan__lembaga__venue_jika_ada", ""),
                key=f"lp_edit_perusahaan_{record_name}",
            )
            nama_tempat = st.text_input(
                "Nama Tempat", value=detail.get("nama_tempat", ""),
                key=f"lp_edit_tempat_{record_name}",
            )
            jenis_partnership = st.selectbox(
                "Jenis Partnership", get_jenis_partnership_options(),
                index=_dropdown_idx(get_jenis_partnership_options(), detail.get("jenis_partnership", "")),
                key=f"lp_edit_jenis_{record_name}",
            )
            kota_lokasi = st.text_input(
                "Kota", value=detail.get("kota_lokasi", ""),
                key=f"lp_edit_kota_{record_name}",
            )

        with cols[1]:
            sumber_lead = st.selectbox(
                "Source Lead", get_source_lead_options(),
                index=_dropdown_idx(get_source_lead_options(), detail.get("source_lead", "")),
                key=f"lp_edit_source_{record_name}",
            )
            sales_pic = st.text_input(
                "Sales PIC", value=detail.get("sales_pic", ""),
                key=f"lp_edit_sales_pic_{record_name}",
            )
            sales_pic_full = st.text_input(
                "Sales PIC (Full Name)", value=detail.get("sales_pic_full", ""),
                key=f"lp_edit_sales_pic_full_{record_name}",
            )
            status_lead = st.selectbox(
                "Status Lead", get_status_lead_options(),
                index=_dropdown_idx(get_status_lead_options(), detail.get("status_lead", "")),
                key=f"lp_edit_status_{record_name}",
            )
            priority = st.selectbox(
                "Prioritas", get_priority_options(),
                index=_dropdown_idx(get_priority_options(), detail.get("priority", "")),
                key=f"lp_edit_priority_{record_name}",
            )

        with st.expander("📍 Detail Lokasi"):
            lcols = st.columns(2)
            with lcols[0]:
                jenis_lokasi = st.selectbox(
                    "Jenis Lokasi", get_jenis_lokasi_options(),
                    index=_dropdown_idx(get_jenis_lokasi_options(), detail.get("jenis_lokasi", "")),
                    key=f"lp_edit_jenis_lokasi_{record_name}",
                )
                tipe_lokasi = st.selectbox(
                    "Tipe Lokasi", get_tipe_lokasi_options(),
                    index=_dropdown_idx(get_tipe_lokasi_options(), detail.get("tipe_lokasi", "")),
                    key=f"lp_edit_tipe_lokasi_{record_name}",
                )
                area_penempatan = st.text_input(
                    "Area Penempatan", value=detail.get("area_penempatan", ""),
                    key=f"lp_edit_area_{record_name}",
                )
                alamat_maps = st.text_input(
                    "Alamat / Google Maps", value=detail.get("alamat__link_google_maps", ""),
                    key=f"lp_edit_alamat_{record_name}",
                )
            with lcols[1]:
                skema_kerjasama = st.selectbox(
                    "Skema Kerjasama", get_skema_kerjasama_options(),
                    index=_dropdown_idx(get_skema_kerjasama_options(), detail.get("skema_kerja_sama_yang_terbuka", "")),
                    key=f"lp_edit_skema_{record_name}",
                )
                estimasi_pengunjung = st.text_input(
                    "Estimasi Pengunjung/hari", value=detail.get("estimasi_pengunjung_per_hari", ""),
                    key=f"lp_edit_estimasi_{record_name}",
                )
                space_tersedia = st.text_input(
                    "Space Tersedia", value=detail.get("space_tersedia", ""),
                    key=f"lp_edit_space_{record_name}",
                )
                listrik_tersedia = st.text_input(
                    "Listrik Tersedia", value=detail.get("listrik_tersedia", ""),
                    key=f"lp_edit_listrik_{record_name}",
                )

        with st.expander("📞 Kontak PIC"):
            ccols = st.columns(2)
            with ccols[0]:
                jabatan_pic = st.text_input(
                    "Jabatan PIC", value=detail.get("jabatan_pic", ""),
                    key=f"lp_edit_jabatan_{record_name}",
                )
                nomor_wa = st.text_input(
                    "No. WhatsApp", value=detail.get("nomor_whatsapp_pic", ""),
                    key=f"lp_edit_wa_{record_name}",
                )
            with ccols[1]:
                email_pic = st.text_input(
                    "Email PIC", value=detail.get("email_pic", ""),
                    key=f"lp_edit_email_{record_name}",
                )

        submitted = st.form_submit_button("💾 Simpan Perubahan", type="primary")
        if submitted:
            payload = {
                "nama_pic": nama_pic.strip(),
                "nama_perusahaan__lembaga__venue_jika_ada": nama_perusahaan.strip(),
                "nama_tempat": nama_tempat.strip(),
                "jenis_partnership": jenis_partnership,
                "kota_lokasi": kota_lokasi.strip(),
                "source_lead": sumber_lead,
                "sales_pic": sales_pic.strip(),
                "sales_pic_full": sales_pic_full.strip(),
                "status_lead": status_lead,
                "priority": priority,
                "jenis_lokasi": jenis_lokasi,
                "tipe_lokasi": tipe_lokasi,
                "area_penempatan": area_penempatan.strip(),
                "alamat__link_google_maps": alamat_maps.strip(),
                "skema_kerja_sama_yang_terbuka": skema_kerjasama,
                "estimasi_pengunjung_per_hari": estimasi_pengunjung.strip(),
                "space_tersedia": space_tersedia.strip(),
                "listrik_tersedia": listrik_tersedia.strip(),
                "jabatan_pic": jabatan_pic.strip(),
                "nomor_whatsapp_pic": nomor_wa.strip(),
                "email_pic": email_pic.strip(),
            }
            ok, msg = update_lead_partnership(record_name, payload)
            if ok:
                st.success(f"✅ {msg}")
                rerun()
            else:
                st.error(f"❌ {msg}")


# ================= CREATE FORM =================

def _render_create_form():
    with st.form("create_lead_partnership"):
        st.markdown("**Form Lead Baru**")
        cols = st.columns(2)

        with cols[0]:
            nama_pic = st.text_input(
                "Nama PIC *", placeholder="Nama kontak person",
                key="lp_create_nama_pic",
            )
            nama_perusahaan = st.text_input(
                "Perusahaan / Venue", placeholder="Nama perusahaan / lembaga",
                key="lp_create_perusahaan",
            )
            nama_tempat = st.text_input(
                "Nama Tempat", placeholder="Nama tempat / venue",
                key="lp_create_tempat",
            )
            jenis_partnership = st.selectbox(
                "Jenis Partnership", get_jenis_partnership_options(),
                key="lp_create_jenis",
            )
            kota_lokasi = st.text_input(
                "Kota", placeholder="Kota lokasi",
                key="lp_create_kota",
            )

        with cols[1]:
            sumber_lead = st.selectbox(
                "Source Lead", get_source_lead_options(),
                key="lp_create_source",
            )
            sales_pic = st.text_input(
                "Sales PIC", placeholder="Nama sales PIC",
                key="lp_create_sales_pic",
            )
            sales_pic_full = st.text_input(
                "Sales PIC (Full Name)", placeholder="Nama lengkap sales PIC",
                key="lp_create_sales_pic_full",
            )
            status_lead = st.selectbox(
                "Status Lead", get_status_lead_options(),
                index=1,  # Default: "New"
                key="lp_create_status",
            )
            priority = st.selectbox(
                "Prioritas", get_priority_options(),
                key="lp_create_priority",
            )

        with st.expander("📍 Detail Lokasi"):
            lcols = st.columns(2)
            with lcols[0]:
                jenis_lokasi = st.selectbox(
                    "Jenis Lokasi", get_jenis_lokasi_options(),
                    key="lp_create_jenis_lokasi",
                )
                tipe_lokasi = st.selectbox(
                    "Tipe Lokasi", get_tipe_lokasi_options(),
                    key="lp_create_tipe_lokasi",
                )
            with lcols[1]:
                skema_kerjasama = st.selectbox(
                    "Skema Kerjasama", get_skema_kerjasama_options(),
                    key="lp_create_skema",
                )
                alamat_maps = st.text_input(
                    "Alamat / Google Maps", placeholder="Link Google Maps",
                    key="lp_create_alamat",
                )

        with st.expander("📞 Kontak PIC"):
            ccols = st.columns(2)
            with ccols[0]:
                jabatan_pic = st.text_input(
                    "Jabatan PIC", placeholder="Owner, Manager, dll",
                    key="lp_create_jabatan",
                )
                nomor_wa = st.text_input(
                    "No. WhatsApp", placeholder="08xxxxxxxxxx",
                    key="lp_create_wa",
                )
            with ccols[1]:
                email_pic = st.text_input(
                    "Email PIC", placeholder="email@example.com",
                    key="lp_create_email",
                )

        submitted = st.form_submit_button("➕ Buat Lead Baru", type="primary")
        if submitted:
            if not nama_pic.strip():
                st.error("Nama PIC wajib diisi.")
            else:
                payload = {
                    "nama_pic": nama_pic.strip(),
                    "nama_perusahaan__lembaga__venue_jika_ada": nama_perusahaan.strip(),
                    "nama_tempat": nama_tempat.strip(),
                    "jenis_partnership": jenis_partnership,
                    "kota_lokasi": kota_lokasi.strip(),
                    "source_lead": sumber_lead,
                    "sales_pic": sales_pic.strip(),
                    "sales_pic_full": sales_pic_full.strip(),
                    "status_lead": status_lead,
                    "priority": priority,
                    "jenis_lokasi": jenis_lokasi,
                    "tipe_lokasi": tipe_lokasi,
                    "skema_kerja_sama_yang_terbuka": skema_kerjasama,
                    "alamat__link_google_maps": alamat_maps.strip(),
                    "jabatan_pic": jabatan_pic.strip(),
                    "nomor_whatsapp_pic": nomor_wa.strip(),
                    "email_pic": email_pic.strip(),
                }
                ok, msg = create_lead_partnership(payload)
                if ok:
                    st.success(f"✅ {msg}")
                    rerun()
                else:
                    st.error(f"❌ {msg}")


# ================= MONTHLY SUMMARY TAB =================

def _tab_ringkasan_bulanan(df: pd.DataFrame):
    """Tab: Ringkasan Bulanan — lead per month with status breakdown."""
    st.markdown("### 📊 Ringkasan Bulanan")
    st.caption("Data lead partnership per bulan — breakdown status lead.")

    if df.empty:
        st.info("Belum ada data untuk ditampilkan.")
        return

    # ── Aggregate monthly ──
    monthly = aggregate_lp_monthly(df)

    if monthly.empty:
        st.info("Tidak bisa mengelompokkan data per bulan (field `creation` tidak ditemukan).")
        return

    # ── Metric cards: total overall ──
    agg = df
    c1, c2, c3, c4 = st.columns(4)
    total_all = len(df)
    total_nego = int((agg["status_lead"].astype(str).str.strip() == "Negotiation").sum()) if "status_lead" in agg.columns else 0
    total_live = int((agg["status_lead"].astype(str).str.strip() == "Live").sum()) if "status_lead" in agg.columns else 0
    total_lost = int((agg["status_lead"].astype(str).str.strip() == "Lost").sum()) if "status_lead" in agg.columns else 0

    with c1:
        st.metric("Total Lead", f"{total_all:,}")
    with c2:
        st.metric("💰 Negosiasi", f"{total_nego:,}")
    with c3:
        st.metric("✅ Live", f"{total_live:,}")
    with c4:
        st.metric("❌ Lost", f"{total_lost:,}")

    # ── Stacked bar chart per bulan ──
    status_cols_chart = ["New", "Contact", "Need Info", "Qualified",
                         "Negotiation", "Approved", "Live", "Lost"]
    avail_status = [c for c in status_cols_chart if c in monthly.columns]

    if avail_status:
        melted = monthly.melt(
            id_vars=["bulan", "total", "won_rate"],
            value_vars=avail_status,
            var_name="Status",
            value_name="Jumlah",
        )
        # Filter out zero values
        melted = melted[melted["Jumlah"] > 0]

        if not melted.empty:
            color_map = {
                "New": "#38bdf8", "Contact": "#f59e0b", "Need Info": "#fb923c",
                "Qualified": "#a78bfa", "Negotiation": "#f472b6", "Approved": "#22c55e",
                "Live": "#10b981", "Lost": "#ef4444",
            }
            fig = px.bar(
                melted,
                x="bulan",
                y="Jumlah",
                color="Status",
                title="📈 Tren Lead per Bulan",
                barmode="stack",
                text_auto=True,
                color_discrete_map=color_map,
            )
            fig.update_traces(textposition="inside", textfont=dict(size=10))
            fig.update_layout(
                height=400,
                xaxis=dict(title="Bulan"),
                yaxis=dict(title="Jumlah Lead"),
                legend=dict(orientation="h", y=-0.25),
                paper_bgcolor="#111827",
                plot_bgcolor="#111827",
                font=dict(color="#f8fafc", size=12),
                margin=dict(l=40, r=20, t=40, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Monthly table ──
    st.markdown("#### 📋 Detail per Bulan")

    # Format for display
    display_monthly = monthly.copy()
    # Rename columns
    col_rename = {
        "bulan": "Bulan", "total": "Total",
        "New": "Baru", "Contact": "Kontak", "Need Info": "Need Info",
        "Qualified": "Qualified", "Negotiation": "Negosiasi",
        "Approved": "Approved", "Live": "Live", "Lost": "Lost",
        "won_rate": "Win Rate (%)",
    }
    display_monthly = display_monthly.rename(columns=col_rename)
    # Select and order columns
    display_cols = [c for c in col_rename.values() if c in display_monthly.columns]
    display_monthly = display_monthly[display_cols] if display_cols else display_monthly

    # Style win rate column
    if "Win Rate (%)" in display_monthly.columns:
        display_monthly["Win Rate (%)"] = display_monthly["Win Rate (%)"].apply(
            lambda x: f"{x}%" if pd.notna(x) else "-"
        )

    st.dataframe(
        display_monthly,
        use_container_width=True,
        hide_index=True,
    )

    # ── Donut chart: overall status distribution ──
    st.markdown("#### 🔄 Distribusi Status Keseluruhan")
    if "status_lead" in df.columns:
        status_counts = df["status_lead"].fillna("Unknown").value_counts().reset_index()
        status_counts.columns = ["Status", "Jumlah"]
        status_counts = status_counts[status_counts["Jumlah"] > 0]

        if not status_counts.empty:
            color_map = {
                "New": "#38bdf8", "Contact": "#f59e0b", "Need Info": "#fb923c",
                "Qualified": "#a78bfa", "Negotiation": "#f472b6", "Approved": "#22c55e",
                "Live": "#10b981", "Lost": "#ef4444",
            }
            fig = px.pie(
                status_counts,
                names="Status",
                values="Jumlah",
                hole=0.4,
                color="Status",
                color_discrete_map=color_map,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(
                height=400,
                paper_bgcolor="#111827",
                font=dict(color="#f8fafc", size=12),
                margin=dict(l=20, r=20, t=10, b=20),
                showlegend=True,
                legend=dict(orientation="h", y=-0.2),
            )
            st.plotly_chart(fig, use_container_width=True)


# ================= PER PIC TAB =================

def _tab_per_pic(df: pd.DataFrame):
    """Tab: Per PIC — ringkasan data per sales_pic_full."""
    st.markdown("### 👤 Ringkasan per Sales PIC")
    st.caption("Data lead partnership dikelompokkan berdasarkan nama Sales PIC (full name).")

    if df.empty:
        st.info("Belum ada data untuk ditampilkan.")
        return

    # Cek ketersediaan field
    if "sales_pic_full" not in df.columns or df["sales_pic_full"].isna().all():
        st.warning("⚠️ Field `sales_pic_full` belum terisi di data Lead Partnership ERPNext.")
        st.info("Silakan isi field `sales_pic_full` di ERPNext untuk setiap record lead partnership.")
        # Fallback: tampilkan data per sales_pic (old field)
        if "sales_pic" in df.columns and not df["sales_pic"].isna().all():
            st.markdown("**Menampilkan data per `sales_pic` sebagai fallback:**")
            _render_fallback_pic_table(df)
        return

    # ── Aggregate per PIC ──
    pic_data = aggregate_lp_by_sales_pic_full(df)

    if pic_data.empty:
        st.info("Tidak ada data PIC untuk ditampilkan.")
        return

    # ── Metric cards ──
    total_pics = len(pic_data)
    total_leads = pic_data["total"].sum()
    avg_rate = pic_data["conversion_rate"].mean()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Jumlah Sales PIC", f"{total_pics}")
    with c2:
        st.metric("Total Lead", f"{total_leads:,}")
    with c3:
        st.metric("Rata-rata Win Rate", f"{avg_rate:.1f}%")

    # ── Bar chart per PIC ──
    st.markdown("#### 📊 Perbandingan Antar Sales PIC")
    status_cols_chart = ["New", "Contact", "Need Info", "Qualified",
                         "Negotiation", "Approved", "Live", "Lost"]
    avail_status = [c for c in status_cols_chart if c in pic_data.columns]

    if avail_status:
        melted = pic_data.melt(
            id_vars=["sales_pic_full", "total", "conversion_rate"],
            value_vars=avail_status,
            var_name="Status",
            value_name="Jumlah",
        )
        melted = melted[melted["Jumlah"] > 0]

        if not melted.empty:
            color_map = {
                "New": "#38bdf8", "Contact": "#f59e0b", "Need Info": "#fb923c",
                "Qualified": "#a78bfa", "Negotiation": "#f472b6", "Approved": "#22c55e",
                "Live": "#10b981", "Lost": "#ef4444",
            }
            fig = px.bar(
                melted,
                x="sales_pic_full",
                y="Jumlah",
                color="Status",
                title="📊 Lead per Sales PIC (Stacked)",
                barmode="stack",
                text_auto=True,
                color_discrete_map=color_map,
            )
            fig.update_traces(textposition="inside", textfont=dict(size=10))
            fig.update_layout(
                height=400,
                xaxis=dict(title="Sales PIC"),
                yaxis=dict(title="Jumlah Lead"),
                legend=dict(orientation="h", y=-0.25),
                paper_bgcolor="#111827",
                plot_bgcolor="#111827",
                font=dict(color="#f8fafc", size=12),
                margin=dict(l=40, r=20, t=40, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Conversion rate chart ──
    st.markdown("#### 📈 Win Rate per Sales PIC")
    if "conversion_rate" in pic_data.columns:
        fig = px.bar(
            pic_data,
            x="sales_pic_full",
            y="conversion_rate",
            title="Win Rate (%) per Sales PIC",
            text_auto=".1f",
            color="conversion_rate",
            color_continuous_scale="viridis",
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(
            height=350,
            xaxis=dict(title="Sales PIC"),
            yaxis=dict(title="Win Rate (%)", range=[0, 105]),
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            font=dict(color="#f8fafc", size=12),
            margin=dict(l=40, r=20, t=40, b=80),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Table detail ──
    st.markdown("#### 📋 Detail per Sales PIC")
    col_rename = {
        "sales_pic_full": "Sales PIC",
        "total": "Total Lead",
        "New": "Baru", "Contact": "Kontak", "Need Info": "Need Info",
        "Qualified": "Qualified", "Negotiation": "Negosiasi",
        "Approved": "Approved", "Live": "Live", "Lost": "Lost",
        "conversion_rate": "Win Rate (%)",
    }
    display_pic = pic_data.rename(columns=col_rename)
    display_cols = [c for c in col_rename.values() if c in display_pic.columns]
    display_pic = display_pic[display_cols] if display_cols else display_pic

    if "Win Rate (%)" in display_pic.columns:
        display_pic["Win Rate (%)"] = display_pic["Win Rate (%)"].apply(
            lambda x: f"{x}%" if pd.notna(x) else "0%"
        )

    st.dataframe(
        display_pic,
        use_container_width=True,
        hide_index=True,
    )

    # ── PIC selector untuk lihat detail lead ──
    st.markdown("#### 🔍 Detail Lead per PIC")
    pic_list = sorted(df["sales_pic_full"].dropna().unique().tolist())
    if pic_list:
        selected_pic = st.selectbox(
            "Pilih Sales PIC untuk lihat detail lead-nya",
            pic_list,
            key="pic_detail_select",
        )
        if selected_pic:
            pic_df = df[df["sales_pic_full"] == selected_pic].copy()
            # Tampilkan kolom penting
            detail_cols = [c for c in [
                "name", "nama_pic", "nama_tempat", "kota_lokasi",
                "jenis_partnership", "status_lead", "source_lead",
                "creation",
            ] if c in pic_df.columns]
            if detail_cols:
                detail_df = pic_df[detail_cols].rename(
                    columns={k: LEAD_PARTNERSHIP_DISPLAY_NAMES.get(k, k) for k in detail_cols}
                )
                if "Tgl Dibuat" in detail_df.columns:
                    detail_df["Tgl Dibuat"] = pd.to_datetime(
                        detail_df["Tgl Dibuat"], errors="coerce"
                    ).dt.strftime("%d/%m/%Y")

                st.dataframe(
                    detail_df.sort_values(
                        "Tgl Dibuat" if "Tgl Dibuat" in detail_df.columns else detail_df.columns[0],
                        ascending=False,
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


def _render_fallback_pic_table(df: pd.DataFrame):
    """Fallback: tampilkan data per sales_pic (old field) jika sales_pic_full kosong."""
    from services.erpnext import aggregate_lp_by_pic
    fallback = aggregate_lp_by_pic(df)
    if not fallback.empty:
        col_rename = {
            "sales_pic": "Sales PIC", "total": "Total Lead",
            "New": "Baru", "Contact": "Kontak", "Need Info": "Need Info",
            "Qualified": "Qualified", "Negotiation": "Negosiasi",
            "Approved": "Approved", "Live": "Live", "Lost": "Lost",
            "conversion_rate": "Win Rate (%)",
        }
        display = fallback.rename(columns=col_rename)
        display_cols = [c for c in col_rename.values() if c in display.columns]
        display = display[display_cols] if display_cols else display
        if "Win Rate (%)" in display.columns:
            display["Win Rate (%)"] = display["Win Rate (%)"].apply(
                lambda x: f"{x}%" if pd.notna(x) else "0%"
            )
        st.dataframe(display, use_container_width=True, hide_index=True)


def _dropdown_idx(options: list, current: str) -> int:
    current = str(current or "").strip()
    for i, opt in enumerate(options):
        if str(opt or "").strip() == current:
            return i
    return 0  # fallback index (empty string)
