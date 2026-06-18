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
    st.markdown('<h1 class="main-header">📸 Dashboard</h1>', unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Enter your email", key="login_email")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")
        submitted = st.form_submit_button("🔐 Login")
        if submitted:
            user = authenticate_user(email, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = user.get("email", email)
                st.session_state["user_name"] = user.get("name", "")
                _set_query_param("auth", create_auth_session(user))
                st.success("Login successful! Redirecting...")
                rerun()
            else:
                st.error("Invalid email or password. Please try again.")
    st.markdown("---")
    st.info("Login memakai akun dari Admin Panel. Env var launcher tetap bisa dipakai sebagai admin fallback.")

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
