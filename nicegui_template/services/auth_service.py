"""
Pure Python auth service for NiceGUI dashboard.
User & Role CRUD, password hashing, permission checks.
Supports local users.json + ERPNext session-based authentication.
Uses same config directory as streamlit_template for data persistence.
"""
import os
import json
import secrets
import hashlib
import time
from pathlib import Path
from typing import Optional, List

import requests

# Path: .../difotoin-dashboard/nicegui_template/services/auth_service.py
# We need: .../difotoin-dashboard/streamlit_template/config/
BASE_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
CONFIG_DIR = BASE_DIR / "config"
USERS_PATH = CONFIG_DIR / "users.json"
ROLES_PATH = CONFIG_DIR / "roles.json"
ERPNEXT_CONFIG_PATH = CONFIG_DIR / "erpnext_config.json"

# ── All known NAV routes ──
ALL_ROUTES = [
    "/", "/pending", "/trend", "/ai-decision", "/conversion", "/ranking",
    "/kemitraan", "/lead-partnership", "/lead-kemitraan",
    "/comparison", "/crud", "/admin", "/upload", "/master-data",
    "/revenue-sharing", "/creative-team", "/problem-booth",
]

# ── Default roles (used as fallback) ──
DEFAULT_ROLES = {
    "admin": ALL_ROUTES,
    "guest": ["/pending"],
    "manager": ["/", "/trend", "/conversion", "/ranking", "/kemitraan",
                "/lead-partnership", "/lead-kemitraan", "/comparison", "/master-data"],
    "creative": ["/creative-team", "/"],
    "staff": ["/", "/ranking", "/kemitraan", "/lead-partnership", "/lead-kemitraan", "/master-data"],
    "viewer": ["/"],
}


# ═══════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════

def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    )
    return salt, digest.hex()


def _verify_password(password: str, salt: str, password_hash: str) -> bool:
    if not password or not salt or not password_hash:
        return False
    _, digest = _hash_password(password, salt)
    return secrets.compare_digest(digest, password_hash)


# ═══════════════════════════════════════════════
#  ERPNEXT AUTH HELPERS
# ═══════════════════════════════════════════════

ERPNEXT_ROLE_MAPPING = {
    "System Manager": "admin",
    "Sales Manager": "manager",
    "Sales User": "staff",
    "Dashboard Read Only": "viewer",
}


