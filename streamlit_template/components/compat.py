import streamlit as st

# ============== COMPAT LAYER (Streamlit lama / Python 3.6) ==============
HAS_CACHE_DATA = hasattr(st, "cache_data")
HAS_COLUMN_CONFIG = hasattr(st, "column_config")
HAS_CAPTION = hasattr(st, "caption")

def cache_data(func=None, **kwargs):
    deco = st.cache_data if HAS_CACHE_DATA else st.cache
    return deco(func) if func else deco(**kwargs)

def rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def text_col(title, width="medium"):
    if HAS_COLUMN_CONFIG:
        try:
            return st.column_config.TextColumn(title, width=width)
        except Exception:
            return None
    return None

def number_col(title, width="medium", fmt="%d"):
    if HAS_COLUMN_CONFIG:
        try:
            return st.column_config.NumberColumn(title, width=width, format=fmt)
        except Exception:
            return None
    return None

DEFAULT_TABLE_MAX_HEIGHT = 560

def table_height(row_count, min_h=220, max_h=DEFAULT_TABLE_MAX_HEIGHT):
    try:
        rows = int(row_count)
    except Exception:
        rows = 8
    return max(min_h, min(max_h, 72 + (rows + 1) * 36))

def df_show(df_obj, use_container_width=True, hide_index=True, column_config=None, height=None):
    if height is None:
        try:
            height = table_height(len(df_obj), 220, DEFAULT_TABLE_MAX_HEIGHT)
        except Exception:
            height = DEFAULT_TABLE_MAX_HEIGHT
    try:
        if column_config is not None and HAS_COLUMN_CONFIG:
            st.dataframe(df_obj, use_container_width=use_container_width, hide_index=hide_index, column_config=column_config, height=height)
        else:
            st.dataframe(df_obj, use_container_width=use_container_width, hide_index=hide_index, height=height)
    except TypeError:
        st.dataframe(df_obj)
    except Exception:
        try:
            st.table(df_obj)
        except Exception:
            st.write(df_obj)
