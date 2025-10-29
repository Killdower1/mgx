# --- ADD / REPLACE THIS IN app.py ---
def show_admin_panel(config: Config) -> None:
    """Admin panel: edit threshold, lihat config, util cache."""
    import os
    from datetime import datetime

    st.title("⚙️ Admin Panel")

    st.subheader("🎯 Threshold Configuration")
    keeper_now = config.get_threshold("keeper_minimum")
    optim_now  = config.get_threshold("optimasi_minimum")

    c1, c2 = st.columns(2)
    with c1:
        new_keeper = st.number_input(
            "Keeper Minimum (IDR)",
            min_value=0,
            value=int(keeper_now) if isinstance(keeper_now, (int, float)) else 0,
            step=1_000_000,
            format="%d",
            help="Minimal omset bulanan untuk status Keeper",
        )
    with c2:
        new_optim = st.number_input(
            "Optimasi Minimum (IDR)",
            min_value=0,
            value=int(optim_now) if isinstance(optim_now, (int, float)) else 0,
            step=1_000_000,
            format="%d",
            help="Minimal omset bulanan untuk status Optimasi",
        )

    colA, colB = st.columns([1,1])
    with colA:
        if st.button("💾 Save Thresholds", use_container_width=True):
            try:
                config.set_threshold("keeper_minimum", int(new_keeper))
                config.set_threshold("optimasi_minimum", int(new_optim))
                ok = config.save_config()
                if ok:
                    # clear cache data loader kalau ada
                    try:
                        load_app_data.clear()
                    except Exception:
                        pass
                    st.success("✅ Thresholds updated & config saved.")
                    st.rerun()
                else:
                    st.error("❌ Failed to save thresholds.")
            except Exception as e:
                st.error(f"❌ Error saving thresholds: {e}")

    with colB:
        if st.button("🧹 Clear Cached Data", use_container_width=True, help="Paksa reload data yang dicache"):
            try:
                load_app_data.clear()
                st.success("✅ Cache cleared.")
            except Exception as e:
                st.warning(f"ℹ️ Cache clear note: {e}")

    st.subheader("📋 Current Configuration")
    try:
        st.json(config.config)
    except Exception:
        st.info("ℹ️ Tidak bisa menampilkan JSON config (object berbeda).")

    st.subheader("ℹ️ System Information")
    st.write(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        st.write(f"**Keeper Threshold:** {config.format_currency(config.get_threshold('keeper_minimum'))}")
        st.write(f"**Optimasi Threshold:** {config.format_currency(config.get_threshold('optimasi_minimum'))}")
    except Exception:
        pass

    # Optional utility: tampilkan ringkas data CSV jika ada
    data_path = "data/difotoin_dashboard_data.csv"
    with st.expander("📄 Data File Info (opsional)"):
        if os.path.exists(data_path):
            try:
                df_info = pd.read_csv(data_path, nrows=5)
                st.write(f"Path: `{data_path}`")
                st.write(f"Rows (approx): ~{sum(1 for _ in open(data_path, 'r', encoding='utf-8', errors='ignore')) - 1:,}")
                st.dataframe(df_info, use_container_width=True)
            except Exception as e:
                st.warning(f"Tidak bisa membaca CSV: {e}")
        else:
            st.info("File data belum ada.")

    # Tombol reload halaman
    if st.button("🔄 Reload Page"):
        st.rerun()