def _load_erpnext_config() -> dict:
    """Load ERPNext connection config."""
    try:
        with open(ERPNEXT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _map_erpnext_role(erpnext_roles: list) -> str:
    """Map ERPNext roles to dashboard role. Most permissive wins."""
    if not erpnext_roles:
        return "viewer"
    priority = ["admin", "manager", "staff", "viewer"]
    mapped_rank = 3  # viewer default
    for er_role in erpnext_roles:
        dash_role = ERPNEXT_ROLE_MAPPING.get(er_role, "")
        if dash_role in priority:
            rank = priority.index(dash_role)
            if rank < mapped_rank:
                mapped_rank = rank
    return priority[mapped_rank]


# ═══════════════════════════════════════════════
#  USERS
# ═══════════════════════════════════════════════

def load_users() -> List[dict]:
    try:
        with open(USERS_PATH, "r") as f:
            data = json.load(f)
        users = data.get("users", []) if isinstance(data, dict) else []
        return users if isinstance(users, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_users(users: List[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w") as f:
        json.dump({"users": users}, f, indent=2)


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user. Tries: local users.json -> ERPNext -> env var admin."""
    email_norm = _normalize_email(email)

    # 1. Try local users.json
    for user in load_users():
        if (_normalize_email(user.get("email", "")) == email_norm
                and _verify_password(password, user.get("salt", ""), user.get("password_hash", ""))):
            user_dict = dict(user)
            user_dict.pop("salt", None)
            user_dict.pop("password_hash", None)
            user_dict["source"] = "local"
            return user_dict

    # 2. Try ERPNext session login
    erpnext_user = _erpnext_authenticate(email, password)
    if erpnext_user:
        return erpnext_user

    # 3. Fallback to env var admin
    admin_email = os.getenv("DIFOTOIN_ADMIN_EMAIL")
    admin_pass = os.getenv("DIFOTOIN_ADMIN_PASSWORD")
    if admin_email and admin_pass:
        if _normalize_email(admin_email) == email_norm and password == admin_pass:
            return {"name": "Admin", "email": admin_email, "role": "admin", "source": "env"}
    return None


def _erpnext_authenticate(email: str, password: str) -> Optional[dict]:
    """Authenticate via ERPNext session login.

    Calls ERPNext /api/method/login to verify credentials,
    then fetches the user's roles to determine dashboard permissions.

    Returns user dict with source='erpnext', or None on failure.
    """
    cfg = _load_erpnext_config()
    erp_url = cfg.get("url", "").rstrip("/")
    if not erp_url:
        return None

    session = requests.Session()
    try:
        # Step 1: Login to ERPNext
        r = session.post(
            f"{erp_url}/api/method/login",
            json={"usr": email, "pwd": password},
            timeout=15,
        )
        if r.status_code != 200:
            return None

        # Verify login was successful
        resp_json = r.json()
        if resp_json.get("message") != "Logged In":
            return None

        # Get full_name from login response
        full_name = resp_json.get("full_name", email)

        # Step 2: Fetch user record with roles
        r2 = session.get(
            f"{erp_url}/api/resource/User/{email}",
            timeout=15,
        )
        erp_roles = []
        if r2.status_code == 200:
            user_data = r2.json().get("data", {})
            roles_list = user_data.get("roles", [])
            erp_roles = [r.get("role", "") for r in roles_list if r.get("role")]

        # Step 3: Map ERPNext roles to dashboard role
        dash_role = _map_erpnext_role(erp_roles)

        # Step 4: Auto-register ke users.json kalo belum ada, atau pake override role
        local_users = load_users()
        user_exists = False
        for u in local_users:
            if _normalize_email(u.get('email', '')) == _normalize_email(email):
                user_exists = True
                if u.get('role'):
                    dash_role = u['role']  # override dari Admin Panel
                break

        if not user_exists:
            # Auto-register first-time ERPNext login ke users.json — set role "guest"
            create_user(full_name, email, "erpnext-auto", "guest")
            dash_role = "guest"  # override return role

        return {
            "name": full_name,
            "email": email,
            "role": dash_role,
            "source": "erpnext",
            "erpnext_roles": erp_roles,
        }
    except requests.exceptions.ConnectionError:
        return None  # ERPNext unreachable — let caller fall through
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None


def create_user(name: str, email: str, password: str, role: str = "viewer") -> Optional[dict]:
    """Create a new user. Returns user dict or None if email exists."""
    email = _normalize_email(email)
    if any(_normalize_email(u.get("email")) == email for u in load_users()):
        return None
    salt, pw_hash = _hash_password(password)
    user = {
        "name": name,
        "email": email,
        "salt": salt,
        "password_hash": pw_hash,
        "role": role,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    users = load_users()
    users.append(user)
    save_users(users)
    return {"name": name, "email": email, "role": role}


def update_user(email: str, updates: dict) -> bool:
    """Update user fields. Supports: name, role, password."""
    email = _normalize_email(email)
    users = load_users()
    for i, u in enumerate(users):
        if _normalize_email(u.get("email")) == email:
            for k, v in updates.items():
                if k == "password":
                    salt, pw_hash = _hash_password(v)
                    u["salt"] = salt
                    u["password_hash"] = pw_hash
                elif k in ("name", "role"):
                    u[k] = v
            u["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            users[i] = u
            save_users(users)
            return True
    return False


def delete_users(emails: List[str]) -> int:
    """Delete users by email. Returns count deleted."""
    norm = set(_normalize_email(e) for e in emails)
    remaining = [u for u in load_users() if _normalize_email(u.get("email")) not in norm]
    deleted = len(load_users()) - len(remaining)
    save_users(remaining)
    return deleted


# ═══════════════════════════════════════════════
#  ROLES
# ═══════════════════════════════════════════════

def load_roles() -> List[dict]:
    """Load roles from roles.json. Falls back to built-in defaults."""
    try:
        with open(ROLES_PATH, "r") as f:
            data = json.load(f)
        roles = data.get("roles", []) if isinstance(data, dict) else data
        if isinstance(roles, list) and len(roles) > 0:
            return roles
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # First-run: seed defaults
    roles = [{"name": name, "permissions": perms} for name, perms in DEFAULT_ROLES.items()]
    save_roles(roles)
    return roles


def save_roles(roles: List[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ROLES_PATH, "w") as f:
        json.dump({"roles": roles}, f, indent=2)


def get_role_permissions(role_name: str) -> List[str]:
    """Get permitted routes for a role."""
    for r in load_roles():
        if r.get("name") == role_name:
            return r.get("permissions", [])
    return DEFAULT_ROLES.get(role_name, [])


def has_permission(role_name: str, route: str) -> bool:
    """Check if a role may access a route."""
    if role_name == "admin":
        return True
    return route in get_role_permissions(role_name)


def get_allowed_routes(role_name: str) -> List[str]:
    """All routes a role may access (for filtering the nav drawer)."""
    if role_name == "admin":
        return ALL_ROUTES.copy()
    return get_role_permissions(role_name)


def create_role(name: str, permissions: List[str]) -> Optional[dict]:
    """Create a new role."""
    if any(r.get("name") == name for r in load_roles()):
        return None
    role = {"name": name, "permissions": permissions}
    roles = load_roles()
    roles.append(role)
    save_roles(roles)
    return role


def update_role(name: str, new_name: Optional[str] = None, permissions: Optional[List[str]] = None) -> bool:
    """Update role name / permissions."""
    roles = load_roles()
    for r in roles:
        if r.get("name") == name:
            if new_name is not None:
                r["name"] = new_name
            if permissions is not None:
                r["permissions"] = permissions
            save_roles(roles)
            return True
    return False


def delete_role(name: str) -> bool:
    """Delete a role. Cannot delete 'admin'."""
    if name == "admin":
        return False
    roles = [r for r in load_roles() if r.get("name") != name]
    save_roles(roles)
    return True


def fix_existing_users_roles():
    """Migrate existing users (no role field) to have a default 'viewer' role."""
    users = load_users()
    changed = False
    for u in users:
        if "role" not in u or not u.get("role"):
            u["role"] = "viewer"
            changed = True
    if changed:
        save_users(users)
