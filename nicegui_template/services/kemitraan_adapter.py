"""
Kemitraan adapter for NiceGUI — wraps streamlit_template's services/kemitraan.py
and provides clean data access functions for the Kemitraan page logic.

Uses importlib to avoid namespace collision with nicegui_template's own 'services' package.
"""
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import numpy as np

# Path to streamlit_template
STREAMLIT_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"


# ═══════════════════════════════════════════════
#  Direct pure-python imports from streamlit_template
# ═══════════════════════════════════════════════

def _load_config():
    """Load Config from streamlit_template."""
    import sys
    if str(STREAMLIT_DIR) not in sys.path:
        sys.path.insert(0, str(STREAMLIT_DIR))
    from config import Config
    return Config()


def _load_processor():
    """Load DataProcessor from streamlit_template."""
    import sys
    if str(STREAMLIT_DIR) not in sys.path:
        sys.path.insert(0, str(STREAMLIT_DIR))
    from data_processor import DataProcessor
    return DataProcessor()


def _load_kemitraan_service():
    """Load services/kemitraan.py via importlib to avoid namespace collision."""
    import importlib.util
    module_path = STREAMLIT_DIR / "services" / "kemitraan.py"
    if not module_path.exists():
        raise ImportError(f"kemitraan module not found: {module_path}")
    spec = importlib.util.spec_from_file_location("streamlit_kemitraan", str(module_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════

def get_kemitraan_services():
    """Get all kemitraan service functions as a module object."""
    return _load_kemitraan_service()


def get_sharing_periods():
    """Get list of sharing periods."""
    mod = _load_kemitraan_service()
    return mod.list_sharing_periods()


def load_sharing_outlets(period: Optional[str] = None):
    """Load sharing outlets for a period."""
    mod = _load_kemitraan_service()
    return mod.load_sharing_outlets_exact(period)


def build_kemitraan_financials(df, sharing_master, mapping, period):
    """Build kemitraan financial calculations."""
    mod = _load_kemitraan_service()
    return mod.build_kemitraan_financials(df, sharing_master, mapping, period)


def format_kemitraan_table(df, config):
    """Format kemitraan table with currency/money columns."""
    mod = _load_kemitraan_service()
    return mod.format_kemitraan_table(df, config)


def normalize_sharing_master(df):
    """Normalize sharing master DataFrame."""
    mod = _load_kemitraan_service()
    return mod.normalize_sharing_master_df(df)


def save_sharing_outlets(period, df):
    """Save sharing outlets for a period."""
    mod = _load_kemitraan_service()
    mod.save_sharing_outlets(period, df)


def sync_sharing_to_mapping(sharing_df, period):
    """Sync sharing data to outlet mapping."""
    mod = _load_kemitraan_service()
    return mod.sync_sharing_to_mapping(sharing_df, period)


def get_dashboard_data() -> pd.DataFrame:
    """Load main dashboard data from Streamlit processor."""
    proc = _load_processor()
    return proc.load_data()


def get_outlet_mapping() -> pd.DataFrame:
    """Load outlet mapping."""
    proc = _load_processor()
    return proc.load_outlet_mapping()


def format_currency(amount) -> str:
    """Format as IDR currency."""
    config = _load_config()
    return config.format_currency(amount)


def get_config():
    """Get Config instance."""
    return _load_config()
