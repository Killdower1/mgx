import streamlit as st

from components.compat import rerun
from services.auth import (
    authenticate_user,
    create_auth_session,
    revoke_auth_session,
    _get_query_param,
    _set_query_param,
    _clear_query_param,
)

def show_login_page():
    st.markdown("""<style>
    [data-testid="stSidebar"]{display:none!important}
    [data-testid="collapsedControl"]{display:none!important}
    .stAppHeader{display:none!important}
    .main-header{margin-top:2rem!important}
    div[data-testid="stForm"]{
        max-width:420px;margin:2rem auto;
        background:linear-gradient(180deg,#1e293b 0%,#182235 100%);
        padding:2.5rem 2.5rem 2rem;
        border-radius:1.25rem;
        border:1px solid var(--df-border);
        box-shadow:0 16px 48px rgba(0,0,0,.35),0 0 0 1px rgba(56,189,248,.08) inset;
    }
    div[data-testid="stForm"]:hover{
        box-shadow:0 20px 56px rgba(0,0,0,.4),0 0 0 1px rgba(56,189,248,.15) inset;
        transition:box-shadow .3s ease;
    }
    div[data-testid="stForm"] button{
        width:100%;
        background:linear-gradient(135deg,#38bdf8,#0ea5e9)!important;
        border:none!important;
        border-radius:.75rem!important;
        font-weight:800!important;
        min-height:2.9rem;
        color:#06121f!important;
        font-size:1.05rem;
        letter-spacing:.3px;
        box-shadow:0 4px 16px rgba(56,189,248,.25);
    }
    div[data-testid="stForm"] button:hover{
        background:linear-gradient(135deg,#7dd3fc,#38bdf8)!important;
        box-shadow:0 6px 24px rgba(56,189,248,.35);
        transition:all .2s ease;
    }
    div[data-testid="stForm"] .stTextInput input{
        background:#0f172a!important;
        border:1px solid #334155!important;
        border-radius:.75rem!important;
        color:#f8fafc!important;
        padding:.7rem 1rem!important;
        font-size:.95rem!important;
        transition:border-color .2s ease,box-shadow .2s ease;
    }
    div[data-testid="stForm"] .stTextInput input:focus{
        border-color:#38bdf8!important;
        box-shadow:0 0 0 2px rgba(56,189,248,.15)!important;
    }
    div[data-testid="stForm"] label{color:#94a3b8!important;font-weight:600!important;font-size:.88rem!important;margin-bottom:.2rem!important}
    div[data-testid="stForm"] .stAlert{margin-top:1rem;border-radius:.75rem}
    .login-icon{font-size:3.2rem;margin-bottom:.25rem}
    .login-footer{text-align:center;color:var(--df-muted);font-size:.82rem;max-width:420px;margin:.5rem auto 0;line-height:1.5}
    </style>""", unsafe_allow_html=True)
    st.markdown("""<div style="text-align:center;padding:2.5rem 0 .5rem">
        <div class="login-icon">📸</div>
        <h1 class="main-header" style="margin-top:0;margin-bottom:.2rem">Difotoin Dashboard</h1>
        <p style="color:var(--df-muted);margin-top:0;font-size:.95rem">Monitoring Outlet &amp; Kemitraan</p>
    </div>""", unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Masukkan email anda", key="login_email", autocomplete="email")
        password = st.text_input("Password", type="password", placeholder="Masukkan password", key="login_pass", autocomplete="current-password")
        submitted = st.form_submit_button("🔐 Masuk")
        if submitted:
            user = authenticate_user(email, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = user.get("email", email)
                st.session_state["user_name"] = user.get("name", "")
                _set_query_param("auth", create_auth_session(user))
                st.success("Login berhasil! Mengarahkan...")
                rerun()
            else:
                st.error("Email atau password salah. Silakan coba lagi.")
    st.markdown("""<div class="login-footer">Gunakan akun yang terdaftar di Admin Panel.<br>Kredensial dari environment variable tetap bisa dipakai.</div>""", unsafe_allow_html=True)

def show_logout_button():
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", key="btn_logout"):
        revoke_auth_session(_get_query_param("auth"))
        _clear_query_param("auth")
        st.session_state["logged_in"] = False
        st.session_state["user_email"] = None
        st.session_state["user_name"] = None
        rerun()
    if st.session_state.get("user_email"):
        label = st.session_state.get("user_name") or st.session_state["user_email"]
        st.sidebar.markdown(f"Logged in as:\n{label}\n\n{st.session_state['user_email']}")
