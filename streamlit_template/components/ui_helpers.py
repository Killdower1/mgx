from typing import List, Tuple, Optional
import pandas as pd
import streamlit as st
from components.compat import df_show, table_height, DEFAULT_TABLE_MAX_HEIGHT

def kemitraan_table_show(df_obj, use_container_width=True, hide_index=True, column_config=None, height=None):
    import streamlit as st
    st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
    df_show(
        df_obj,
        use_container_width=use_container_width,
        hide_index=hide_index,
        column_config=column_config,
        height=height,
    )
    st.markdown('</div>', unsafe_allow_html=True)

def _html_escape(value) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

def _status_class(status) -> str:
    status_text = str(status or "").strip().lower()
    if status_text == "keeper":
        return "keeper"
    if status_text == "optimasi":
        return "optimasi"
    if status_text == "relocate":
        return "relocate"
    if status_text == "tidak aktif":
        return "inactive"
    return "neutral"

def render_mobile_cards(df_obj: pd.DataFrame, title_col: str, rows: List[Tuple[str, str]], status_col: Optional[str] = None, max_rows: int = 30) -> None:
    if not isinstance(df_obj, pd.DataFrame) or df_obj.empty or title_col not in df_obj.columns:
        return
    parts = ['<div class="mobile-card-list">']
    shown = df_obj.head(max_rows).copy()
    for _, row in shown.iterrows():
        title = _html_escape(row.get(title_col, ""))
        status = _html_escape(row.get(status_col, "")) if status_col and status_col in row else ""
        status_class = _status_class(status)
        parts.append('<article class="mobile-data-card">')
        parts.append('<div class="mobile-card-head">')
        parts.append(f'<strong>{title}</strong>')
        if status:
            parts.append(f'<span class="mobile-status {status_class}">{status}</span>')
        parts.append('</div><div class="mobile-card-grid">')
        for label, col in rows:
            if col not in row:
                continue
            parts.append(
                '<div><span>{}</span><b>{}</b></div>'.format(
                    _html_escape(label),
                    _html_escape(row.get(col, "")),
                )
            )
        parts.append('</div></article>')
    if len(df_obj) > len(shown):
        parts.append(f'<p class="mobile-card-note">Menampilkan {len(shown)} dari {len(df_obj)} baris. Tabel lengkap tersedia di layar besar.</p>')
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)

def s_caption(text: str):
    try:
        if hasattr(st, "caption"):
            st.caption(text)
        else:
            st.markdown(f"<small>{text}</small>", unsafe_allow_html=True)
    except Exception:
        st.markdown(f"<small>{text}</small>", unsafe_allow_html=True)

def bool_series(values) -> pd.Series:
    series = values if isinstance(values, pd.Series) else pd.Series(values)
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])

def _clean_master_values(values: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text.lower() in seen:
            continue
        cleaned.append(text)
        seen.add(text.lower())
    return cleaned
