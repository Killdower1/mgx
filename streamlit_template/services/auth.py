import os
import json
import secrets
import hashlib
import base64
import hmac
import time
from typing import List, Tuple, Dict, Optional

import streamlit as st

from config import USERS_PATH, AUTH_SESSIONS_PATH, DELETED_OUTLETS_PATH

VALID_EMAIL = os.getenv("DIFOTOIN_ADMIN_EMAIL", "admin@difotoin.local")
VALID_PASSWORD = os.getenv("DIFOTOIN_ADMIN_PASSWORD", "")
AUTH_SESSION_TTL_SECONDS = int(os.getenv("DIFOTOIN_AUTH_SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60)))
AUTH_SIGNING_SECRET = os.getenv("DIFOTOIN_AUTH_SECRET", "") or VALID_PASSWORD or "difotoin-dashboard-auth"
AUTH_SIGNING_VERSION = "v1"

# ================= AUTH =================
def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()

def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt.encode("utf-8"), 120000)
    return salt, digest.hex()

def _verify_password(password: str, salt: str, password_hash: str) -> bool:
    if not password or not salt or not password_hash:
        return False
    _, digest = _hash_password(password, salt)
    return secrets.compare_digest(digest, str(password_hash))

def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

def _b64url_decode(value: str) -> bytes:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("utf-8"))

def _build_signed_auth_token(user: dict) -> str:
    payload = {
        "v": AUTH_SIGNING_VERSION,
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "exp": int(time.time()) + AUTH_SESSION_TTL_SECONDS,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(str(AUTH_SIGNING_SECRET).encode("utf-8"), body, hashlib.sha256).digest()
    return f"{_b64url_encode(body)}.{_b64url_encode(sig)}"

def _verify_signed_auth_token(token: str) -> Optional[dict]:
    if not token or "." not in str(token):
        return None
    try:
        body_part, sig_part = str(token).split(".", 1)
        body = _b64url_decode(body_part)
        expected_sig = hmac.new(str(AUTH_SIGNING_SECRET).encode("utf-8"), body, hashlib.sha256).digest()
        if not secrets.compare_digest(_b64url_decode(sig_part), expected_sig):
            return None
        payload = json.loads(body.decode("utf-8"))
        if payload.get("v") != AUTH_SIGNING_VERSION:
            return None
        expires_at = int(payload.get("exp", 0))
        if expires_at <= int(time.time()):
            return None
        return {
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "expires_at": expires_at,
        }
    except Exception:
        return None

def load_users() -> List[dict]:
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = data.get("users", []) if isinstance(data, dict) else []
        return users if isinstance(users, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        return []

def save_users(users: List[dict]) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, indent=2)

def load_deleted_outlets() -> List[str]:
    try:
        with open(DELETED_OUTLETS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        outlets = data.get("outlets", []) if isinstance(data, dict) else []
        return [str(x).strip() for x in outlets if str(x).strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

def save_deleted_outlets(outlets: List[str]) -> None:
    DELETED_OUTLETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = sorted(set(str(x).strip() for x in outlets if str(x).strip()))
    with open(DELETED_OUTLETS_PATH, "w", encoding="utf-8") as f:
        json.dump({"outlets": clean}, f, indent=2)

def load_auth_sessions() -> Dict[str, dict]:
    try:
        with open(AUTH_SESSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        sessions = data.get("sessions", {}) if isinstance(data, dict) else {}
        return sessions if isinstance(sessions, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def save_auth_sessions(sessions: Dict[str, dict]) -> None:
    AUTH_SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    clean = {
        token: session for token, session in sessions.items()
        if int(session.get("expires_at", 0)) > now
    }
    with open(AUTH_SESSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump({"sessions": clean}, f, indent=2)

def create_auth_session(user: dict) -> str:
    sessions = load_auth_sessions()
    token = _build_signed_auth_token(user)
    sessions[token] = {
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "expires_at": int(time.time()) + AUTH_SESSION_TTL_SECONDS,
    }
    save_auth_sessions(sessions)
    return token

def get_auth_session(token: str) -> Optional[dict]:
    if not token:
        return None
    sessions = load_auth_sessions()
    session = sessions.get(token)
    if session:
        if int(session.get("expires_at", 0)) <= int(time.time()):
            sessions.pop(token, None)
            save_auth_sessions(sessions)
        else:
            return session
    return _verify_signed_auth_token(token)

def revoke_auth_session(token: str) -> None:
    if not token:
        return
    sessions = load_auth_sessions()
    if token in sessions:
        sessions.pop(token, None)
        save_auth_sessions(sessions)

def _get_query_param(key: str) -> str:
    try:
        value = st.query_params.get(key, "")
        return value[0] if isinstance(value, list) else str(value or "")
    except Exception:
        try:
            values = st.experimental_get_query_params().get(key, [""])
            return values[0] if values else ""
        except Exception:
            return ""

def _set_query_param(key: str, value: str) -> None:
    try:
        st.query_params[key] = value
    except Exception:
        try:
            current = st.experimental_get_query_params()
            current[key] = value
            st.experimental_set_query_params(**current)
        except Exception:
            pass

def _clear_query_param(key: str) -> None:
    try:
        if key in st.query_params:
            del st.query_params[key]
    except Exception:
        try:
            current = st.experimental_get_query_params()
            current.pop(key, None)
            st.experimental_set_query_params(**current)
        except Exception:
            pass

def authenticate_user(email: str, password: str) -> Optional[dict]:
    email_norm = _normalize_email(email)
    for user in load_users():
        if _normalize_email(user.get("email")) == email_norm and _verify_password(password, user.get("salt", ""), user.get("password_hash", "")):
            return user
    if VALID_PASSWORD and email_norm == _normalize_email(VALID_EMAIL) and password == VALID_PASSWORD:
        return {"name": "Admin", "email": VALID_EMAIL, "source": "env"}
    return None

def _init_auth_state():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_email", None)
    st.session_state.setdefault("user_name", None)
    if not st.session_state.get("logged_in"):
        session = get_auth_session(_get_query_param("auth"))
        if session:
            st.session_state["logged_in"] = True
            st.session_state["user_email"] = session.get("email")
            st.session_state["user_name"] = session.get("name", "")

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

def check_login():
    _init_auth_state()
    return bool(st.session_state.get("logged_in"))
